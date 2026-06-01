import json

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
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
