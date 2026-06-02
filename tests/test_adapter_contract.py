from pathlib import Path

import pytest

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.mock_web_adapter import MockWebAdapter
from food_ops_demo.storage import DemoDatabase


@pytest.fixture(params=["memory", "sqlite", "mock_web"], ids=["memory", "sqlite", "mock_web"])
def adapter(request, tmp_path):
    if request.param == "memory":
        yield FakePlatformAdapter()
        return
    if request.param == "sqlite":
        yield FakePlatformAdapter(database=DemoDatabase(tmp_path / "demo.sqlite3"))
        return

    adapter = MockWebAdapter(
        page_url=Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri(),
        screenshot_dir=tmp_path / "screenshots",
        headless=True,
    )
    try:
        yield adapter
    finally:
        adapter.close()


def test_adapter_contract_updates_menu_price(adapter):
    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    item = adapter.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert result.success is True
    assert item.price == "29.90"


def test_adapter_contract_updates_menu_sale_status(adapter):
    result = adapter.update_menu_sale_status("人民广场店", "可乐", "sold_out")
    item = adapter.find_menu_items("人民广场店", "可乐")[0]

    assert result.success is True
    assert item.sale_status == "sold_out"


def test_adapter_contract_updates_store_fields(adapter):
    business_hours = [{"start": "10:00", "end": "21:00"}]

    phone_result = adapter.update_store_phone("人民广场店", "021-66668888")
    hours_result = adapter.update_business_hours("人民广场店", business_hours)
    snapshot = adapter.get_snapshot("人民广场店")

    assert phone_result.success is True
    assert hours_result.success is True
    assert snapshot.phone == "021-66668888"
    assert snapshot.business_hours == business_hours
