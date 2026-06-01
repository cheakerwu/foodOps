from fastapi.testclient import TestClient

from food_ops_demo.app import create_app


def test_health_and_snapshot(tmp_path):
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))

    health = client.get("/health")
    snapshot = client.get("/api/demo/snapshot")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert snapshot.status_code == 200
    assert snapshot.json()["store_name"] == "人民广场店"


def test_parse_create_confirm_task_flow(tmp_path):
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))

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


def test_invalid_parse_returns_structured_error(tmp_path):
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))

    response = client.post("/api/demo/parse", json={"text": "把人民广场店的不存在的菜改成 29.9"})

    assert response.status_code == 200
    assert response.json()["plan"] is None
    assert response.json()["errors"][0]["code"] == "target_not_found"


def test_manual_intervention_routes_resume_task(tmp_path):
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))
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
    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的招牌牛肉饭改成 29.9"}).json()
    task = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()
    client.post(f"/api/demo/tasks/{task['task_id']}/confirm")

    audit = client.get("/api/demo/audit")

    assert audit.status_code == 200
    assert audit.json()["items"][0]["task_id"] == task["task_id"]

