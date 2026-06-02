from food_ops_demo.models import OperationPlan
from food_ops_demo.orchestration import (
    BatchPriceChange,
    StorePriceChange,
    build_child_plans,
    lock_key_for_plan,
)


def test_build_child_plans_for_multi_store_price_changes():
    batch = BatchPriceChange(
        instruction="把三个门店的招牌牛肉饭分别改成不同价格",
        platform_account_id="meituan_account_001",
        changes=[
            StorePriceChange(store_name="人民广场店", item_name="招牌牛肉饭", price="29.90"),
            StorePriceChange(store_name="五角场店", item_name="招牌牛肉饭", price="31.90"),
            StorePriceChange(store_name="徐家汇店", item_name="招牌牛肉饭", price="26.50"),
        ],
    )

    plans = build_child_plans(batch)

    assert [plan.store_name for plan in plans] == ["人民广场店", "五角场店", "徐家汇店"]
    assert [plan.changes["price"] for plan in plans] == ["29.90", "31.90", "26.50"]
    assert all(plan.operation_type == "menu.update_price" for plan in plans)
    assert all(plan.requires_approval is True for plan in plans)


def test_lock_key_uses_platform_account_and_store():
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
        risk_level="medium",
        requires_approval=True,
    )

    assert lock_key_for_plan("meituan_account_001", plan) == "meituan_account_001:人民广场店"
