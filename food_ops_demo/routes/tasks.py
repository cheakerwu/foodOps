from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from food_ops_demo.dependencies import AppServices
from food_ops_demo.models import OperationPlan
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan

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


def _task_response(task) -> dict[str, Any]:
    return task.model_dump(mode="json")


def build_router(services: AppServices) -> APIRouter:
    router = APIRouter()
    manager = services.task_manager
    database = services.database
    fake_adapter = services.fake_adapter
    adapter_registry = services.adapter_registry
    audit_log = services.audit_log

    @router.get("/snapshot")
    def snapshot() -> dict[str, Any]:
        return fake_adapter.get_snapshot(DEFAULT_STORE_NAME).model_dump(mode="json")

    @router.post("/reset")
    def reset_demo() -> dict[str, str]:
        database.reset_demo_data()
        return {"status": "reset"}

    @router.post("/operations/parse")
    def parse_operation(payload: ParseRequest) -> dict[str, Any]:
        return _do_parse(payload, adapter_registry)

    @router.post("/parse")
    def parse(payload: ParseRequest) -> dict[str, Any]:
        return _do_parse(payload, adapter_registry)

    @router.post("/tasks")
    def create_task(payload: CreateTaskRequest) -> dict[str, Any]:
        task = manager.create_task(payload.plan, payload.preview, adapter_mode=payload.adapter_mode)
        return task.model_dump(mode="json")

    @router.get("/tasks")
    def list_tasks() -> dict[str, Any]:
        return {"items": [task.model_dump(mode="json") for task in manager.list_tasks()]}

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @router.post("/tasks/{task_id}/confirm")
    def confirm_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.confirm_task(task_id))

    @router.post("/tasks/{task_id}/simulate-intervention")
    def simulate_intervention(task_id: str, payload: InterventionRequest) -> dict[str, Any]:
        return _task_response(manager.simulate_intervention(task_id, payload.type))

    @router.post("/tasks/{task_id}/resume")
    def resume_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.resume_task(task_id))

    @router.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, Any]:
        return _task_response(manager.cancel_task(task_id))

    @router.get("/audit")
    def audit() -> dict[str, Any]:
        return {"items": audit_log.recent()}

    return router


def _do_parse(payload: ParseRequest, adapter_registry) -> dict[str, Any]:
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
