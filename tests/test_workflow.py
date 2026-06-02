import json

import pytest

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationPlan
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


def _validated_plan(text: str, adapter: FakePlatformAdapter):
    parsed = parse_instruction(text)
    assert parsed.plan is not None
    validated = validate_plan(parsed.plan, adapter)
    assert validated.plan is not None
    return validated.plan, validated.preview


def test_create_task_waits_for_approval(tmp_path):
    adapter = FakePlatformAdapter()
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"))
    plan, preview = _validated_plan("把人民广场店的招牌牛肉饭改成 29.9", adapter)

    task = manager.create_task(plan, preview)

    assert task.state == "awaiting_approval"
    assert task.preview["target_price"] == "29.90"
    assert [event.state for event in task.timeline] == [
        "created",
        "parsed",
        "validated",
        "previewed",
        "awaiting_approval",
    ]


def test_confirm_task_executes_and_writes_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    adapter = FakePlatformAdapter()
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(audit_path))
    plan, preview = _validated_plan("把人民广场店的招牌牛肉饭改成 29.9", adapter)
    task = manager.create_task(plan, preview)

    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.before_snapshot["items"][0]["price"] == "32.00"
    assert completed.after_snapshot["items"][0]["price"] == "29.90"
    assert completed.result["verified"] is True
    record = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert record["task_id"] == task.task_id
    assert record["result"]["verified"] is True


def test_task_manager_persists_tasks_across_instances(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的招牌牛肉饭改成 29.9", adapter)
    task = first.create_task(plan, preview)
    first.confirm_task(task.task_id)
    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = second.get_task(task.task_id)
    assert loaded is not None
    assert loaded.state == "succeeded"
    assert loaded.result["verified"] is True


def test_task_manager_default_adapter_uses_database_when_database_is_supplied(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    validation_adapter = FakePlatformAdapter(database=db)
    manager = TaskManager(audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的招牌牛肉饭改成 29.9", validation_adapter)
    task = manager.create_task(plan, preview)

    completed = manager.confirm_task(task.task_id)
    persisted_item = db.find_menu_items(plan.store_name, plan.target_name or "")[0]

    assert completed.state == "succeeded"
    assert persisted_item.price == "29.90"


def test_task_manager_persists_cancelled_task(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的可乐下架", adapter)
    task = first.create_task(plan, preview)

    first.cancel_task(task.task_id)
    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = second.get_task(task.task_id)

    assert loaded is not None
    assert loaded.state == "cancelled"


def test_task_manager_persists_manual_required_task(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的可乐下架", adapter)
    task = first.create_task(plan, preview)

    first.simulate_intervention(task.task_id, "login_expired")
    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = second.get_task(task.task_id)

    assert loaded is not None
    assert loaded.state == "manual_required"
    assert loaded.manual_intervention_type == "login_expired"


def test_task_manager_resumes_persisted_manual_task_to_success(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的可乐下架", adapter)
    task = first.create_task(plan, preview)
    first.simulate_intervention(task.task_id, "login_expired")

    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    resumed = second.resume_task(task.task_id)
    third = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = third.get_task(task.task_id)

    assert resumed.state == "succeeded"
    assert loaded is not None
    assert loaded.state == "succeeded"
    assert loaded.result["verified"] is True


def test_task_manager_persists_invalid_state_failure(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的可乐下架", adapter)
    task = first.create_task(plan, preview)
    first.confirm_task(task.task_id)

    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    failed = second.confirm_task(task.task_id)
    third = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = third.get_task(task.task_id)

    assert failed.state == "failed"
    assert loaded is not None
    assert loaded.state == "failed"
    assert loaded.error is not None
    assert loaded.error.code == "invalid_state"


def test_task_manager_persists_execution_failure(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan = OperationPlan(
        instruction="把人民广场店的不存在菜品改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="不存在菜品",
        changes={"price": "29.90"},
    )
    task = manager.create_task(plan, {})

    failed = manager.confirm_task(task.task_id)
    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = second.get_task(task.task_id)

    assert failed.state == "failed"
    assert loaded is not None
    assert loaded.state == "failed"
    assert loaded.error is not None
    assert loaded.error.code == "target_not_found"


def test_task_manager_list_tasks_rejects_negative_limit(tmp_path):
    manager = TaskManager(adapter=FakePlatformAdapter(), audit_log=AuditLog(tmp_path / "audit.jsonl"))

    with pytest.raises(ValueError, match="limit"):
        manager.list_tasks(limit=-1)


def test_manual_intervention_can_resume_to_success(tmp_path):
    adapter = FakePlatformAdapter()
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"))
    plan, preview = _validated_plan("把人民广场店的可乐下架", adapter)
    task = manager.create_task(plan, preview)

    manual = manager.simulate_intervention(task.task_id, "login_expired")
    resumed = manager.resume_task(task.task_id)

    assert manual.state == "manual_required"
    assert resumed.state == "succeeded"
    assert resumed.manual_intervention_type == "login_expired"
    assert adapter.find_menu_items("人民广场店", "可乐")[0].sale_status == "off_sale"


def test_confirm_phone_update_changes_snapshot(tmp_path):
    adapter = FakePlatformAdapter()
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"))
    plan, preview = _validated_plan("把人民广场店联系电话改成 021-66668888", adapter)
    task = manager.create_task(plan, preview)

    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.after_snapshot["phone"] == "021-66668888"
