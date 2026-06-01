from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan


def test_single_item_price_change_is_medium_risk_and_requires_approval():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.plan.risk_level == "medium"
    assert result.plan.requires_approval is True
    assert result.preview["current_price"] == "32.00"
    assert result.preview["target_price"] == "29.90"


def test_large_price_change_is_high_risk():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 60").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.plan.risk_level == "high"
    assert result.plan.requires_approval is True


def test_price_below_one_yuan_is_rejected():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 0.5").plan

    result = validate_plan(plan, adapter)

    assert result.plan is None
    assert result.errors[0].code == "price_too_low"


def test_unknown_menu_item_is_rejected():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的不存在的菜改成 29.9").plan

    result = validate_plan(plan, adapter)

    assert result.plan is None
    assert result.errors[0].code == "target_not_found"


def test_sale_status_change_is_medium_risk():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的可乐下架").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.plan.risk_level == "medium"
    assert result.plan.requires_approval is True
    assert result.preview["current_sale_status"] == "on_sale"
    assert result.preview["target_sale_status"] == "off_sale"


def test_business_hours_change_is_high_risk():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店营业时间改成 10:00 到 21:00").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.plan.risk_level == "high"
    assert result.plan.requires_approval is True
    assert result.preview["current_business_hours"] == [{"start": "09:30", "end": "21:30"}]
    assert result.preview["target_business_hours"] == [{"start": "10:00", "end": "21:00"}]
