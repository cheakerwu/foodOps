from food_ops_demo.models import ErrorDetail, OperationResult, Task
from food_ops_demo.parser import parse_instruction


def test_operation_result_can_describe_shadow_prefill_without_submit():
    result = OperationResult(
        success=True,
        submitted=False,
        shadow_mode=True,
        evidence={
            "adapter_mode": "shadow",
            "target_url": "http://127.0.0.1:8765/mock/merchant",
            "screenshot_path": "data/demo/shadow-mode-evidence/shadow-prefill-price.png",
        },
    )

    assert result.success is True
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.evidence["adapter_mode"] == "shadow"


def test_task_can_store_shadow_evidence():
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9").plan
    task = Task(
        instruction=plan.instruction,
        plan=plan,
        adapter_mode="shadow",
        shadow_evidence={"submitted": False, "intended_price": "29.90"},
    )

    assert task.adapter_mode == "shadow"
    assert task.shadow_evidence["submitted"] is False
    assert task.shadow_evidence["intended_price"] == "29.90"


from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.risk import validate_plan
from food_ops_demo.workflow import TaskManager


class RecordingShadowAdapter(FakePlatformAdapter):
    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        return OperationResult(
            success=True,
            submitted=False,
            shadow_mode=True,
            evidence={
                "adapter_mode": "shadow",
                "operation_type": "menu.update_price",
                "store_name": store_name,
                "target_name": item_name,
                "original_value": "32.00",
                "intended_value": price,
                "screenshot_path": "data/demo/shadow-mode-evidence/shadow-prefill-price.png",
            },
        )


def _shadow_price_plan(adapter):
    parsed = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    validated = validate_plan(parsed.plan, adapter)
    assert validated.plan is not None
    return validated.plan, validated.preview


def test_task_manager_stops_shadow_result_at_pending_review(tmp_path):
    adapter = RecordingShadowAdapter()
    plan, preview = _shadow_price_plan(adapter)
    manager = TaskManager(
        adapters={"shadow": adapter},
        default_adapter_mode="shadow",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="shadow")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "pending_review"
    assert completed.adapter_mode == "shadow"
    assert completed.before_snapshot["items"][0]["price"] == "32.00"
    assert completed.after_snapshot == {}
    assert completed.result["success"] is True
    assert completed.result["submitted"] is False
    assert completed.result["shadow_mode"] is True
    assert completed.shadow_evidence["intended_value"] == "29.90"
    assert [event.state for event in completed.timeline][-5:] == [
        "session_ready",
        "pre_snapshot_done",
        "executing",
        "shadow_prefilled",
        "pending_review",
    ]


def test_task_manager_keeps_fake_mode_committed_success(tmp_path):
    adapter = FakePlatformAdapter()
    plan, preview = _shadow_price_plan(adapter)
    manager = TaskManager(
        adapters={"fake": adapter},
        default_adapter_mode="fake",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="fake")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.result["submitted"] is True
    assert completed.result["shadow_mode"] is False
    assert completed.after_snapshot["items"][0]["price"] == "29.90"
