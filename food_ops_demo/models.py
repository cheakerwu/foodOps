from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ErrorDetail(BaseModel):
    code: str
    message: str


class OperationPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("plan"))
    instruction: str
    operation_type: str
    store_name: str
    target_name: str | None = None
    changes: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "unknown"
    requires_approval: bool = False
    created_at: str = Field(default_factory=utc_now_iso)


class ParseResult(BaseModel):
    plan: OperationPlan | None = None
    errors: list[ErrorDetail] = Field(default_factory=list)


class MenuItem(BaseModel):
    item_id: str
    store_id: str
    name: str
    price: str
    sale_status: str
    image: str


class StoreSnapshot(BaseModel):
    store_id: str
    store_name: str
    phone: str
    business_hours: list[dict[str, str]]
    items: list[MenuItem]


class OperationResult(BaseModel):
    success: bool
    error: ErrorDetail | None = None


class ValidationResult(BaseModel):
    plan: OperationPlan | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorDetail] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    state: str
    message: str
    error_code: str | None = None
    timestamp: str = Field(default_factory=utc_now_iso)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    instruction: str
    plan: OperationPlan
    adapter_mode: str = "fake"
    state: str = "created"
    preview: dict[str, Any] = Field(default_factory=dict)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    before_snapshot: dict[str, Any] = Field(default_factory=dict)
    after_snapshot: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None
    manual_intervention_type: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
