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


def test_static_page_contains_reset_and_task_center():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'id="resetButton"' in html
    assert 'id="taskList"' in html
    assert "任务中心" in html


def test_static_page_contains_adapter_mode_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'id="adapterMode"' in html
    assert 'value="fake"' in html
    assert 'value="mock_web"' in html
    assert "FakeAdapter" in html
    assert "MockWebAdapter" in html


def test_static_page_contains_shadow_mode_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'value="shadow"' in html
    assert "ShadowMode" in html
    assert "开始预填" in html
    assert "pending_review" in html
    assert "未提交" in html


def test_static_page_contains_browser_use_mode_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'value="browser_use"' in html
    assert "BrowserUseAdapter 实验模式" in html
    assert "浏览器" in html or "Browser Use Agent" in html
    assert "不如 MockWebAdapter 稳定" in html
    assert 'id="browserUseWarning"' in html
    assert 'id="evidenceSection"' in html
    assert 'id="evidence"' in html
    assert "最终 URL" in html or "final_url" in html
    assert "观测值" in html or "observed_value" in html
    assert "截图路径" in html or "screenshot_paths" in html
    assert "证据文本" in html or "evidence_text" in html


def test_root_serves_static_page(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    response = client.get("/")

    assert response.status_code == 200
    assert "外卖运营 Agent 工作台" in response.text
