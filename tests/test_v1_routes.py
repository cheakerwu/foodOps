from fastapi.testclient import TestClient

from food_ops_demo.app import create_app
from food_ops_demo.config import FoodOpsSettings


def _client(tmp_path):
    settings = FoodOpsSettings.from_env()
    settings = FoodOpsSettings(
        **{
            **settings.__dict__,
            "database_path": tmp_path / "food_ops.sqlite3",
            "audit_path": tmp_path / "audit.jsonl",
        }
    )
    return TestClient(create_app(settings=settings))


def test_v1_health_route(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_v1_parse_create_confirm_price_task(tmp_path):
    client = _client(tmp_path)
    parsed = client.post(
        "/api/v1/operations/parse",
        json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "fake"},
    ).json()
    created = client.post(
        "/api/v1/tasks",
        json={"plan": parsed["plan"], "preview": parsed["preview"], "adapter_mode": "fake"},
    ).json()
    confirmed = client.post(f"/api/v1/tasks/{created['task_id']}/confirm").json()

    assert parsed["errors"] == []
    assert created["state"] == "awaiting_approval"
    assert confirmed["state"] == "succeeded"
    assert confirmed["result"]["verified"] is True


def test_demo_routes_remain_compatible(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/demo/snapshot")

    assert response.status_code == 200
    assert response.json()["store_name"] == "人民广场店"
