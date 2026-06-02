from __future__ import annotations

from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.models import OperationPlan
from food_ops_demo.storage import DemoDatabase


class LocalRunner:
    def __init__(self, database: DemoDatabase, adapter_registry: AdapterRegistry, worker_id: str) -> None:
        self.database = database
        self.adapter_registry = adapter_registry
        self.worker_id = worker_id

    def run_once(self) -> int:
        job = self.database.acquire_next_job(worker_id=self.worker_id, lease_seconds=60)
        if job is None:
            return 0

        plan = OperationPlan.model_validate_json(job["plan_json"])
        with self.adapter_registry.use(job["adapter_mode"]) as adapter:
            if adapter is None:
                self.database.complete_job(
                    job["job_id"],
                    state="failed",
                    result={"success": False, "error_code": "adapter_mode_not_found"},
                )
                return 1
            result = self._apply_plan(plan, adapter)
            self.database.complete_job(
                job["job_id"],
                state="succeeded" if result.success else "failed",
                result=result.model_dump(mode="json"),
            )
        return 1

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
