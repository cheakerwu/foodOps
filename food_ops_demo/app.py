from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.browser_use_adapter import BrowserUseAdapter
from food_ops_demo.mock_web_adapter import MockWebAdapter
from food_ops_demo.shadow_adapter import ShadowPlatformAdapter
from food_ops_demo.models import OperationPlan
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


DEFAULT_STORE_NAME = "人民广场店"


class ParseRequest(BaseModel):
    text: str
    adapter_mode: str = "fake"


class CreateTaskRequest(BaseModel):
    plan: OperationPlan
    preview: dict[str, Any] = Field(default_factory=dict)
    adapter_mode: str = "fake"


class InterventionRequest(BaseModel):
    type: str


def create_app(
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
    shadow_url: str | None = None,
    shadow_screenshot_dir: str | Path | None = None,
    browser_use_url: str | None = None,
    browser_use_screenshot_dir: str | Path | None = None,
    browser_use_max_steps: int | None = None,
) -> FastAPI:
    database = DemoDatabase(database_path or os.getenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3"))
    fake_adapter = FakePlatformAdapter(database=database)
    mock_url = mock_web_url or os.getenv("FOOD_OPS_MOCK_WEB_URL", "http://127.0.0.1:8765/mock/merchant")
    shadow_target_url = shadow_url or os.getenv("FOOD_OPS_SHADOW_URL") or mock_url
    shadow_evidence_dir = (
        shadow_screenshot_dir
        or os.getenv("FOOD_OPS_SHADOW_SCREENSHOT_DIR")
        or "data/demo/shadow-mode-evidence"
    )
    browser_use_target_url = browser_use_url or os.getenv(
        "FOOD_OPS_BROWSER_USE_URL", "http://127.0.0.1:8765/mock/merchant"
    )
    browser_use_ss_dir = (
        browser_use_screenshot_dir
        or os.getenv("FOOD_OPS_BROWSER_USE_SCREENSHOT_DIR")
        or "data/demo/browser-use-screenshots"
    )
    browser_use_steps = browser_use_max_steps or int(os.getenv("FOOD_OPS_BROWSER_USE_MAX_STEPS", "25"))
    adapter_registry = AdapterRegistry(
        {
            "fake": lambda: fake_adapter,
            "mock_web": lambda: MockWebAdapter(
                page_url=mock_url,
                screenshot_dir=os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", "data/demo/mock-web-screenshots"),
                headless=os.getenv("FOOD_OPS_MOCK_WEB_HEADLESS", "1") != "0",
                database=database,
            ),
            "shadow": lambda: ShadowPlatformAdapter(
                page_url=shadow_target_url,
                screenshot_dir=shadow_evidence_dir,
                headless=os.getenv("FOOD_OPS_SHADOW_HEADLESS", "1") != "0",
            ),
            "browser_use": lambda: BrowserUseAdapter(
                page_url=browser_use_target_url,
                screenshot_dir=browser_use_ss_dir,
                max_steps=browser_use_steps,
            ),
        },
        shared_modes={"fake"},
    )
    audit_log = AuditLog(audit_path or os.getenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl"))
    manager = TaskManager(
        adapter=fake_adapter,
        adapter_registry=adapter_registry,
        default_adapter_mode="fake",
        audit_log=audit_log,
        database=database,
    )
    static_page = Path(__file__).parent / "static" / "index.html"

    app = FastAPI(title="Food Ops Agent MVP")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static_page.read_text(encoding="utf-8")

    mock_merchant_page = Path(__file__).parent / "static" / "mock_merchant.html"

    @app.get("/mock/merchant", response_class=HTMLResponse)
    def mock_merchant() -> str:
        html = mock_merchant_page.read_text(encoding="utf-8")
        state = _mock_state_from_snapshot(fake_adapter.get_snapshot(DEFAULT_STORE_NAME))
        return _inject_mock_state(html, state)

    @app.get("/api/mock/merchant/snapshot")
    def mock_merchant_snapshot() -> dict[str, Any]:
        return _mock_state_from_snapshot(fake_adapter.get_snapshot(DEFAULT_STORE_NAME))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/demo/snapshot")
    def snapshot() -> dict[str, Any]:
        return fake_adapter.get_snapshot(DEFAULT_STORE_NAME).model_dump(mode="json")

    @app.post("/api/demo/reset")
    def reset_demo() -> dict[str, str]:
        database.reset_demo_data()
        return {"status": "reset"}

    @app.post("/api/demo/parse")
    def parse(payload: ParseRequest) -> dict[str, Any]:
        with adapter_registry.use(payload.adapter_mode) as selected_adapter:
            if selected_adapter is None:
                return {
                    "plan": None,
                    "preview": {},
                    "errors": [
                        {"code": "adapter_mode_not_found", "message": f"找不到执行模式：{payload.adapter_mode}"}
                    ],
                }
            parsed = parse_instruction(payload.text)
            if parsed.errors or parsed.plan is None:
                return {
                    "plan": None,
                    "preview": {},
                    "errors": [error.model_dump(mode="json") for error in parsed.errors],
                }

            validated = validate_plan(parsed.plan, selected_adapter)
            return {
                "plan": validated.plan.model_dump(mode="json") if validated.plan else None,
                "preview": validated.preview,
                "errors": [error.model_dump(mode="json") for error in validated.errors],
            }

    @app.post("/api/demo/tasks")
    def create_task(payload: CreateTaskRequest) -> dict[str, Any]:
        task = manager.create_task(payload.plan, payload.preview, adapter_mode=payload.adapter_mode)
        return task.model_dump(mode="json")

    @app.get("/api/demo/tasks")
    def list_tasks() -> dict[str, Any]:
        return {"items": [task.model_dump(mode="json") for task in manager.list_tasks()]}

    @app.get("/api/demo/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @app.post("/api/demo/tasks/{task_id}/confirm")
    def confirm_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.confirm_task(task_id))

    @app.post("/api/demo/tasks/{task_id}/simulate-intervention")
    def simulate_intervention(task_id: str, payload: InterventionRequest) -> dict[str, Any]:
        return _task_response(manager.simulate_intervention(task_id, payload.type))

    @app.post("/api/demo/tasks/{task_id}/resume")
    def resume_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.resume_task(task_id))

    @app.post("/api/demo/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.cancel_task(task_id))

    @app.get("/api/demo/audit")
    def audit() -> dict[str, Any]:
        return {"items": audit_log.recent()}

    return app


def _task_response(task) -> dict[str, Any]:
    return task.model_dump(mode="json")


def _inject_mock_state(html: str, state: dict[str, Any]) -> str:
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    script = f"<script>window.__MOCK_MERCHANT_INITIAL_STATE__={state_json};</script>"
    return html.replace("<head>", f"<head>\n  {script}", 1)


def _mock_state_from_snapshot(snapshot) -> dict[str, Any]:
    return {
        "storeId": snapshot.store_id,
        "storeName": snapshot.store_name,
        "phone": snapshot.phone,
        "businessHours": snapshot.business_hours,
        "items": {
            item.item_id: {
                "name": item.name,
                "price": float(item.price),
                "saleStatus": item.sale_status,
            }
            for item in snapshot.items
        },
        "scenario": None,
    }
