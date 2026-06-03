# Food Ops V1 Formalization And BrowserUse Real Platform Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the completed Phase 5 codebase from a local demo shape into a formal V1 validation build that is ready for controlled real-platform adapter testing.

**Architecture:** Keep FastAPI as the control plane for parsing, validation, approvals, task creation, and status reads; move browser execution toward runner-owned scoped jobs with explicit evidence and lifecycle handling. Split configuration, dependency assembly, routes, repositories, and adapter code into clearer boundaries while keeping current behavior compatible. Promote `browser_use` from an experimental UI option into a real-platform adapter path with capability declarations, structured snapshot extraction, deterministic evidence, environment validation, and safe session cleanup.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, sqlite3, pytest, httpx, Uvicorn, Playwright sync API for mock/shadow paths, browser-use for AI-driven browser automation, vanilla HTML/CSS/JS, CodeGraph.

---

## Current Baseline

Current branch baseline before this plan:

```text
main...origin/main
163 passed, 1 xpassed, 1 warning in 28.39s
```

The warning to eliminate before V1 acceptance:

```text
RuntimeWarning: coroutine 'BrowserSession.close' was never awaited
food_ops_demo/browser_use_adapter.py:55
```

Current Phase 5 browser-use integration appears as:

- `pyproject.toml`: optional dependency extra `browser_use = ["browser-use>=0.1.0"]`.
- `food_ops_demo/browser_use_adapter.py`: `BrowserUseAdapter` wraps `browser_use.Agent`, `Browser`, and `ChatBrowserUse`.
- `food_ops_demo/app.py`: registers adapter mode `"browser_use"`.
- `food_ops_demo/static/index.html`: exposes the `BrowserUseAdapter 实验模式` selector option and evidence display.
- `food_ops_demo/models.py`: includes `BrowserUseExecutionEvidence` and `OperationResult.screenshot_paths`.
- `tests/test_browser_use_adapter.py`, `tests/test_workflow_browser_use_mode.py`, and `tests/test_browser_use_evidence_models.py`: cover mocked adapter behavior, workflow routing, lifecycle, and audit evidence.

No `browser-use-main/` source tree is vendored in this repository. V1 should continue using `browser-use` as a package dependency unless a later architecture decision explicitly vendors or forks it.

---

## File Structure

Create or modify these files in this plan:

- Create `food_ops_demo/config.py`: typed application settings with all environment-variable parsing and defaults.
- Create `tests/test_config.py`: settings defaults, environment overrides, invalid integer validation, and V1 API prefix validation.
- Create `food_ops_demo/constants.py`: adapter modes, task states, operation types, and shared error codes.
- Modify `food_ops_demo/adapter_modes.py`: keep backward-compatible re-exports from `constants.py`.
- Modify `food_ops_demo/app.py`: consume `FoodOpsSettings`, register `/api/v1` routes, keep `/api/demo` compatibility, and remove scattered `os.getenv(...)` reads.
- Create `food_ops_demo/dependencies.py`: assemble database, audit log, adapter registry, and task manager from settings.
- Create `food_ops_demo/routes/__init__.py`: routes package marker.
- Create `food_ops_demo/routes/health.py`: health endpoint.
- Create `food_ops_demo/routes/tasks.py`: parse, task, audit, and snapshot endpoints.
- Create `food_ops_demo/routes/dev_mock.py`: mock merchant HTML and mock merchant snapshot endpoints.
- Create `tests/test_v1_routes.py`: V1 route parity with current `/api/demo` behavior.
- Create `food_ops_demo/repositories.py`: focused repository wrappers around the existing SQLite connection contract.
- Modify `food_ops_demo/storage.py`: keep `DemoDatabase` as a compatibility facade while delegating to repositories.
- Create `tests/test_repositories.py`: repository-level tests for stores, tasks, jobs, and locks.
- Modify `food_ops_demo/browser_use_adapter.py`: fix close lifecycle, add capabilities, structured snapshot extraction, environment validation, and stronger evidence.
- Modify `food_ops_demo/models.py`: add adapter capability and structured browser-use snapshot output models.
- Modify `tests/test_browser_use_adapter.py`: cover async close, capabilities, structured snapshot extraction, validation failures, and evidence fields.
- Modify `tests/test_workflow_browser_use_mode.py`: cover real-platform adapter mode as non-shared scoped execution with evidence.
- Modify `food_ops_demo/runner.py`: make runner update persisted task status and audit evidence for queued jobs.
- Modify `food_ops_demo/workflow.py`: enqueue browser-backed work in V1 mode while keeping current synchronous demo behavior available.
- Create `tests/test_v1_runner_execution.py`: control-plane enqueue and runner-owned execution acceptance.
- Modify `food_ops_demo/static/index.html`: rename BrowserUse label from experimental to real-platform test mode and show capability/evidence status.
- Modify `README.md`: rewrite from MVP/Demo wording to V1 validation build wording.
- Modify `docs/project-structure.md`: document V1 structure, route namespaces, runner boundary, adapter capabilities, and updated verification baseline.
- Modify `.env.example`: add V1 settings and keep compatibility variables.
- Modify `pyproject.toml`: rename project metadata to V1 wording and update package description.

---

## V1 Boundary Decisions

- Keep Python package name `food_ops_demo` for this plan. Renaming the import package would create high churn and does not directly improve real-platform readiness.
- Add `/api/v1/*` while preserving `/api/demo/*` compatibility. This avoids breaking existing tests and local browser workflows.
- Keep mock merchant backend in the same FastAPI service but isolate it under `routes/dev_mock.py` and document it as a development-only backend.
- Keep SQLite for V1 validation. The repository layer should make a later move to Postgres or a hosted task queue straightforward.
- Treat `browser_use` as a real-platform adapter candidate but keep `mock_web` and `shadow` as validation tools.
- Keep sync FastAPI route handlers for control-plane APIs. Browser automation should move toward runner-owned jobs, not long request handlers.

---

## Task 1: Add Typed V1 Settings

**Files:**
- Create: `food_ops_demo/config.py`
- Create: `tests/test_config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_config.py`:

```python
from __future__ import annotations

import pytest

from food_ops_demo.config import FoodOpsSettings


def test_settings_defaults_are_v1_ready(monkeypatch):
    for key in [
        "FOOD_OPS_ENV",
        "FOOD_OPS_API_PREFIX",
        "FOOD_OPS_DATA_DIR",
        "FOOD_OPS_DATABASE_PATH",
        "FOOD_OPS_AUDIT_PATH",
        "FOOD_OPS_BROWSER_USE_MAX_STEPS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = FoodOpsSettings.from_env()

    assert settings.env == "local"
    assert settings.api_prefix == "/api/v1"
    assert settings.data_dir.as_posix() == "data/local"
    assert settings.database_path.as_posix() == "data/local/food_ops.sqlite3"
    assert settings.audit_path.as_posix() == "data/local/audit.jsonl"
    assert settings.browser_use_max_steps == 25
    assert settings.browser_use_url == "http://127.0.0.1:8765/mock/merchant"


def test_settings_accept_legacy_demo_paths(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3")
    monkeypatch.setenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl")

    settings = FoodOpsSettings.from_env()

    assert settings.database_path.as_posix() == "data/demo/demo.sqlite3"
    assert settings.audit_path.as_posix() == "data/demo/audit.jsonl"


def test_settings_reject_invalid_browser_use_steps(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_BROWSER_USE_MAX_STEPS", "many")

    with pytest.raises(ValueError, match="FOOD_OPS_BROWSER_USE_MAX_STEPS must be an integer"):
        FoodOpsSettings.from_env()


def test_settings_reject_api_prefix_without_leading_slash(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_API_PREFIX", "api/v1")

    with pytest.raises(ValueError, match="FOOD_OPS_API_PREFIX must start with '/'"):
        FoodOpsSettings.from_env()
```

