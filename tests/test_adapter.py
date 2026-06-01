from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.storage import DemoDatabase


def test_fake_adapter_returns_seed_snapshot():
    adapter = FakePlatformAdapter()

    snapshot = adapter.get_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.business_hours == [{"start": "09:30", "end": "21:30"}]
    assert [item.name for item in snapshot.items] == ["招牌牛肉饭", "可乐", "宫保鸡丁"]


def test_fake_adapter_updates_menu_price():
    adapter = FakePlatformAdapter()

    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    item = adapter.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert result.success is True
    assert item.price == "29.90"


def test_fake_adapter_updates_menu_sale_status():
    adapter = FakePlatformAdapter()

    result = adapter.update_menu_sale_status("人民广场店", "可乐", "off_sale")
    item = adapter.find_menu_items("人民广场店", "可乐")[0]

    assert result.success is True
    assert item.sale_status == "off_sale"


def test_fake_adapter_updates_business_hours():
    adapter = FakePlatformAdapter()

    result = adapter.update_business_hours("人民广场店", [{"start": "10:00", "end": "21:00"}])
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.business_hours == [{"start": "10:00", "end": "21:00"}]


def test_fake_adapter_reports_missing_target():
    adapter = FakePlatformAdapter()

    result = adapter.update_menu_price("人民广场店", "不存在的菜", "29.90")

    assert result.success is False
    assert result.error.code == "target_not_found"


def test_fake_adapter_can_persist_through_database(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = FakePlatformAdapter(database=DemoDatabase(path))
    first.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    second = FakePlatformAdapter(database=DemoDatabase(path))
    item = second.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "29.90"
