from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def live_app(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["FOOD_OPS_DATABASE_PATH"] = str(tmp_path / "demo.sqlite3")
    env["FOOD_OPS_AUDIT_PATH"] = str(tmp_path / "audit.jsonl")
    env["FOOD_OPS_MOCK_WEB_URL"] = f"{base_url}/mock/merchant"
    env["FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR"] = str(tmp_path / "mock-web-screenshots")
    env["FOOD_OPS_MOCK_WEB_HEADLESS"] = "1"
    env["FOOD_OPS_SHADOW_URL"] = f"{base_url}/mock/merchant"
    env["FOOD_OPS_SHADOW_SCREENSHOT_DIR"] = str(tmp_path / "shadow-mode-evidence")
    env["FOOD_OPS_SHADOW_HEADLESS"] = "1"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "food_ops_demo.asgi:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{base_url}/health", timeout=1)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(f"server did not start\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _create_task(client: httpx.Client, text: str, adapter_mode: str) -> dict:
    parsed = client.post(
        "/api/demo/parse",
        json={"text": text, "adapter_mode": adapter_mode},
    )
    assert parsed.status_code == 200, parsed.text
    parsed_body = parsed.json()
    assert parsed_body["errors"] == []
    created = client.post(
        "/api/demo/tasks",
        json={
            "plan": parsed_body["plan"],
            "preview": parsed_body["preview"],
            "adapter_mode": adapter_mode,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()


def test_shadow_then_mock_web_parse_does_not_reuse_bad_playwright_lifecycle(live_app: str):
    with httpx.Client(base_url=live_app, timeout=30) as client:
        client.post("/api/demo/reset")
        shadow_task = _create_task(client, "把人民广场店的招牌牛肉饭改成 29.9", "shadow")
        shadow_result = client.post(f"/api/demo/tasks/{shadow_task['task_id']}/confirm")
        assert shadow_result.status_code == 200, shadow_result.text
        assert shadow_result.json()["state"] == "pending_review"

        mock_parse = client.post(
            "/api/demo/parse",
            json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "mock_web"},
        )
        assert mock_parse.status_code == 200, mock_parse.text
        assert mock_parse.json()["errors"] == []
        assert mock_parse.json()["plan"]["operation_type"] == "menu.update_price"
