from unittest.mock import MagicMock

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationResult
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.runner import LocalRunner
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


class RecordingBrowserAdapter(FakePlatformAdapter):
    def __init__(self, database):
        super().__init__(database=database)
        self.closed = False

    def close(self):
        self.closed = True


def test_browser_task_can_be_queued_and_completed_by_runner(tmp_path):
    database = DemoDatabase(tmp_path / "food_ops.sqlite3")
    audit = AuditLog(tmp_path / "audit.jsonl")
    created_adapters = []

    def factory():
        adapter = RecordingBrowserAdapter(database)
        created_adapters.append(adapter)
        return adapter

    registry = AdapterRegistry({"browser_use": factory}, shared_modes=set())
    validation_adapter = FakePlatformAdapter(database=database)
    parsed = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    validated = validate_plan(parsed.plan, validation_adapter)
    manager = TaskManager(
        adapter_registry=registry,
        default_adapter_mode="browser_use",
        audit_log=audit,
        database=database,
        queue_browser_modes=True,
        platform_account_id="account_local",
    )
    task = manager.create_task(validated.plan, validated.preview, adapter_mode="browser_use")
    queued = manager.confirm_task(task.task_id)

    assert queued.state == "queued"
    assert queued.result["queued"] is True

    runner = LocalRunner(database=database, adapter_registry=registry, worker_id="worker_1", audit_log=audit)
    processed = runner.run_once()
    completed = database.get_task(task.task_id)

    assert processed == 1
    assert completed.state == "succeeded"
    assert completed.result["verified"] is True
    assert created_adapters[0].closed is True
