from __future__ import annotations

from pathlib import Path
from typing import Any

from food_ops_demo.adapter import BasePlatformAdapter, FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import ErrorDetail, OperationPlan, OperationResult, Task, TimelineEvent, utc_now_iso
from food_ops_demo.storage import DemoDatabase


class TaskManager:
    def __init__(
        self,
        adapter: BasePlatformAdapter | None = None,
        audit_log: AuditLog | None = None,
        database: DemoDatabase | None = None,
    ) -> None:
        self.adapter = adapter or FakePlatformAdapter(database=database)
        self.audit_log = audit_log or AuditLog(Path("data/demo/audit.jsonl"))
        self.database = database
        self._tasks: dict[str, Task] = {}

    def create_task(self, plan: OperationPlan, preview: dict[str, Any]) -> Task:
        task = Task(instruction=plan.instruction, plan=plan, preview=preview)
        for state, message in [
            ("created", "任务已创建。"),
            ("parsed", "指令已解析为标准操作计划。"),
            ("validated", "风险规则已校验。"),
            ("previewed", "变更预览已生成。"),
            ("awaiting_approval", "等待人工确认。"),
        ]:
            self._set_state(task, state, message)
        self._tasks[task.task_id] = task
        self._persist(task)
        return self._copy(task)

    def get_task(self, task_id: str) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None and self.database is not None:
            task = self.database.get_task(task_id)
            if task is not None:
                self._tasks[task.task_id] = task
        return self._copy(task) if task else None

    def list_tasks(self, limit: int = 20) -> list[Task]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        if self.database is not None:
            return [self._copy(task) for task in self.database.list_tasks(limit=limit)]
        return [
            self._copy(task)
            for task in sorted(self._tasks.values(), key=lambda item: item.updated_at, reverse=True)[:limit]
        ]

    def confirm_task(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        if task.state != "awaiting_approval":
            self._fail(task, "invalid_state", "只有等待确认的任务可以执行。")
            self._persist(task)
            return self._copy(task)
        return self._execute(task)

    def simulate_intervention(self, task_id: str, intervention_type: str) -> Task:
        task = self._require_task(task_id)
        task.manual_intervention_type = intervention_type
        self._set_state(task, "manual_required", f"需要人工介入：{intervention_type}。")
        self._persist(task)
        return self._copy(task)

    def resume_task(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        if task.state != "manual_required":
            self._fail(task, "invalid_state", "只有人工介入中的任务可以继续。")
            self._persist(task)
            return self._copy(task)
        self._set_state(task, "executing", "人工处理完成，继续执行。")
        return self._execute(task, skip_queue=True)

    def cancel_task(self, task_id: str) -> Task:
        task = self._require_task(task_id)
        self._set_state(task, "cancelled", "任务已取消。")
        self._persist(task)
        return self._copy(task)

    def _execute(self, task: Task, skip_queue: bool = False) -> Task:
        if not skip_queue:
            self._set_state(task, "queued", "任务已进入执行队列。")
            self._set_state(task, "executing", "正在通过 FakeAdapter 执行。")

        try:
            task.before_snapshot = self.adapter.get_snapshot(task.plan.store_name).model_dump(mode="json")
        except KeyError:
            self._fail(task, "store_not_found", f"找不到门店：{task.plan.store_name}")
            self._append_audit(task)
            self._persist(task)
            return self._copy(task)

        result = self._apply_plan(task.plan)
        if not result.success:
            task.error = result.error
            self._set_state(task, "failed", result.error.message if result.error else "执行失败。", result.error.code if result.error else None)
            self._append_audit(task)
            self._persist(task)
            return self._copy(task)

        self._set_state(task, "verifying", "正在回读校验执行结果。")
        task.after_snapshot = self.adapter.get_snapshot(task.plan.store_name).model_dump(mode="json")
        verified = self._verify(task.plan, task.after_snapshot)
        task.result = {"success": result.success, "verified": verified}
        if verified:
            self._set_state(task, "succeeded", "任务执行成功，回读校验通过。")
        else:
            self._fail(task, "verification_failed", "执行后回读校验未通过。")
        self._append_audit(task)
        self._persist(task)
        return self._copy(task)

    def _apply_plan(self, plan: OperationPlan) -> OperationResult:
        if plan.operation_type == "menu.update_price":
            return self.adapter.update_menu_price(plan.store_name, plan.target_name or "", plan.changes["price"])
        if plan.operation_type == "menu.update_sale_status":
            return self.adapter.update_menu_sale_status(plan.store_name, plan.target_name or "", plan.changes["sale_status"])
        if plan.operation_type == "store.update_business_hours":
            return self.adapter.update_business_hours(plan.store_name, plan.changes["business_hours"])
        if plan.operation_type == "store.update_phone":
            return self.adapter.update_store_phone(plan.store_name, plan.changes["phone"])
        return OperationResult(
            success=False,
            error=ErrorDetail(code="unsupported_operation", message=f"暂不支持操作类型：{plan.operation_type}"),
        )

    def _verify(self, plan: OperationPlan, snapshot: dict[str, Any]) -> bool:
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

    def _append_audit(self, task: Task) -> None:
        self.audit_log.append(task.model_dump(mode="json"))

    def _set_state(self, task: Task, state: str, message: str, error_code: str | None = None) -> None:
        task.state = state
        task.updated_at = utc_now_iso()
        task.timeline.append(TimelineEvent(state=state, message=message, error_code=error_code))

    def _fail(self, task: Task, code: str, message: str) -> None:
        task.error = ErrorDetail(code=code, message=message)
        self._set_state(task, "failed", message, code)

    def _require_task(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None and self.database is not None:
            task = self.database.get_task(task_id)
            if task is not None:
                self._tasks[task.task_id] = task
        if task is None:
            raise KeyError(task_id)
        return task

    def _copy(self, task: Task) -> Task:
        return task.model_copy(deep=True)

    def _persist(self, task: Task) -> None:
        if self.database is not None:
            self.database.save_task(task)
