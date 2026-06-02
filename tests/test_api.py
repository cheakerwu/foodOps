import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from food_ops_demo.app import create_app


def test_importing_app_module_does_not_create_default_database(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import food_ops_demo.app; "
            "from pathlib import Path; "
            "raise SystemExit(1 if Path('data/demo/demo.sqlite3').exists() else 0)",
        ],
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert completed.returncode == 0


def test_health_and_snapshot(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    health = client.get("/health")
    snapshot = client.get("/api/demo/snapshot")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert snapshot.status_code == 200
    assert snapshot.json()["store_name"] == "人民广场店"


def test_parse_create_confirm_task_flow(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的招牌牛肉饭改成 29.9"})
    parsed_body = parsed.json()
    created = client.post(
        "/api/demo/tasks",
        json={"plan": parsed_body["plan"], "preview": parsed_body["preview"]},
    )
    confirmed = client.post(f"/api/demo/tasks/{created.json()['task_id']}/confirm")
    snapshot = client.get("/api/demo/snapshot").json()

    assert parsed.status_code == 200
    assert parsed_body["plan"]["operation_type"] == "menu.update_price"
    assert parsed_body["preview"]["current_price"] == "32.00"
    assert created.status_code == 200
    assert created.json()["state"] == "awaiting_approval"
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "succeeded"
    assert snapshot["items"][0]["price"] == "29.90"


def test_task_list_endpoint_returns_recent_tasks(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的可乐下架"}).json()
    created = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()
    response = client.get("/api/demo/tasks")
    assert response.status_code == 200
    assert response.json()["items"][0]["task_id"] == created["task_id"]


def test_reset_demo_data_restores_snapshot(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的招牌牛肉饭改成 29.9"}).json()
    created = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()
    confirmed = client.post(f"/api/demo/tasks/{created['task_id']}/confirm")

    reset = client.post("/api/demo/reset")
    snapshot = client.get("/api/demo/snapshot")

    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "succeeded"
    assert reset.status_code == 200
    assert reset.json() == {"status": "reset"}
    assert snapshot.status_code == 200
    assert snapshot.json()["items"][0]["price"] == "32.00"


def test_invalid_parse_returns_structured_error(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    response = client.post("/api/demo/parse", json={"text": "把人民广场店的不存在的菜改成 29.9"})

    assert response.status_code == 200
    assert response.json()["plan"] is None
    assert response.json()["errors"][0]["code"] == "target_not_found"


def test_manual_intervention_routes_resume_task(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的可乐下架"}).json()
    task = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()

    manual = client.post(f"/api/demo/tasks/{task['task_id']}/simulate-intervention", json={"type": "login_expired"})
    resumed = client.post(f"/api/demo/tasks/{task['task_id']}/resume")

    assert manual.status_code == 200
    assert manual.json()["state"] == "manual_required"
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "succeeded"
    assert resumed.json()["manual_intervention_type"] == "login_expired"


def test_audit_endpoint_returns_recent_records(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的招牌牛肉饭改成 29.9"}).json()
    task = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()
    client.post(f"/api/demo/tasks/{task['task_id']}/confirm")

    audit = client.get("/api/demo/audit")

    assert audit.status_code == 200
    assert audit.json()["items"][0]["task_id"] == task["task_id"]


def test_parse_and_create_task_accept_adapter_mode(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    parsed = client.post(
        "/api/demo/parse",
        json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "fake"},
    ).json()
    created = client.post(
        "/api/demo/tasks",
        json={"plan": parsed["plan"], "preview": parsed["preview"], "adapter_mode": "fake"},
    ).json()

    assert created["adapter_mode"] == "fake"


@pytest.mark.xfail(
    reason="Playwright sync API uses greenlet which cannot cross thread boundaries "
    "in FastAPI TestClient. Covered by test_shadow_adapter.py directly.",
    strict=False,
)
def test_shadow_mode_parse_create_confirm_flow(tmp_path):
    shadow_url = Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri()
    client = TestClient(
        create_app(
            database_path=tmp_path / "demo.sqlite3",
            audit_path=tmp_path / "audit.jsonl",
            mock_web_url=shadow_url,
            shadow_url=shadow_url,
            shadow_screenshot_dir=tmp_path / "shadow-evidence",
        )
    )

    parsed = client.post(
        "/api/demo/parse",
        json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "shadow"},
    ).json()
    created = client.post(
        "/api/demo/tasks",
        json={"plan": parsed["plan"], "preview": parsed["preview"], "adapter_mode": "shadow"},
    ).json()
    confirmed = client.post(f"/api/demo/tasks/{created['task_id']}/confirm").json()

    assert parsed["errors"] == []
    assert parsed["preview"]["current_price"] == "32.00"
    assert created["adapter_mode"] == "shadow"
    assert confirmed["state"] == "pending_review"
    assert confirmed["result"]["submitted"] is False
    assert confirmed["result"]["shadow_mode"] is True
    assert confirmed["shadow_evidence"]["intended_value"] == "29.90"
    assert (tmp_path / "shadow-evidence" / "shadow-prefill-price.png").exists()


def test_parse_rejects_unknown_adapter_mode_without_throwing(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    response = client.post(
        "/api/demo/parse",
        json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "missing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] is None
    assert body["errors"][0]["code"] == "adapter_mode_not_found"