- [ ] **Step 2: Run settings tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_config.py -q
```

Expected:

```text
FAILED tests/test_config.py::test_settings_defaults_are_v1_ready
ModuleNotFoundError: No module named 'food_ops_demo.config'
```

- [ ] **Step 3: Implement typed settings**

Create `food_ops_demo/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_bool(name: str, default: str) -> bool:
    return os.getenv(name, default) not in {"0", "false", "False", "no", "NO"}


def _get_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class FoodOpsSettings:
    env: str
    api_prefix: str
    data_dir: Path
    database_path: Path
    audit_path: Path
    mock_web_url: str
    mock_web_screenshot_dir: Path
    mock_web_headless: bool
    shadow_url: str
    shadow_screenshot_dir: Path
    shadow_headless: bool
    browser_use_url: str
    browser_use_screenshot_dir: Path
    browser_use_max_steps: int
    browser_use_required_api_key: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "FoodOpsSettings":
        data_dir = Path(os.getenv("FOOD_OPS_DATA_DIR", "data/local"))
        api_prefix = os.getenv("FOOD_OPS_API_PREFIX", "/api/v1")
        if not api_prefix.startswith("/"):
            raise ValueError("FOOD_OPS_API_PREFIX must start with '/'")

        mock_url = os.getenv("FOOD_OPS_MOCK_WEB_URL", "http://127.0.0.1:8765/mock/merchant")
        return cls(
            env=os.getenv("FOOD_OPS_ENV", "local"),
            api_prefix=api_prefix.rstrip("/"),
            data_dir=data_dir,
            database_path=Path(os.getenv("FOOD_OPS_DATABASE_PATH", str(data_dir / "food_ops.sqlite3"))),
            audit_path=Path(os.getenv("FOOD_OPS_AUDIT_PATH", str(data_dir / "audit.jsonl"))),
            mock_web_url=mock_url,
            mock_web_screenshot_dir=Path(
                os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", str(data_dir / "mock-web-screenshots"))
            ),
            mock_web_headless=_get_bool("FOOD_OPS_MOCK_WEB_HEADLESS", "1"),
            shadow_url=os.getenv("FOOD_OPS_SHADOW_URL", mock_url),
            shadow_screenshot_dir=Path(
                os.getenv("FOOD_OPS_SHADOW_SCREENSHOT_DIR", str(data_dir / "shadow-mode-evidence"))
            ),
            shadow_headless=_get_bool("FOOD_OPS_SHADOW_HEADLESS", "1"),
            browser_use_url=os.getenv("FOOD_OPS_BROWSER_USE_URL", mock_url),
            browser_use_screenshot_dir=Path(
                os.getenv("FOOD_OPS_BROWSER_USE_SCREENSHOT_DIR", str(data_dir / "browser-use-screenshots"))
            ),
            browser_use_max_steps=_get_int("FOOD_OPS_BROWSER_USE_MAX_STEPS", "25"),
            browser_use_required_api_key=_get_bool("FOOD_OPS_BROWSER_USE_REQUIRE_API_KEY", "0"),
            log_level=os.getenv("FOOD_OPS_LOG_LEVEL", "INFO"),
        )
```

- [ ] **Step 4: Update `.env.example`**

Replace `.env.example` with:

```env
FOOD_OPS_ENV=local
FOOD_OPS_API_PREFIX=/api/v1
FOOD_OPS_DATA_DIR=data/local
FOOD_OPS_DATABASE_PATH=data/local/food_ops.sqlite3
FOOD_OPS_AUDIT_PATH=data/local/audit.jsonl
FOOD_OPS_LOG_LEVEL=INFO

FOOD_OPS_MOCK_WEB_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR=data/local/mock-web-screenshots
FOOD_OPS_MOCK_WEB_HEADLESS=1

FOOD_OPS_SHADOW_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_SHADOW_SCREENSHOT_DIR=data/local/shadow-mode-evidence
FOOD_OPS_SHADOW_HEADLESS=1

FOOD_OPS_BROWSER_USE_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_BROWSER_USE_SCREENSHOT_DIR=data/local/browser-use-screenshots
FOOD_OPS_BROWSER_USE_MAX_STEPS=25
FOOD_OPS_BROWSER_USE_REQUIRE_API_KEY=0
# BROWSER_USE_API_KEY=your-api-key-here
```

- [ ] **Step 5: Run settings tests to verify they pass**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_config.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit**

```powershell
git add food_ops_demo/config.py tests/test_config.py .env.example
git commit -m "feat: add v1 settings"
```

---

## Task 2: Centralize Constants And Compatibility Re-exports

**Files:**
- Create: `food_ops_demo/constants.py`
- Modify: `food_ops_demo/adapter_modes.py`
- Modify: `tests/test_static_page.py`
- Create: `tests/test_constants.py`

- [ ] **Step 1: Write failing constants tests**

Create `tests/test_constants.py`:

```python
from food_ops_demo.constants import AdapterMode, ErrorCode, OperationType, TaskState


def test_adapter_modes_match_route_payload_values():
    assert AdapterMode.FAKE == "fake"
    assert AdapterMode.MOCK_WEB == "mock_web"
    assert AdapterMode.SHADOW == "shadow"
    assert AdapterMode.BROWSER_USE == "browser_use"


def test_task_state_values_match_existing_timeline_values():
    assert TaskState.AWAITING_APPROVAL == "awaiting_approval"
    assert TaskState.PENDING_REVIEW == "pending_review"
    assert TaskState.SUCCEEDED == "succeeded"
    assert TaskState.FAILED == "failed"


def test_operation_type_values_match_operation_plan_payloads():
    assert OperationType.UPDATE_PRICE == "menu.update_price"
    assert OperationType.UPDATE_SALE_STATUS == "menu.update_sale_status"
    assert OperationType.UPDATE_BUSINESS_HOURS == "store.update_business_hours"
    assert OperationType.UPDATE_PHONE == "store.update_phone"


def test_error_code_values_match_existing_api_contracts():
    assert ErrorCode.ADAPTER_MODE_NOT_FOUND == "adapter_mode_not_found"
    assert ErrorCode.AUTH_REQUIRED == "auth_required"
    assert ErrorCode.VERIFICATION_FAILED == "verification_failed"
    assert ErrorCode.BROWSER_USE_AGENT_FAILED == "browser_use_agent_failed"
```

- [ ] **Step 2: Run constants tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_constants.py -q
```

Expected:

```text
FAILED tests/test_constants.py::test_adapter_modes_match_route_payload_values
ModuleNotFoundError: No module named 'food_ops_demo.constants'
```

- [ ] **Step 3: Implement constants**

Create `food_ops_demo/constants.py`:

