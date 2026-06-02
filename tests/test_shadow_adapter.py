from pathlib import Path

import pytest

from food_ops_demo.shadow_adapter import ShadowPlatformAdapter


@pytest.fixture
def mock_page_url() -> str:
    return Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri()


def test_shadow_adapter_prefills_price_without_saving(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        before = adapter.get_snapshot("人民广场店")
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
        after = adapter.get_snapshot("人民广场店")
    finally:
        adapter.close()

    assert before.items[0].price == "32.00"
    assert after.items[0].price == "32.00"
    assert result.success is True
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.evidence["adapter_mode"] == "shadow"
    assert result.evidence["operation_type"] == "menu.update_price"
    assert result.evidence["store_name"] == "人民广场店"
    assert result.evidence["target_name"] == "招牌牛肉饭"
    assert result.evidence["original_value"] == "32.00"
    assert result.evidence["intended_value"] == "29.90"
    assert Path(result.evidence["screenshot_path"]).exists()


def test_shadow_adapter_returns_not_found_without_prefill(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "不存在的菜", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.error.code == "target_not_found"
