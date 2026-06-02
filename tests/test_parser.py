from food_ops_demo.parser import parse_instruction


def test_parse_price_update_instruction():
    result = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")

    assert not result.errors
    assert result.plan is not None
    assert result.plan.operation_type == "menu.update_price"
    assert result.plan.store_name == "人民广场店"
    assert result.plan.target_name == "招牌牛肉饭"
    assert result.plan.changes["price"] == "29.90"


def test_parse_sale_status_instruction():
    result = parse_instruction("把人民广场店的可乐下架")

    assert not result.errors
    assert result.plan is not None
    assert result.plan.operation_type == "menu.update_sale_status"
    assert result.plan.store_name == "人民广场店"
    assert result.plan.target_name == "可乐"
    assert result.plan.changes["sale_status"] == "off_sale"


def test_parse_business_hours_instruction():
    result = parse_instruction("把人民广场店营业时间改成 10:00 到 21:00")

    assert not result.errors
    assert result.plan is not None
    assert result.plan.operation_type == "store.update_business_hours"
    assert result.plan.store_name == "人民广场店"
    assert result.plan.changes["business_hours"] == [{"start": "10:00", "end": "21:00"}]


def test_unknown_instruction_has_clear_error():
    result = parse_instruction("帮我优化一下菜单")

    assert result.plan is None
    assert result.errors[0].code == "unsupported_instruction"


def test_parse_store_phone_update_instruction():
    result = parse_instruction("把人民广场店联系电话改成 021-66668888")

    assert not result.errors
    assert result.plan is not None
    assert result.plan.operation_type == "store.update_phone"
    assert result.plan.store_name == "人民广场店"
    assert result.plan.changes["phone"] == "021-66668888"


def test_parse_mark_sold_out_alias():
    result = parse_instruction("把人民广场店的可乐设为售罄")

    assert not result.errors
    assert result.plan.operation_type == "menu.update_sale_status"
    assert result.plan.changes["sale_status"] == "sold_out"


def test_parse_restore_sale_alias():
    result = parse_instruction("把人民广场店的可乐恢复销售")

    assert not result.errors
    assert result.plan.operation_type == "menu.update_sale_status"
    assert result.plan.changes["sale_status"] == "on_sale"