```python
from __future__ import annotations


class AdapterMode:
    FAKE = "fake"
    MOCK_WEB = "mock_web"
    SHADOW = "shadow"
    BROWSER_USE = "browser_use"


class TaskState:
    CREATED = "created"
    PARSED = "parsed"
    VALIDATED = "validated"
    PREVIEWED = "previewed"
    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    SESSION_READY = "session_ready"
    PRE_SNAPSHOT_DONE = "pre_snapshot_done"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SHADOW_PREFILLED = "shadow_prefilled"
    PENDING_REVIEW = "pending_review"
    MANUAL_REQUIRED = "manual_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationType:
    UPDATE_PRICE = "menu.update_price"
    UPDATE_SALE_STATUS = "menu.update_sale_status"
    UPDATE_BUSINESS_HOURS = "store.update_business_hours"
    UPDATE_PHONE = "store.update_phone"


class ErrorCode:
    ADAPTER_MODE_NOT_FOUND = "adapter_mode_not_found"
    AUTH_REQUIRED = "auth_required"
    TARGET_NOT_FOUND = "target_not_found"
    STORE_NOT_FOUND = "store_not_found"
    INVALID_STATE = "invalid_state"
    VERIFICATION_FAILED = "verification_failed"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    BROWSER_USE_AGENT_FAILED = "browser_use_agent_failed"
    BROWSER_USE_STRUCTURED_OUTPUT_INVALID = "browser_use_structured_output_invalid"
    BROWSER_USE_VERIFICATION_FAILED = "browser_use_verification_failed"
    BROWSER_USE_UNSUPPORTED_OPERATION = "browser_use_unsupported_operation"
    BROWSER_USE_CONFIGURATION_ERROR = "browser_use_configuration_error"
```

- [ ] **Step 4: Keep adapter mode compatibility exports**

Replace `food_ops_demo/adapter_modes.py` with:

```python
"""Backward-compatible adapter mode constants."""

from food_ops_demo.constants import AdapterMode

FAKE_ADAPTER_MODE = AdapterMode.FAKE
MOCK_WEB_ADAPTER_MODE = AdapterMode.MOCK_WEB
BROWSER_USE_ADAPTER_MODE = AdapterMode.BROWSER_USE
SHADOW_ADAPTER_MODE = AdapterMode.SHADOW
```

- [ ] **Step 5: Run constants and adapter mode tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_constants.py tests/test_static_page.py::test_static_page_contains_browser_use_mode_controls -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit**

```powershell
git add food_ops_demo/constants.py food_ops_demo/adapter_modes.py tests/test_constants.py
git commit -m "refactor: centralize v1 constants"
```

---

## Task 3: Split App Assembly And Add `/api/v1` Routes

**Files:**
- Create: `food_ops_demo/dependencies.py`
- Create: `food_ops_demo/routes/__init__.py`
- Create: `food_ops_demo/routes/health.py`
- Create: `food_ops_demo/routes/tasks.py`
- Create: `food_ops_demo/routes/dev_mock.py`
- Modify: `food_ops_demo/app.py`
- Create: `tests/test_v1_routes.py`

- [ ] **Step 1: Write failing V1 route parity tests**

Create `tests/test_v1_routes.py`:

```python
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
```

- [ ] **Step 2: Run V1 route tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_routes.py -q
```

Expected:

```text
FAILED tests/test_v1_routes.py::test_v1_health_route
TypeError: create_app() got an unexpected keyword argument 'settings'
```

- [ ] **Step 3: Create dependency assembly**

Create `food_ops_demo/dependencies.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.browser_use_adapter import BrowserUseAdapter
from food_ops_demo.config import FoodOpsSettings
from food_ops_demo.constants import AdapterMode
from food_ops_demo.mock_web_adapter import MockWebAdapter
from food_ops_demo.shadow_adapter import ShadowPlatformAdapter
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


@dataclass
class AppServices:
    settings: FoodOpsSettings
    database: DemoDatabase
    fake_adapter: FakePlatformAdapter
    adapter_registry: AdapterRegistry
    audit_log: AuditLog
    task_manager: TaskManager


def build_services(settings: FoodOpsSettings) -> AppServices:
    database = DemoDatabase(settings.database_path)
    fake_adapter = FakePlatformAdapter(database=database)
    adapter_registry = AdapterRegistry(
        {
            AdapterMode.FAKE: lambda: fake_adapter,
            AdapterMode.MOCK_WEB: lambda: MockWebAdapter(
                page_url=settings.mock_web_url,
                screenshot_dir=settings.mock_web_screenshot_dir,
                headless=settings.mock_web_headless,
                database=database,
            ),
            AdapterMode.SHADOW: lambda: ShadowPlatformAdapter(
                page_url=settings.shadow_url,
                screenshot_dir=settings.shadow_screenshot_dir,
                headless=settings.shadow_headless,
            ),
            AdapterMode.BROWSER_USE: lambda: BrowserUseAdapter(
                page_url=settings.browser_use_url,
                screenshot_dir=settings.browser_use_screenshot_dir,
                max_steps=settings.browser_use_max_steps,
                require_api_key=settings.browser_use_required_api_key,
            ),
        },
        shared_modes={AdapterMode.FAKE},
    )
    audit_log = AuditLog(settings.audit_path)
    task_manager = TaskManager(
        adapter=fake_adapter,
        adapter_registry=adapter_registry,
        default_adapter_mode=AdapterMode.FAKE,
        audit_log=audit_log,
        database=database,
    )
    return AppServices(
        settings=settings,
        database=database,
        fake_adapter=fake_adapter,
        adapter_registry=adapter_registry,
        audit_log=audit_log,
        task_manager=task_manager,
    )
```

- [ ] **Step 4: Create route modules**

Create `food_ops_demo/routes/__init__.py`:

```python
"""FastAPI route registration modules."""
```

Create `food_ops_demo/routes/health.py`:

```python
from __future__ import annotations

from fastapi import APIRouter


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return router
```

Create `food_ops_demo/routes/tasks.py`:

```python
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from food_ops_demo.dependencies import AppServices
from food_ops_demo.models import OperationPlan
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.storage import SEED_STORE_NAME


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

    @router.get("/snapshot")
    def snapshot() -> dict[str, Any]:
        return services.fake_adapter.get_snapshot(SEED_STORE_NAME).model_dump(mode="json")

    @router.post("/reset")
    def reset_demo() -> dict[str, str]:
        services.database.reset_demo_data()
        return {"status": "reset"}

    @router.post("/operations/parse")
    @router.post("/parse")
    def parse(payload: ParseRequest) -> dict[str, Any]:
        with services.adapter_registry.use(payload.adapter_mode) as selected_adapter:
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

    @router.post("/tasks")
    def create_task(payload: CreateTaskRequest) -> dict[str, Any]:
        task = services.task_manager.create_task(payload.plan, payload.preview, adapter_mode=payload.adapter_mode)
        return task.model_dump(mode="json")

    @router.get("/tasks")
    def list_tasks() -> dict[str, Any]:
        return {"items": [task.model_dump(mode="json") for task in services.task_manager.list_tasks()]}

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = services.task_manager.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.model_dump(mode="json")

    @router.post("/tasks/{task_id}/confirm")
    def confirm_task(task_id: str) -> dict[str, Any]:
        return _task_response(services.task_manager.confirm_task(task_id))

    @router.post("/tasks/{task_id}/simulate-intervention")
    def simulate_intervention(task_id: str, payload: InterventionRequest) -> dict[str, Any]:
        return _task_response(services.task_manager.simulate_intervention(task_id, payload.type))

    @router.post("/tasks/{task_id}/resume")
    def resume_task(task_id: str) -> dict[str, Any]:
        return _task_response(services.task_manager.resume_task(task_id))

    @router.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, Any]:
        return _task_response(services.task_manager.cancel_task(task_id))

    @router.get("/audit")
    def audit() -> dict[str, Any]:
        return {"items": services.audit_log.recent()}

    return router
