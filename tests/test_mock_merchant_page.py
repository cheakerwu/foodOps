from pathlib import Path

from fastapi.testclient import TestClient

from food_ops_demo.app import create_app


def test_mock_merchant_page_file_contains_required_controls():
    html = Path("food_ops_demo/static/mock_merchant.html").read_text(encoding="utf-8")

    assert 'id="mockMerchantApp"' in html
    assert 'data-testid="store-phone-input"' in html
    assert 'data-testid="business-hours-start-input"' in html
    assert 'data-testid="business-hours-end-input"' in html
    assert 'data-testid="item-row-item_001"' in html
    assert 'data-testid="item-row-item_002"' in html
    assert 'data-testid="item-row-item_003"' in html
    assert "window.__mockMerchant.getSnapshot" in html
    assert "window.__mockMerchant.setScenario" in html


def test_mock_merchant_route_serves_page(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    response = client.get("/mock/merchant")

    assert response.status_code == 200
    assert "Mock 商家后台" in response.text
    assert 'data-testid="save-phone-button"' in response.text
