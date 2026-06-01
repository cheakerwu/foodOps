from pathlib import Path

from fastapi.testclient import TestClient

from food_ops_demo.app import create_app


def test_static_page_contains_core_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'id="instructionInput"' in html
    assert 'id="parseButton"' in html
    assert 'id="confirmButton"' in html
    assert 'id="timeline"' in html
    assert "模拟登录失效" in html


def test_root_serves_static_page(tmp_path):
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))

    response = client.get("/")

    assert response.status_code == 200
    assert "外卖运营 Agent 工作台" in response.text
