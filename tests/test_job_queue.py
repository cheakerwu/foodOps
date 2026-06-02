from food_ops_demo.models import OperationPlan
from food_ops_demo.storage import DemoDatabase


def _plan(store_name: str, price: str) -> OperationPlan:
    return OperationPlan(
        instruction=f"把{store_name}的招牌牛肉饭改成 {price}",
        operation_type="menu.update_price",
        store_name=store_name,
        target_name="招牌牛肉饭",
        changes={"price": price},
        risk_level="medium",
        requires_approval=True,
    )


def test_job_queue_acquires_one_job_per_lock_key(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_002",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "31.90"),
    )

    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)
    second = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert first is not None
    assert first["task_id"] == "task_001"
    assert second is None


def test_job_queue_allows_different_store_locks(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_002",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:五角场店",
        plan=_plan("五角场店", "31.90"),
    )

    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)
    second = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert first is not None
    assert second is not None
    assert {first["task_id"], second["task_id"]} == {"task_001", "task_002"}


def test_complete_job_releases_lock(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)

    db.complete_job(first["job_id"], state="succeeded", result={"success": True})
    next_job = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert next_job is None
