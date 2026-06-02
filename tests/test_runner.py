from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.models import OperationPlan
from food_ops_demo.runner import LocalRunner
from food_ops_demo.storage import DemoDatabase


def test_local_runner_processes_one_fake_job(tmp_path):
    database = DemoDatabase(tmp_path / "demo.sqlite3")
    fake = FakePlatformAdapter(database=database)
    registry = AdapterRegistry({"fake": lambda: fake}, shared_modes={"fake"})
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
        risk_level="medium",
        requires_approval=True,
    )
    database.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="fake",
        platform_account_id="local_demo",
        lock_key="local_demo:人民广场店",
        plan=plan,
    )
    runner = LocalRunner(database=database, adapter_registry=registry, worker_id="runner_001")

    processed = runner.run_once()
    snapshot = database.get_store_snapshot("人民广场店")

    assert processed == 1
    assert snapshot.items[0].price == "29.90"
