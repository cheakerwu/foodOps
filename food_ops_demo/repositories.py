from __future__ import annotations

from food_ops_demo.models import OperationPlan, Task
from food_ops_demo.storage import DemoDatabase


class StoreRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def get_snapshot(self, store_name: str):
        return self.database.get_store_snapshot(store_name)

    def find_menu_items(self, store_name: str, item_name: str):
        return self.database.find_menu_items(store_name, item_name)

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> bool:
        return self.database.update_menu_price(store_name, item_name, price)

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> bool:
        return self.database.update_menu_sale_status(store_name, item_name, sale_status)

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> bool:
        return self.database.update_business_hours(store_name, business_hours)

    def update_store_phone(self, store_name: str, phone: str) -> bool:
        return self.database.update_store_phone(store_name, phone)

    def reset_seed_data(self) -> None:
        self.database.reset_demo_data()


class TaskRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def save(self, task: Task) -> None:
        self.database.save_task(task)

    def get(self, task_id: str) -> Task | None:
        return self.database.get_task(task_id)

    def list(self, limit: int = 20) -> list[Task]:
        return self.database.list_tasks(limit=limit)


class JobQueueRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def enqueue(
        self,
        batch_id: str,
        task_id: str,
        adapter_mode: str,
        platform_account_id: str,
        lock_key: str,
        plan: OperationPlan,
    ) -> str:
        return self.database.enqueue_job(
            batch_id=batch_id,
            task_id=task_id,
            adapter_mode=adapter_mode,
            platform_account_id=platform_account_id,
            lock_key=lock_key,
            plan=plan,
        )

    def acquire_next(self, worker_id: str, lease_seconds: int) -> dict | None:
        return self.database.acquire_next_job(worker_id=worker_id, lease_seconds=lease_seconds)

    def complete(self, job_id: str, state: str, result: dict) -> None:
        self.database.complete_job(job_id=job_id, state=state, result=result)
