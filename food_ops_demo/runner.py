from __future__ import annotations

from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationPlan, Task, TimelineEvent, utc_now_iso
from food_ops_demo.storage import DemoDatabase


class LocalRunner:
    def __init__(
        self,
        database: DemoDatabase,
        adapter_registry: AdapterRegistry,
        worker_id: str,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.database = database
        self.adapter_registry = adapter_registry
        self.worker_id = worker_id
        self.audit_log = audit_log

    def run_once(self) -> int:
        job = self.database.acquire_next_job(worker_id=self.worker_id, lease_seconds=60)
        if job is None:
            return 0

        task_id = job["task_id"]
        task = self.database.get_task(task_id)
        plan = OperationPlan.model_validate_json(job["plan_json"])

        if task is not None:
            self._set_state(task, "executing", f"Runner {self.worker_id} 开始执行。")
            self.database.save_task(task)

        with self.adapter_registry.use(job["adapter_mode"]) as adapter:
            if adapter is None:
                result = {"success": False, "error_code": "adapter_mode_not_found"}
                if task is not None:
                    task.error = None
                    self._set_state(task, "failed", "找不到执行模式。", "adapter_mode_not_found")
                    self.database.save_task(task)
                    if self.audit_log is not None:
                        self.audit_log.append(task.model_dump(mode="json"))
                self.database.complete_job(job["job_id"], state="failed", result=result)
                return 1

            # Capture before snapshot
            try:
                before_snapshot = adapter.get_snapshot(plan.store_name).model_dump(mode="json")
            except KeyError:
                result = {"success": False, "error_code": "store_not_found"}
                if task is not None:
                    self._set_state(task, "failed", f"找不到门店：{plan.store_name}", "store_not_found")
                    self.database.save_task(task)
                    if self.audit_log is not None:
                        self.audit_log.append(task.model_dump(mode="json"))
                self.database.complete_job(job["job_id"], state="failed", result=result)
                return 1

            if task is not None:
                task.before_snapshot = before_snapshot

            # Apply the plan
            op_result = self._apply_plan(plan, adapter)

            if not op_result.success:
                result = op_result.model_dump(mode="json")
                if task is not None:
                    self._set_state(
                        task,
                        "failed",
                        op_result.error.message if op_result.error else "执行失败。",
                        op_result.error.code if op_result.error else None,
                    )
                    self.database.save_task(task)
                    if self.audit_log is not None:
                        self.audit_log.append(task.model_dump(mode="json"))
                self.database.complete_job(job["job_id"], state="failed", result=result)
                return 1

            # Verify
            self._set_state(task, "verifying", "正在回读校验执行结果。") if task is not None else None
            after_snapshot = adapter.get_snapshot(plan.store_name).model_dump(mode="json")
            if task is not None:
                task.after_snapshot = after_snapshot
            verified = self._verify(plan, after_snapshot)

            final_result = {
                "success": True,
                "verified": verified,
                "submitted": op_result.submitted,
                "shadow_mode": op_result.shadow_mode,
                "evidence": op_result.evidence,
                "screenshot_paths": op_result.screenshot_paths,
            }

            if task is not None:
                task.result = final_result
                if verified:
                    self._set_state(task, "succeeded", "任务执行成功，回读校验通过。")
                else:
                    self._set_state(task, "failed", "执行后回读校验未通过。", "verification_failed")
                self.database.save_task(task)
                if self.audit_log is not None:
                    self.audit_log.append(task.model_dump(mode="json"))

            self.database.complete_job(
                job["job_id"],
                state="succeeded" if verified else "failed",
                result=final_result,
            )

        return 1

    def _set_state(self, task: Task, state: str, message: str, error_code: str | None = None) -> None:
        task.state = state
        task.updated_at = utc_now_iso()
        task.timeline.append(TimelineEvent(state=state, message=message, error_code=error_code))

    def _verify(self, plan: OperationPlan, snapshot: dict) -> bool:
        if plan.operation_type == "store.update_business_hours":
            return snapshot["business_hours"] == plan.changes["business_hours"]
        if plan.operation_type == "store.update_phone":
            return snapshot["phone"] == plan.changes["phone"]
        matches = [item for item in snapshot["items"] if item["name"] == plan.target_name]
        if len(matches) != 1:
            return False
        item = matches[0]
        if plan.operation_type == "menu.update_price":
            return item["price"] == plan.changes["price"]
        if plan.operation_type == "menu.update_sale_status":
            return item["sale_status"] == plan.changes["sale_status"]
        return False

    def _apply_plan(self, plan: OperationPlan, adapter) -> object:
        if plan.operation_type == "menu.update_price":
            return adapter.update_menu_price(plan.store_name, plan.target_name or "", plan.changes["price"])
        if plan.operation_type == "menu.update_sale_status":
            return adapter.update_menu_sale_status(plan.store_name, plan.target_name or "", plan.changes["sale_status"])
        if plan.operation_type == "store.update_business_hours":
            return adapter.update_business_hours(plan.store_name, plan.changes["business_hours"])
        if plan.operation_type == "store.update_phone":
            return adapter.update_store_phone(plan.store_name, plan.changes["phone"])
        raise ValueError(f"unsupported operation type: {plan.operation_type}")
