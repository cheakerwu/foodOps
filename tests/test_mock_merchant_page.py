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


def test_mock_merchant_route_includes_current_database_snapshot(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post(
        "/api/demo/parse",
        json={
            "text": "\u628a\u4eba\u6c11\u5e7f\u573a\u5e97\u7684\u62db\u724c\u725b\u8089\u996d\u6539\u6210 1000",
            "adapter_mode": "fake",
        },
    ).json()
    task = client.post(
        "/api/demo/tasks",
        json={"plan": parsed["plan"], "preview": parsed["preview"], "adapter_mode": "fake"},
    ).json()
    client.post(f"/api/demo/tasks/{task['task_id']}/confirm")

    response = client.get("/mock/merchant")

    assert response.status_code == 200
    assert '"price":1000.0' in response.text
