from food_ops_demo.models import OperationPlan, Task
from food_ops_demo.repositories import JobQueueRepository, StoreRepository, TaskRepository
from food_ops_demo.storage import DemoDatabase


def _database(tmp_path):
    return DemoDatabase(tmp_path / "food_ops.sqlite3")


def test_store_repository_reads_and_updates_price(tmp_path):
    db = _database(tmp_path)
    stores = StoreRepository(db)

    assert stores.get_snapshot("人民广场店").items[0].price == "32.00"
    assert stores.update_menu_price("人民广场店", "招牌牛肉饭", "29.90") is True
    assert stores.find_menu_items("人民广场店", "招牌牛肉饭")[0].price == "29.90"


def test_task_repository_round_trips_task(tmp_path):
    db = _database(tmp_path)
    tasks = TaskRepository(db)
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
    )
    task = Task(instruction=plan.instruction, plan=plan, preview={})

    tasks.save(task)

    assert tasks.get(task.task_id).task_id == task.task_id
    assert tasks.list(limit=1)[0].task_id == task.task_id


def test_job_queue_repository_serializes_same_lock(tmp_path):
    db = _database(tmp_path)
    jobs = JobQueueRepository(db)
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
    )
    jobs.enqueue(
        batch_id="batch_1",
        task_id="task_1",
        adapter_mode="mock_web",
        platform_account_id="account_1",
        lock_key="account_1:人民广场店",
        plan=plan,
    )
    jobs.enqueue(
        batch_id="batch_1",
        task_id="task_2",
        adapter_mode="mock_web",
        platform_account_id="account_1",
        lock_key="account_1:人民广场店",
        plan=plan,
    )

    first = jobs.acquire_next(worker_id="worker_1", lease_seconds=60)
    second = jobs.acquire_next(worker_id="worker_2", lease_seconds=60)

    assert first is not None
    assert second is None
