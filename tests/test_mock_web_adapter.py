from pathlib import Path

import pytest

from food_ops_demo.mock_web_adapter import MockWebAdapter


@pytest.fixture
def mock_page_url() -> str:
    return Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri()


@pytest.fixture
def adapter(mock_page_url):
    adapter = MockWebAdapter(page_url=mock_page_url, headless=True)
    try:
        yield adapter
    finally:
        adapter.close()


def test_mock_web_adapter_reads_seed_snapshot(adapter):
    snapshot = adapter.get_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.phone == "021-88888888"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


def test_mock_web_adapter_updates_price_through_page(adapter):
    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    item = adapter.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert result.success is True
    assert item.price == "29.90"


def test_mock_web_adapter_updates_sale_status_through_page(adapter):
    result = adapter.update_menu_sale_status("人民广场店", "可乐", "sold_out")
    item = adapter.find_menu_items("人民广场店", "可乐")[0]

    assert result.success is True
    assert item.sale_status == "sold_out"


def test_mock_web_adapter_updates_store_phone_through_page(adapter):
    result = adapter.update_store_phone("人民广场店", "021-66668888")
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.phone == "021-66668888"


def test_mock_web_adapter_updates_business_hours_through_page(adapter):
    result = adapter.update_business_hours("人民广场店", [{"start": "10:00", "end": "21:00"}])
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.business_hours == [{"start": "10:00", "end": "21:00"}]


def test_mock_web_adapter_saves_screenshot_after_success(mock_page_url, tmp_path):
    adapter = MockWebAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert (tmp_path / "last-success.png").exists()


def test_mock_web_adapter_reports_auth_required(mock_page_url):
    adapter = MockWebAdapter(page_url=f"{mock_page_url}?scenario=auth_required", headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.error.code == "auth_required"


def test_mock_web_adapter_reports_save_failure(mock_page_url):
    adapter = MockWebAdapter(page_url=f"{mock_page_url}?scenario=save_failure", headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.error.code == "mock_save_failed"
