from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationPlan
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


DEFAULT_STORE_NAME = "人民广场店"


class ParseRequest(BaseModel):
    text: str


class CreateTaskRequest(BaseModel):
    plan: OperationPlan
    preview: dict[str, Any] = Field(default_factory=dict)


class InterventionRequest(BaseModel):
    type: str


def create_app(audit_path: str | Path | None = None, database_path: str | Path | None = None) -> FastAPI:
    database = DemoDatabase(database_path or os.getenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3"))
    adapter = FakePlatformAdapter(database=database)
    audit_log = AuditLog(audit_path or os.getenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl"))
    manager = TaskManager(adapter=adapter, audit_log=audit_log, database=database)
    static_page = Path(__file__).parent / "static" / "index.html"

    app = FastAPI(title="Food Ops Agent MVP")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static_page.read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/demo/snapshot")
    def snapshot() -> dict[str, Any]:
        return adapter.get_snapshot(DEFAULT_STORE_NAME).model_dump(mode="json")

    @app.post("/api/demo/parse")
    def parse(payload: ParseRequest) -> dict[str, Any]:
        parsed = parse_instruction(payload.text)
        if parsed.errors or parsed.plan is None:
            return {"plan": None, "preview": {}, "errors": [error.model_dump(mode="json") for error in parsed.errors]}

        validated = validate_plan(parsed.plan, adapter)
        return {
            "plan": validated.plan.model_dump(mode="json") if validated.plan else None,
            "preview": validated.preview,
            "errors": [error.model_dump(mode="json") for error in validated.errors],
        }

    @app.post("/api/demo/tasks")
    def create_task(payload: CreateTaskRequest) -> dict[str, Any]:
        task = manager.create_task(payload.plan, payload.preview)
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


app = create_app()
