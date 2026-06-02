from food_ops_demo.models import OperationResult, Task
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
