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
