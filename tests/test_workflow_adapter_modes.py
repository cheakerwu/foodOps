from __future__ import annotations

from food_ops_demo.adapter import BasePlatformAdapter, FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import ErrorDetail, OperationResult
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.workflow import TaskManager


class RecordingAdapter(FakePlatformAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.price_updates: list[tuple[str, str, str]] = []

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        self.price_updates.append((store_name, item_name, price))
        return super().update_menu_price(store_name, item_name, price)


def _validated_price_plan(adapter: BasePlatformAdapter):
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9").plan
    result = validate_plan(plan, adapter)
    assert result.plan is not None
    return result.plan, result.preview


def test_task_manager_routes_execution_to_task_adapter_mode(tmp_path):
    fake = RecordingAdapter()
    mock_web = RecordingAdapter()
    plan, preview = _validated_price_plan(mock_web)
    manager = TaskManager(
        adapters={"fake": fake, "mock_web": mock_web},
        default_adapter_mode="fake",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="mock_web")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.adapter_mode == "mock_web"
    assert fake.price_updates == []
    assert mock_web.price_updates == [("人民广场店", "招牌牛肉饭", "29.90")]


def test_task_manager_rejects_unknown_adapter_mode(tmp_path):
    fake = RecordingAdapter()
    plan, preview = _validated_price_plan(fake)
    manager = TaskManager(adapters={"fake": fake}, audit_log=AuditLog(tmp_path / "audit.jsonl"))

    task = manager.create_task(plan, preview, adapter_mode="missing")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "failed"
    assert completed.error.code == "adapter_mode_not_found"