```

Create `food_ops_demo/routes/dev_mock.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from food_ops_demo.dependencies import AppServices
from food_ops_demo.storage import SEED_STORE_NAME


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


def build_router(services: AppServices, mock_merchant_page: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/mock/merchant", response_class=HTMLResponse)
    def mock_merchant() -> str:
        html = mock_merchant_page.read_text(encoding="utf-8")
        state = _mock_state_from_snapshot(services.fake_adapter.get_snapshot(SEED_STORE_NAME))
        return _inject_mock_state(html, state)

    @router.get("/api/mock/merchant/snapshot")
    def mock_merchant_snapshot() -> dict[str, Any]:
        return _mock_state_from_snapshot(services.fake_adapter.get_snapshot(SEED_STORE_NAME))

    return router
```

- [ ] **Step 5: Refactor `create_app()` to register route modules**

Replace `food_ops_demo/app.py` with:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from food_ops_demo.config import FoodOpsSettings
from food_ops_demo.dependencies import build_services
from food_ops_demo.routes import dev_mock, health, tasks


def create_app(
    *,
    settings: FoodOpsSettings | None = None,
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
    shadow_url: str | None = None,
    shadow_screenshot_dir: str | Path | None = None,
    browser_use_url: str | None = None,
    browser_use_screenshot_dir: str | Path | None = None,
    browser_use_max_steps: int | None = None,
) -> FastAPI:
    base_settings = settings or FoodOpsSettings.from_env()
    if any(
        value is not None
        for value in [
            audit_path,
            database_path,
            mock_web_url,
            shadow_url,
            shadow_screenshot_dir,
            browser_use_url,
            browser_use_screenshot_dir,
            browser_use_max_steps,
        ]
    ):
        base_settings = FoodOpsSettings(
            **{
                **base_settings.__dict__,
                "audit_path": Path(audit_path) if audit_path is not None else base_settings.audit_path,
                "database_path": Path(database_path) if database_path is not None else base_settings.database_path,
                "mock_web_url": mock_web_url or base_settings.mock_web_url,
                "shadow_url": shadow_url or base_settings.shadow_url,
                "shadow_screenshot_dir": Path(shadow_screenshot_dir)
                if shadow_screenshot_dir is not None
                else base_settings.shadow_screenshot_dir,
                "browser_use_url": browser_use_url or base_settings.browser_use_url,
                "browser_use_screenshot_dir": Path(browser_use_screenshot_dir)
                if browser_use_screenshot_dir is not None
                else base_settings.browser_use_screenshot_dir,
                "browser_use_max_steps": browser_use_max_steps or base_settings.browser_use_max_steps,
            }
        )

    services = build_services(base_settings)
    app = FastAPI(title="Food Ops Agent V1")
    static_page = Path(__file__).parent / "static" / "index.html"
    mock_merchant_page = Path(__file__).parent / "static" / "mock_merchant.html"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static_page.read_text(encoding="utf-8")

    app.include_router(health.build_router())
    app.include_router(health.build_router(), prefix=base_settings.api_prefix)
    app.include_router(tasks.build_router(services), prefix=base_settings.api_prefix)
    app.include_router(tasks.build_router(services), prefix="/api/demo")
    app.include_router(dev_mock.build_router(services, mock_merchant_page))
    return app
```

- [ ] **Step 6: Run route tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_routes.py tests/test_api.py tests/test_static_page.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 7: Commit**

```powershell
git add food_ops_demo/app.py food_ops_demo/dependencies.py food_ops_demo/routes tests/test_v1_routes.py
git commit -m "refactor: split v1 app routes and dependencies"
```

---

## Task 4: Add Repository Wrappers Around SQLite Storage

**Files:**
- Create: `food_ops_demo/repositories.py`
- Modify: `food_ops_demo/storage.py`
- Create: `tests/test_repositories.py`

- [ ] **Step 1: Write repository behavior tests**

Create `tests/test_repositories.py`:

```python
from food_ops_demo.models import OperationPlan, Task
from food_ops_demo.repositories import JobQueueRepository, StoreRepository, TaskRepository
from food_ops_demo.storage import DemoDatabase


def _database(tmp_path):
    return DemoDatabase(tmp_path / "food_ops.sqlite3")


def test_store_repository_reads_and_updates_price(tmp_path):
    db = _database(tmp_path)
    stores = StoreRepository(db)

    assert stores.get_snapshot("人民广场店").items[0].price == "32.00"
    assert stores.update_menu_price("人民广场店", "招牌牛肉饭", "29.90") is True
    assert stores.find_menu_items("人民广场店", "招牌牛肉饭")[0].price == "29.90"


def test_task_repository_round_trips_task(tmp_path):
    db = _database(tmp_path)
    tasks = TaskRepository(db)
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
    )
    task = Task(instruction=plan.instruction, plan=plan, preview={})

    tasks.save(task)

    assert tasks.get(task.task_id).task_id == task.task_id
    assert tasks.list(limit=1)[0].task_id == task.task_id


def test_job_queue_repository_serializes_same_lock(tmp_path):
    db = _database(tmp_path)
    jobs = JobQueueRepository(db)
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
    )
    jobs.enqueue(
        batch_id="batch_1",
        task_id="task_1",
        adapter_mode="mock_web",
        platform_account_id="account_1",
        lock_key="account_1:人民广场店",
        plan=plan,
    )
    jobs.enqueue(
        batch_id="batch_1",
        task_id="task_2",
        adapter_mode="mock_web",
        platform_account_id="account_1",
        lock_key="account_1:人民广场店",
        plan=plan,
    )

    first = jobs.acquire_next(worker_id="worker_1", lease_seconds=60)
    second = jobs.acquire_next(worker_id="worker_2", lease_seconds=60)

    assert first is not None
    assert second is None
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_repositories.py -q
```

Expected:

```text
FAILED tests/test_repositories.py::test_store_repository_reads_and_updates_price
ModuleNotFoundError: No module named 'food_ops_demo.repositories'
```

- [ ] **Step 3: Implement repository wrappers**

Create `food_ops_demo/repositories.py`:

```python
from __future__ import annotations

from food_ops_demo.models import OperationPlan, Task
from food_ops_demo.storage import DemoDatabase


class StoreRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def get_snapshot(self, store_name: str):
        return self.database.get_store_snapshot(store_name)

    def find_menu_items(self, store_name: str, item_name: str):
        return self.database.find_menu_items(store_name, item_name)

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> bool:
        return self.database.update_menu_price(store_name, item_name, price)

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> bool:
        return self.database.update_menu_sale_status(store_name, item_name, sale_status)

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> bool:
        return self.database.update_business_hours(store_name, business_hours)

    def update_store_phone(self, store_name: str, phone: str) -> bool:
        return self.database.update_store_phone(store_name, phone)

    def reset_seed_data(self) -> None:
        self.database.reset_demo_data()


class TaskRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def save(self, task: Task) -> None:
        self.database.save_task(task)

    def get(self, task_id: str) -> Task | None:
        return self.database.get_task(task_id)

    def list(self, limit: int = 20) -> list[Task]:
        return self.database.list_tasks(limit=limit)


class JobQueueRepository:
    def __init__(self, database: DemoDatabase) -> None:
        self.database = database

    def enqueue(
        self,
        batch_id: str,
        task_id: str,
        adapter_mode: str,
        platform_account_id: str,
        lock_key: str,
        plan: OperationPlan,
    ) -> str:
        return self.database.enqueue_job(
            batch_id=batch_id,
            task_id=task_id,
            adapter_mode=adapter_mode,
            platform_account_id=platform_account_id,
            lock_key=lock_key,
            plan=plan,
        )

    def acquire_next(self, worker_id: str, lease_seconds: int) -> dict | None:
        return self.database.acquire_next_job(worker_id=worker_id, lease_seconds=lease_seconds)

    def complete(self, job_id: str, state: str, result: dict) -> None:
        self.database.complete_job(job_id=job_id, state=state, result=result)
```

- [ ] **Step 4: Run repository tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_repositories.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add food_ops_demo/repositories.py tests/test_repositories.py
git commit -m "refactor: add sqlite repository boundaries"
```

---

## Task 5: Upgrade BrowserUseAdapter Lifecycle, Capabilities, And Configuration Validation

**Files:**
- Modify: `food_ops_demo/models.py`
- Modify: `food_ops_demo/browser_use_adapter.py`
- Modify: `tests/test_browser_use_adapter.py`

- [ ] **Step 1: Add failing tests for capabilities and async close compatibility**

Append to `tests/test_browser_use_adapter.py`:

```python
import inspect
from unittest.mock import AsyncMock


def test_browser_use_adapter_declares_real_platform_capabilities(adapter):
    capabilities = adapter.capabilities()

    assert capabilities.adapter_mode == "browser_use"
    assert capabilities.real_platform is True
    assert capabilities.supported_operations == ["menu.update_price"]
    assert capabilities.requires_browser_session is True
    assert capabilities.requires_api_key is False


def test_close_runs_async_browser_close_when_needed(tmp_path):
    browser = MagicMock()
    browser.close = AsyncMock()
    adapter = BrowserUseAdapter(
        page_url="https://merchant.example.com",
        browser=browser,
        llm=MagicMock(),
    )
    adapter._owns_browser = True

    adapter.close()

    browser.close.assert_awaited_once()
    assert adapter._browser is None
    assert inspect.iscoroutinefunction(browser.close)


def test_validate_configuration_requires_api_key_when_enabled(monkeypatch, tmp_path):
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    adapter = BrowserUseAdapter(
        page_url="https://merchant.example.com",
        browser=MagicMock(),
        llm=MagicMock(),
        require_api_key=True,
    )

    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    assert result.success is False
    assert result.error.code == "browser_use_configuration_error"
    assert "BROWSER_USE_API_KEY" in result.error.message
```

- [ ] **Step 2: Run BrowserUseAdapter tests to verify failures**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_browser_use_adapter.py::test_browser_use_adapter_declares_real_platform_capabilities tests/test_browser_use_adapter.py::test_close_runs_async_browser_close_when_needed tests/test_browser_use_adapter.py::test_validate_configuration_requires_api_key_when_enabled -q
```

Expected:

```text
FAILED tests/test_browser_use_adapter.py::test_browser_use_adapter_declares_real_platform_capabilities
AttributeError: 'BrowserUseAdapter' object has no attribute 'capabilities'
```

- [ ] **Step 3: Add capability model**

Modify `food_ops_demo/models.py` after `StoreSnapshot`:

```python
class AdapterCapabilities(BaseModel):
    adapter_mode: str
    real_platform: bool = False
    supported_operations: list[str] = Field(default_factory=list)
    requires_browser_session: bool = False
    requires_api_key: bool = False
    supports_shadow_mode: bool = False
```

- [ ] **Step 4: Upgrade BrowserUseAdapter lifecycle and configuration validation**

Modify imports in `food_ops_demo/browser_use_adapter.py`:

```python
import asyncio
import inspect
import os
from pathlib import Path
from typing import Any
```

Add `AdapterCapabilities` import:

```python
from food_ops_demo.models import (
    AdapterCapabilities,
    BrowserUseExecutionEvidence,
    ErrorDetail,
    MenuItem,
    OperationResult,
    StoreSnapshot,
)
```

Extend `__init__`:

```python
    def __init__(
        self,
        page_url: str,
        browser: Any | None = None,
        llm: Any | None = None,
        screenshot_dir: str | Path | None = None,
        max_steps: int = 25,
        require_api_key: bool = False,
    ) -> None:
        self.page_url = page_url
        self._browser = browser
        self._owns_browser = browser is None
        self._llm = llm
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else None
        self._max_steps = max_steps
        self._require_api_key = require_api_key
        self._screenshot_paths: list[str] = []
```

Replace `close()` with:

```python
    def close(self) -> None:
        """Close browser resources if owned by this adapter."""
        if not self._owns_browser or self._browser is None:
            return
        close = getattr(self._browser, "close", None)
        if callable(close):
            try:
                result = close()
                if inspect.isawaitable(result):
                    asyncio.run(result)
            except Exception:  # pragma: no cover -- best-effort cleanup
                pass
        self._browser = None
```

Add methods before `_ensure_llm()`:

```python
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_mode="browser_use",
            real_platform=True,
            supported_operations=["menu.update_price"],
            requires_browser_session=True,
            requires_api_key=self._require_api_key,
            supports_shadow_mode=False,
        )

    def _configuration_error(self) -> OperationResult | None:
        if self._require_api_key and not os.getenv("BROWSER_USE_API_KEY"):
            return OperationResult(
                success=False,
                error=ErrorDetail(
                    code="browser_use_configuration_error",
                    message="BROWSER_USE_API_KEY is required for browser_use mode.",
                ),
            )
        return None
```

At the top of `update_menu_price()`, add:

```python
        config_error = self._configuration_error()
        if config_error is not None:
            return config_error
```

- [ ] **Step 5: Run BrowserUseAdapter tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_browser_use_adapter.py -q
```

Expected:

```text
all BrowserUseAdapter tests pass
```

- [ ] **Step 6: Run full suite and confirm warning is gone**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -q
```

Expected:

```text
all tests pass with no RuntimeWarning about BrowserSession.close
```

- [ ] **Step 7: Commit**

```powershell
git add food_ops_demo/models.py food_ops_demo/browser_use_adapter.py tests/test_browser_use_adapter.py
git commit -m "fix: harden browser_use adapter lifecycle"
```

---

## Task 6: Add Structured BrowserUse Snapshot Extraction

**Files:**
- Modify: `food_ops_demo/browser_use_adapter.py`
- Modify: `tests/test_browser_use_adapter.py`

- [ ] **Step 1: Add failing structured snapshot tests**

Append to `tests/test_browser_use_adapter.py`:

```python
from food_ops_demo.browser_use_adapter import _StoreSnapshotResult


@patch("browser_use.Agent")
def test_get_snapshot_maps_structured_browser_use_output(mock_agent_cls, adapter):
    history = _make_history()
    history.structured_output = _StoreSnapshotResult(
        store_id="store_real_001",
        store_name="人民广场店",
        phone="021-88888888",
        business_hours=[{"start": "09:30", "end": "21:30"}],
        items=[
            {
                "item_id": "remote_item_001",
                "name": "招牌牛肉饭",
                "price": "32.00",
                "sale_status": "on_sale",
                "image": "",
            }
        ],
    )
    mock_agent_cls.return_value.run_sync.return_value = history

    snapshot = adapter.get_snapshot("人民广场店")

    assert snapshot.store_id == "store_real_001"
    assert snapshot.store_name == "人民广场店"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


@patch("browser_use.Agent")
def test_get_snapshot_raises_when_structured_output_missing(mock_agent_cls, adapter):
    history = _make_history(final_result="plain text only")
    history.structured_output = None
    mock_agent_cls.return_value.run_sync.return_value = history

    with pytest.raises(RuntimeError, match="structured snapshot"):
        adapter.get_snapshot("人民广场店")
```

- [ ] **Step 2: Run structured snapshot tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_browser_use_adapter.py::test_get_snapshot_maps_structured_browser_use_output tests/test_browser_use_adapter.py::test_get_snapshot_raises_when_structured_output_missing -q
```

Expected:

```text
FAILED tests/test_browser_use_adapter.py::test_get_snapshot_maps_structured_browser_use_output
ImportError: cannot import name '_StoreSnapshotResult'
```

- [ ] **Step 3: Add structured snapshot schemas and implementation**

Add near `_PriceUpdateResult` in `food_ops_demo/browser_use_adapter.py`:

```python
class _StoreSnapshotItemResult(BaseModel):
    item_id: str = ""
    name: str
    price: str
    sale_status: str = "on_sale"
    image: str = ""


class _StoreSnapshotResult(BaseModel):
    store_id: str = ""
    store_name: str
    phone: str = ""
    business_hours: list[dict[str, str]] = []
    items: list[_StoreSnapshotItemResult] = []
```

Replace `get_snapshot()` with:

```python
    def get_snapshot(self, store_name: str) -> StoreSnapshot:
        task = (
            f"Navigate to {self.page_url}. Extract the current store data for store named '{store_name}'. "
            "Return structured data with store_id, store_name, phone, business_hours, and items. "
            "Each item must include item_id, name, price, sale_status, and image."
        )
        try:
            history = self._run_agent(task, output_model_schema=_StoreSnapshotResult)
            self._collect_screenshots(history)
        except Exception as exc:
            raise RuntimeError(
                f"BrowserUseAgent failed while getting snapshot for '{store_name}': {exc}"
            ) from exc

        structured = history.structured_output
        if structured is None:
            raise RuntimeError(f"BrowserUseAgent returned no structured snapshot for '{store_name}'.")
        if structured.store_name != store_name:
            raise KeyError(store_name)

        return StoreSnapshot(
            store_id=structured.store_id,
            store_name=structured.store_name,
            phone=structured.phone,
            business_hours=structured.business_hours,
            items=[
                MenuItem(
                    item_id=item.item_id or item.name,
                    store_id=structured.store_id,
                    name=item.name,
                    price=item.price,
                    sale_status=item.sale_status,
                    image=item.image,
                )
                for item in structured.items
            ],
        )
```

- [ ] **Step 4: Run structured snapshot tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_browser_use_adapter.py::test_get_snapshot_maps_structured_browser_use_output tests/test_browser_use_adapter.py::test_get_snapshot_raises_when_structured_output_missing -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run browser_use workflow tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_browser_use_mode.py tests/test_browser_use_adapter.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 6: Commit**

```powershell
git add food_ops_demo/browser_use_adapter.py tests/test_browser_use_adapter.py
git commit -m "feat: extract structured browser_use snapshots"
```

---

## Task 7: Move Browser-Backed Execution Toward Runner-Owned Jobs

**Files:**
- Modify: `food_ops_demo/storage.py`
- Modify: `food_ops_demo/runner.py`
- Modify: `food_ops_demo/workflow.py`
- Create: `tests/test_v1_runner_execution.py`

- [ ] **Step 1: Add failing runner-owned execution test**

Create `tests/test_v1_runner_execution.py`:

```python
from unittest.mock import MagicMock

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationResult
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.runner import LocalRunner
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


class RecordingBrowserAdapter(FakePlatformAdapter):
    def __init__(self, database):
        super().__init__(database=database)
        self.closed = False

    def close(self):
        self.closed = True


def test_browser_task_can_be_queued_and_completed_by_runner(tmp_path):
    database = DemoDatabase(tmp_path / "food_ops.sqlite3")
    audit = AuditLog(tmp_path / "audit.jsonl")
    created_adapters = []

    def factory():
        adapter = RecordingBrowserAdapter(database)
        created_adapters.append(adapter)
        return adapter

    registry = AdapterRegistry({"browser_use": factory}, shared_modes=set())
    validation_adapter = FakePlatformAdapter(database=database)
    parsed = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    validated = validate_plan(parsed.plan, validation_adapter)
    manager = TaskManager(
        adapter_registry=registry,
        default_adapter_mode="browser_use",
        audit_log=audit,
        database=database,
        queue_browser_modes=True,
        platform_account_id="account_local",
    )
    task = manager.create_task(validated.plan, validated.preview, adapter_mode="browser_use")
    queued = manager.confirm_task(task.task_id)

    assert queued.state == "queued"
    assert queued.result["queued"] is True

    runner = LocalRunner(database=database, adapter_registry=registry, worker_id="worker_1", audit_log=audit)
    processed = runner.run_once()
    completed = database.get_task(task.task_id)

    assert processed == 1
    assert completed.state == "succeeded"
    assert completed.result["verified"] is True
    assert created_adapters[0].closed is True
```

- [ ] **Step 2: Run runner-owned execution test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_runner_execution.py -q
```

Expected:

```text
FAILED tests/test_v1_runner_execution.py::test_browser_task_can_be_queued_and_completed_by_runner
TypeError: TaskManager.__init__() got an unexpected keyword argument 'queue_browser_modes'
```

- [ ] **Step 3: Add task ID lookup to queued jobs**

Add to `food_ops_demo/storage.py` after `complete_job()`:

```python
    def get_job_task_id(self, job_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT task_id FROM operation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return row["task_id"] if row else None
```

- [ ] **Step 4: Add queue option to TaskManager**

Modify `TaskManager.__init__` signature in `food_ops_demo/workflow.py`:

```python
        queue_browser_modes: bool = False,
        platform_account_id: str = "local_demo",
```

Set fields:

```python
        self.queue_browser_modes = queue_browser_modes
        self.platform_account_id = platform_account_id
```

Add helper:

```python
    def _should_queue(self, task: Task) -> bool:
        return self.queue_browser_modes and task.adapter_mode in {"mock_web", "shadow", "browser_use"}
```

At the start of `_execute()`, after retrieving the task and before opening `adapter_registry.use(...)`, add:

```python
        if not skip_queue and self.database is not None and self._should_queue(task):
            self._set_state(task, "queued", "任务已进入执行队列。")
            lock_key = f"{self.platform_account_id}:{task.plan.store_name}"
            job_id = self.database.enqueue_job(
                batch_id=task.task_id,
                task_id=task.task_id,
                adapter_mode=task.adapter_mode,
                platform_account_id=self.platform_account_id,
                lock_key=lock_key,
                plan=task.plan,
            )
            task.result = {"queued": True, "job_id": job_id, "lock_key": lock_key}
            self._persist(task)
            return self._copy(task)
```

- [ ] **Step 5: Update LocalRunner to persist task status and audit**

Modify `LocalRunner.__init__` in `food_ops_demo/runner.py`:

```python
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationPlan, Task, TimelineEvent, utc_now_iso


class LocalRunner:
    def __init__(
        self,
        database: DemoDatabase,
        adapter_registry: AdapterRegistry,
        worker_id: str,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.database = database
        self.adapter_registry = adapter_registry
        self.worker_id = worker_id
        self.audit_log = audit_log
```

Add helper methods:

```python
    def _set_state(self, task: Task, state: str, message: str) -> None:
        task.state = state
        task.updated_at = utc_now_iso()
        task.timeline.append(TimelineEvent(state=state, message=message))

    def _verify(self, plan: OperationPlan, snapshot: dict) -> bool:
        if plan.operation_type == "store.update_business_hours":
            return snapshot["business_hours"] == plan.changes["business_hours"]
        if plan.operation_type == "store.update_phone":
            return snapshot["phone"] == plan.changes["phone"]
        matches = [item for item in snapshot["items"] if item["name"] == plan.target_name]
        if len(matches) != 1:
            return False
        item = matches[0]
        if plan.operation_type == "menu.update_price":
            return item["price"] == plan.changes["price"]
        if plan.operation_type == "menu.update_sale_status":
            return item["sale_status"] == plan.changes["sale_status"]
        return False
```

In `run_once()`, after `job = ...`, load the task:

```python
        task = self.database.get_task(job["task_id"])
        if task is None:
            self.database.complete_job(
                job["job_id"],
                state="failed",
                result={"success": False, "error_code": "task_not_found"},
            )
            return 1
```

Replace the success branch after `result = self._apply_plan(...)` with:

```python
            self._set_state(task, "executing", f"正在通过 {job['adapter_mode']} 执行。")
            task.before_snapshot = adapter.get_snapshot(plan.store_name).model_dump(mode="json")
            result = self._apply_plan(plan, adapter)
            if not result.success:
                task.error = result.error
                self._set_state(task, "failed", result.error.message if result.error else "执行失败。")
                task.result = result.model_dump(mode="json")
                self.database.save_task(task)
                self.database.complete_job(job["job_id"], state="failed", result=task.result)
                if self.audit_log is not None:
                    self.audit_log.append(task.model_dump(mode="json"))
                return 1

            self._set_state(task, "verifying", "正在回读校验执行结果。")
            task.after_snapshot = adapter.get_snapshot(plan.store_name).model_dump(mode="json")
            verified = self._verify(plan, task.after_snapshot)
            task.result = {
                "success": result.success,
                "verified": verified,
                "submitted": result.submitted,
                "shadow_mode": result.shadow_mode,
                "evidence": result.evidence,
                "screenshot_paths": result.screenshot_paths,
            }
            self._set_state(
                task,
                "succeeded" if verified else "failed",
                "任务执行成功，回读校验通过。" if verified else "执行后回读校验未通过。",
            )
            self.database.save_task(task)
            self.database.complete_job(
                job["job_id"],
                state="succeeded" if verified else "failed",
                result=task.result,
            )
            if self.audit_log is not None:
                self.audit_log.append(task.model_dump(mode="json"))
```

- [ ] **Step 6: Run runner tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_runner_execution.py tests/test_runner.py tests/test_job_queue.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 7: Commit**

```powershell
git add food_ops_demo/workflow.py food_ops_demo/runner.py food_ops_demo/storage.py tests/test_v1_runner_execution.py
git commit -m "feat: queue browser tasks for runner execution"
```

---

## Task 8: Upgrade UI Labels And Evidence Presentation For V1

**Files:**
- Modify: `food_ops_demo/static/index.html`
- Modify: `tests/test_static_page.py`

- [ ] **Step 1: Add failing static page tests**

Append to `tests/test_static_page.py`:

```python
def test_static_page_labels_browser_use_as_real_platform_test_mode():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert "BrowserUse 真实平台测试" in html
    assert "实验模式" not in html


def test_static_page_shows_browser_use_evidence_fields():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert "最终 URL" in html
    assert "观测值" in html
    assert "截图路径" in html
    assert "证据文本" in html
```

- [ ] **Step 2: Run static tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py::test_static_page_labels_browser_use_as_real_platform_test_mode tests/test_static_page.py::test_static_page_shows_browser_use_evidence_fields -q
```

Expected:

```text
FAILED tests/test_static_page.py::test_static_page_labels_browser_use_as_real_platform_test_mode
AssertionError: assert 'BrowserUse 真实平台测试' in html
```

- [ ] **Step 3: Update browser_use UI copy**

In `food_ops_demo/static/index.html`, replace:

```html
<option value="browser_use">BrowserUseAdapter 实验模式</option>
```

with:

```html
<option value="browser_use">BrowserUse 真实平台测试</option>
```

Replace the browser-use warning text with:

```html
真实平台测试：由 Browser Use Agent 操作目标后台。请确认环境变量、登录态、截图证据和人工复核流程均已准备。
```

- [ ] **Step 4: Run static tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py -q
```

Expected:

```text
all static page tests pass
```

- [ ] **Step 5: Commit**

```powershell
git add food_ops_demo/static/index.html tests/test_static_page.py
git commit -m "style: label browser_use as real platform test mode"
```

---

## Task 9: Rewrite V1 Documentation And Project Metadata

**Files:**
- Modify: `README.md`
- Modify: `docs/project-structure.md`
- Modify: `pyproject.toml`
- Modify: `food_ops_demo/__init__.py`
- Create: `docs/superpowers/specs/2026-06-03-v1-acceptance-checklist.md`

- [ ] **Step 1: Add documentation verification tests**

Create `tests/test_v1_docs.py`:

```python
from pathlib import Path


def test_readme_describes_v1_not_minimal_mvp():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "正式版 V1" in text
    assert "最小本地 MVP" not in text
    assert "/api/v1" in text
    assert "BrowserUse 真实平台测试" in text


def test_project_structure_has_current_test_baseline():
    text = Path("docs/project-structure.md").read_text(encoding="utf-8")

    assert "163 passed" in text
    assert "72 passed" not in text
    assert "控制面" in text
    assert "执行面" in text


def test_pyproject_metadata_is_v1():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "food-ops-agent"' in text
    assert 'version = "1.0.0"' in text
    assert "V1" in text
```

- [ ] **Step 2: Run docs tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_docs.py -q
```

Expected:

```text
FAILED tests/test_v1_docs.py::test_readme_describes_v1_not_minimal_mvp
AssertionError: assert '正式版 V1' in text
```

- [ ] **Step 3: Update package metadata**

Modify `pyproject.toml`:

```toml
[project]
name = "food-ops-agent"
version = "1.0.0"
description = "Food operations Agent V1 validation workbench and real-platform adapter test harness"
requires-python = ">=3.11"
```

Keep dependencies and optional dependencies unchanged.

Modify `food_ops_demo/__init__.py`:

```python
"""Food delivery operations Agent V1 validation package."""
```

- [ ] **Step 4: Rewrite README core positioning**

Replace the opening section in `README.md` with:

```markdown
# 外卖运营 Agent 工作台

本仓库当前定位为正式版 V1 验证构建，用于在真实外卖平台接入前验证运营 Agent 的控制面、执行面、审计证据和浏览器自动化适配边界。

核心闭环：

```text
自然语言指令 -> 标准操作计划 -> 风险校验 -> 人工确认 -> 任务入队/执行 -> 回读校验 -> 证据与审计留痕
```

V1 保留本地 FakeAdapter、MockWebAdapter 和 ShadowMode 作为验收工具，同时引入 BrowserUse 真实平台测试模式，用于对接真实商家后台前的自动化验证。
```
```

Add an API section:

```markdown
## API 命名空间

- `/api/v1/*`：正式 V1 控制面接口。
- `/api/demo/*`：本地兼容接口，保留给既有验收脚本和演示页面。
- `/mock/merchant`：开发用 Mock 商家后台，不作为真实平台接口。
```

Add a BrowserUse V1 section:

```markdown
## BrowserUse 真实平台测试

`browser_use` 模式通过 browser-use Agent 操作目标后台页面。V1 要求每次执行都产生结构化结果、最终 URL、观测值、截图路径和审计记录。

当前正式支持：

- `menu.update_price`

当前返回明确错误的能力：

- `menu.update_sale_status`
- `store.update_business_hours`
- `store.update_phone`
```

- [ ] **Step 5: Update project structure document**

In `docs/project-structure.md`, update:

```markdown
更新时间：2026-06-03
当前定位：正式版 V1 验证构建
当前验收基线：`163 passed, 1 xpassed`，且 V1 完成后不应存在 browser-use close RuntimeWarning。
```

Add:

```markdown
## 控制面与执行面

- 控制面：FastAPI 负责解析、校验、审批、入队、任务状态和审计查询。
- 执行面：LocalRunner 负责获取 queued job、创建 scoped adapter、执行浏览器操作、回写任务状态和审计证据。
- 真实平台 adapter 不应作为 FastAPI 全局单例长期持有浏览器会话。
```

- [ ] **Step 6: Add V1 acceptance checklist**

Create `docs/superpowers/specs/2026-06-03-v1-acceptance-checklist.md`:

```markdown
# V1 Acceptance Checklist

## Automated Verification

- `pytest -q` exits with status 0.
- No `RuntimeWarning: coroutine 'BrowserSession.close' was never awaited`.
- `/api/v1/health` returns `{"status": "ok"}`.
- `/api/v1/operations/parse` accepts `fake`, `mock_web`, `shadow`, and `browser_use`.
- `/api/demo/*` compatibility endpoints still work.

## Local Adapter Paths

- FakeAdapter can update price and sale status.
- MockWebAdapter can update price and the visible Mock backend reflects the saved price.
- ShadowMode can prefill without submit and stops at `pending_review`.
- BrowserUse can run a mocked price update with evidence.

## Real Platform Readiness

- BrowserUse target URL is configured by `FOOD_OPS_BROWSER_USE_URL`.
- BrowserUse execution includes final URL, observed value, evidence text, and screenshot paths.
- Missing API key returns `browser_use_configuration_error` when API key enforcement is enabled.
- Browser-backed adapters are scoped per operation and closed after use.
- Runner-owned execution can process queued browser jobs.

## Evidence And Audit

- Every completed browser-backed task includes `adapter_mode`.
- Every completed browser-backed task includes `before_snapshot` and `after_snapshot` when submitted.
- Failed browser_use tasks include `error.code`, `error.message`, and evidence fields.
- Audit JSONL contains the same result evidence shown in the workbench.
```

- [ ] **Step 7: Run documentation tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_v1_docs.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit**

```powershell
git add README.md docs/project-structure.md docs/superpowers/specs/2026-06-03-v1-acceptance-checklist.md pyproject.toml food_ops_demo/__init__.py tests/test_v1_docs.py
git commit -m "docs: position project as v1 validation build"
```

---

## Task 10: Final V1 Acceptance Run

**Files:**
- Modify only if previous tasks reveal a verified defect.

- [ ] **Step 1: Run full automated suite**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -q
```

Expected:

```text
all tests pass
no RuntimeWarning about BrowserSession.close
```

- [ ] **Step 2: Start local V1 service**

Run:

```powershell
$env:FOOD_OPS_ENV='local'
$env:FOOD_OPS_API_PREFIX='/api/v1'
$env:FOOD_OPS_DATA_DIR='data/local'
$env:FOOD_OPS_BROWSER_USE_REQUIRE_API_KEY='0'
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8765
```

- [ ] **Step 3: Verify V1 health and route compatibility**

Run in a second shell:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/demo/snapshot'
```

Expected:

```text
status ok
status ok
store_name 人民广场店
```

- [ ] **Step 4: Run real-user browser acceptance paths**

Use the workbench at:

```text
http://127.0.0.1:8765/
```

Execute these paths:

```text
FakeAdapter: 把人民广场店的可乐设为售罄 -> succeeded
MockWebAdapter: 把人民广场店的招牌牛肉饭改成 1000 -> succeeded, Mock 后台显示 1000.00
ShadowMode: 把人民广场店的招牌牛肉饭改成 29.9 -> pending_review, submitted=false
BrowserUse 真实平台测试: 把人民广场店的招牌牛肉饭改成 29.9 -> mocked tests pass; live run only when BROWSER_USE_API_KEY and target login are ready
```

Expected:

```text
No HTTP 500
No Playwright Sync API lifecycle error
No browser-use close RuntimeWarning
Evidence and audit fields visible for browser_use tasks
```

- [ ] **Step 5: Check service logs**

Run:

```powershell
Select-String -Path 'data/local/*.log','data/demo/*.log' -Pattern 'Traceback','Internal Server Error','Playwright Sync API','BrowserSession.close' -ErrorAction SilentlyContinue
```

Expected:

```text
No matches for fresh V1 acceptance logs
```

- [ ] **Step 6: Commit acceptance documentation updates**

If acceptance evidence files or docs were updated:

```powershell
git status --short
git add README.md docs/project-structure.md docs/superpowers/specs/2026-06-03-v1-acceptance-checklist.md
git commit -m "docs: record v1 acceptance baseline"
```

If no tracked files changed:

```powershell
git status --short
```

Expected:

```text
clean worktree
```

---

## Self-Review

### Spec Coverage

- Formal V1 structure: covered by Tasks 1, 2, 3, 4, and 9.
- Clear module boundaries: covered by route split, dependency assembly, repository wrappers, and constants.
- Removal of demo-only ambiguity: covered by V1 docs, `/api/v1`, `data/local`, and dev mock isolation.
- Real platform testing preparation: covered by BrowserUse capabilities, configuration validation, structured snapshots, evidence, and runner-owned execution.
- Logs, errors, and lifecycle: covered by Task 5 warning elimination, `browser_use_configuration_error`, evidence model use, and final log checks.
- Existing core behavior preserved: covered by route compatibility tests, existing full suite, and final acceptance paths.

### Placeholder Scan

The plan avoids open-ended instructions by giving exact file paths, concrete test names, concrete code snippets, concrete commands, and expected outcomes.

### Type Consistency

The plan uses these names consistently:

- `FoodOpsSettings`
- `AdapterMode`
- `TaskState`
- `OperationType`
- `ErrorCode`
- `AdapterCapabilities`
- `BrowserUseExecutionEvidence`
- `_StoreSnapshotResult`
- `StoreRepository`
- `TaskRepository`
- `JobQueueRepository`
- `AppServices`

### Execution Order

The task order is intentional:

1. Settings and constants make later edits smaller.
2. Route split and repositories reduce `app.py` and `storage.py` coupling.
3. BrowserUse hardening fixes the current warning and upgrades adapter semantics.
4. Runner-owned execution aligns the system with real-platform operation constraints.
5. UI/docs clarify V1 positioning.
6. Final acceptance verifies that structure changes did not regress behavior.

