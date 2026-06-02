# Browser Runner And Multi-Store Orchestration Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Phase 4 Playwright lifecycle defect with the production direction by moving browser execution out of shared FastAPI adapter instances and introducing a local runner foundation for multi-store task orchestration.

**Architecture:** Treat FastAPI as the control plane: parse instructions, validate plans, create tasks, expose task status, and enqueue browser work. Treat Playwright as an execution-plane concern: each browser job is handled by an isolated runner-owned adapter lifecycle with explicit close semantics, per-account/per-store locks, evidence capture, and status callbacks. This fixes the current Sync API/thread reuse defect and creates the same shape needed for future requests such as changing different prices across many stores.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, sqlite3, pytest, httpx, Uvicorn subprocess smoke tests, Playwright Python sync API for the local runner phase, vanilla HTML/CSS/JS, CodeGraph.

---

## Incident And Production Alignment

The real-user Phase 4 acceptance run exposed this server-side stack:

```text
playwright._impl._errors.Error: It looks like you are using Playwright Sync API inside the asyncio loop.
Please use the Async API instead.

D:\code\demov1\food_ops_demo\app.py:117
D:\code\demov1\food_ops_demo\risk.py:14
D:\code\demov1\food_ops_demo\mock_web_adapter.py:94
```

Root cause in the current MVP shape:

- `food_ops_demo.app.create_app()` registers `MockWebAdapter` and `ShadowPlatformAdapter` as long-lived app-level adapter objects.
- Each browser adapter stores `_playwright`, `_browser`, and `_page` on the adapter instance.
- FastAPI executes route handlers through AnyIO threadpool boundaries.
- After Shadow Mode uses one browser adapter, a later MockWebAdapter request can hit Playwright Sync API from an incompatible thread/loop context.

Production implication:

- Multi-store orchestration cannot run browser automation inside API request handlers.
- A request like "change Store A item X to 29.9, Store B item Y to 31.9, Store C item Z to 26.5" must become a batch of child jobs.
- Jobs must be serialized by platform account and store, while unrelated stores/accounts can run concurrently.
- Browser sessions and Playwright lifecycle must belong to a runner worker, not to FastAPI route globals.
- Every child job needs evidence, retry state, manual-intervention state, and a parent batch summary.

## File Structure

- Create `tests/test_live_playwright_lifecycle.py`: live Uvicorn regression that runs Shadow Mode followed by MockWebAdapter in the same service process.
- Create `food_ops_demo/adapter_registry.py`: adapter factory/context manager that returns fresh browser adapters per use and closes them deterministically.
- Modify `food_ops_demo/app.py`: replace app-level browser adapter singletons with `AdapterRegistry`.
- Modify `food_ops_demo/workflow.py`: execute tasks through `AdapterRegistry.use(mode)` so browser adapters are task-scoped.
- Modify `tests/test_workflow_adapter_modes.py`: keep fake/mock routing coverage with the registry.
- Modify `tests/test_api.py`: keep API mode coverage and add adapter lifecycle assertions.
- Create `food_ops_demo/orchestration.py`: batch-to-child-plan decomposition and lock-key calculation for multi-store price tasks.
- Create `tests/test_orchestration.py`: verify multi-store jobs, lock keys, and parent/child relationships.
- Modify `food_ops_demo/storage.py`: add local queue tables and lease/lock methods.
- Create `tests/test_job_queue.py`: verify queue acquire, lease, completion, and store lock behavior.
- Create `food_ops_demo/runner.py`: local runner loop that acquires queued jobs and executes them with runner-owned adapter lifecycle.
- Create `tests/test_runner.py`: verify runner processes one browser job and records evidence.
- Modify `food_ops_demo/static/index.html`: show batch parent status and child job progress for local multi-store orchestration.
- Modify `README.md`: document why Playwright runs in runner-owned execution, not request handlers.
- Modify `docs/project-structure.md`: document control plane, runner, queue, and lock responsibilities.

---

## Task 1: Add Live Regression For Shadow Then MockWebAdapter

**Files:**
- Create: `tests/test_live_playwright_lifecycle.py`

- [ ] **Step 1: Write the failing live-service regression**

Create `tests/test_live_playwright_lifecycle.py`:

```python
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
```

- [ ] **Step 2: Run the live regression and verify it fails on the current architecture**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_live_playwright_lifecycle.py::test_shadow_then_mock_web_parse_does_not_reuse_bad_playwright_lifecycle -v
```

Expected before the lifecycle fix:

```text
FAILED
mock_parse.status_code == 500
Playwright Sync API inside the asyncio loop
```

- [ ] **Step 3: Commit the failing regression**

Run:

```powershell
git add tests/test_live_playwright_lifecycle.py
git commit -m "test: reproduce browser adapter lifecycle leak"
```

---

## Task 2: Add Adapter Registry With Scoped Browser Lifetimes

**Files:**
- Create: `food_ops_demo/adapter_registry.py`
- Create: `tests/test_adapter_registry.py`

- [ ] **Step 1: Write adapter registry tests**

Create `tests/test_adapter_registry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry


class ClosableAdapter(FakePlatformAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


@dataclass
class AdapterRecorder:
    created: list[ClosableAdapter]

    def factory(self) -> ClosableAdapter:
        adapter = ClosableAdapter()
        self.created.append(adapter)
        return adapter


def test_registry_reuses_shared_fake_adapter():
    fake = FakePlatformAdapter()
    registry = AdapterRegistry({"fake": lambda: fake}, shared_modes={"fake"})

    with registry.use("fake") as first:
        with registry.use("fake") as second:
            assert first is fake
            assert second is fake


def test_registry_closes_scoped_browser_adapter_after_use():
    recorder = AdapterRecorder(created=[])
    registry = AdapterRegistry({"mock_web": recorder.factory}, shared_modes=set())

    with registry.use("mock_web") as adapter:
        assert adapter.closed is False
        first = adapter

    assert first.closed is True
    with registry.use("mock_web") as second:
        assert second is not first
    assert second.closed is True


def test_registry_returns_none_for_unknown_mode():
    registry = AdapterRegistry({}, shared_modes=set())

    assert registry.has_mode("missing") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter_registry.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'food_ops_demo.adapter_registry'
```

- [ ] **Step 3: Implement the registry**

Create `food_ops_demo/adapter_registry.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from food_ops_demo.adapter import BasePlatformAdapter


AdapterFactory = Callable[[], BasePlatformAdapter]


class AdapterRegistry:
    def __init__(self, factories: dict[str, AdapterFactory], shared_modes: set[str] | None = None) -> None:
        self._factories = factories
        self._shared_modes = shared_modes or set()
        self._shared_adapters: dict[str, BasePlatformAdapter] = {}

    def has_mode(self, mode: str) -> bool:
        return mode in self._factories

    @contextmanager
    def use(self, mode: str) -> Iterator[BasePlatformAdapter | None]:
        factory = self._factories.get(mode)
        if factory is None:
            yield None
            return

        if mode in self._shared_modes:
            adapter = self._shared_adapters.get(mode)
            if adapter is None:
                adapter = factory()
                self._shared_adapters[mode] = adapter
            yield adapter
            return

        adapter = factory()
        try:
            yield adapter
        finally:
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
```

- [ ] **Step 4: Run registry tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter_registry.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit registry**

Run:

```powershell
git add food_ops_demo/adapter_registry.py tests/test_adapter_registry.py
git commit -m "feat: add scoped adapter registry"
```

---

## Task 3: Wire FastAPI Parse And TaskManager Through AdapterRegistry

**Files:**
- Modify: `food_ops_demo/app.py`
- Modify: `food_ops_demo/workflow.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_workflow_adapter_modes.py`

- [ ] **Step 1: Add API regression for unknown adapter mode through registry**

Append to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Modify `TaskManager` constructor to accept registry**

Modify imports in `food_ops_demo/workflow.py`:

```python
from food_ops_demo.adapter_registry import AdapterRegistry
```

Modify `TaskManager.__init__`:

```python
    def __init__(
        self,
        adapter: BasePlatformAdapter | None = None,
        audit_log: AuditLog | None = None,
        database: DemoDatabase | None = None,
        adapters: dict[str, BasePlatformAdapter] | None = None,
        adapter_registry: AdapterRegistry | None = None,
        default_adapter_mode: str = "fake",
    ) -> None:
        default_adapter = adapter or FakePlatformAdapter(database=database)
        self.adapter_registry = adapter_registry
        self.adapters = adapters or {default_adapter_mode: default_adapter}
        self.default_adapter_mode = default_adapter_mode
        self.adapter = self.adapters[self.default_adapter_mode]
        self.audit_log = audit_log or AuditLog(Path("data/demo/audit.jsonl"))
        self.database = database
        self._tasks: dict[str, Task] = {}
```

- [ ] **Step 3: Split `_execute` into registry and adapter-specific execution**

Modify `food_ops_demo/workflow.py`:

```python
    def _execute(self, task: Task, skip_queue: bool = False) -> Task:
        if self.adapter_registry is None:
            adapter = self._adapter_for(task)
            if adapter is None:
                self._fail(task, "adapter_mode_not_found", f"找不到执行模式：{task.adapter_mode}")
                self._persist(task)
                return self._copy(task)
            return self._execute_with_adapter(task, adapter, skip_queue=skip_queue)

        with self.adapter_registry.use(task.adapter_mode) as adapter:
            if adapter is None:
                self._fail(task, "adapter_mode_not_found", f"找不到执行模式：{task.adapter_mode}")
                self._persist(task)
                return self._copy(task)
            return self._execute_with_adapter(task, adapter, skip_queue=skip_queue)

    def _execute_with_adapter(self, task: Task, adapter: BasePlatformAdapter, skip_queue: bool = False) -> Task:
        if not skip_queue:
            self._set_state(task, "queued", "任务已进入执行队列。")
            if task.adapter_mode == "shadow":
                self._set_state(task, "session_ready", "Shadow Mode 页面会话已就绪。")
            else:
                self._set_state(task, "executing", f"正在通过 {task.adapter_mode} 执行。")

        try:
            task.before_snapshot = adapter.get_snapshot(task.plan.store_name).model_dump(mode="json")
        except KeyError:
            self._fail(task, "store_not_found", f"找不到门店：{task.plan.store_name}")
            self._append_audit(task)
            self._persist(task)
            return self._copy(task)

        if task.adapter_mode == "shadow":
            self._set_state(task, "pre_snapshot_done", "已读取提交前快照。")
            self._set_state(task, "executing", f"正在通过 {task.adapter_mode} 执行。")

        result = self._apply_plan(task.plan, adapter)
        if result.shadow_mode and result.success:
            return self._complete_shadow_task(task, result)
        if not result.success:
            task.error = result.error
            if result.error and result.error.code == "auth_required":
                task.manual_intervention_type = "auth_required"
                self._set_state(task, "manual_required", result.error.message, result.error.code)
            else:
                self._set_state(
                    task,
                    "failed",
                    result.error.message if result.error else "执行失败。",
                    result.error.code if result.error else None,
                )
            self._append_audit(task)
            self._persist(task)
            return self._copy(task)

        self._set_state(task, "verifying", "正在回读校验执行结果。")
        task.after_snapshot = adapter.get_snapshot(task.plan.store_name).model_dump(mode="json")
        verified = self._verify(task.plan, task.after_snapshot)
        task.result = {
            "success": result.success,
            "verified": verified,
            "submitted": result.submitted,
            "shadow_mode": result.shadow_mode,
        }
        if verified:
            self._set_state(task, "succeeded", "任务执行成功，回读校验通过。")
        else:
            self._fail(task, "verification_failed", "执行后回读校验未通过。")
        self._append_audit(task)
        self._persist(task)
        return self._copy(task)
```

Remove the old body of `_execute` after adding `_execute_with_adapter`.

- [ ] **Step 4: Modify `create_app()` to build factories instead of browser singletons**

Modify imports in `food_ops_demo/app.py`:

```python
from food_ops_demo.adapter_registry import AdapterRegistry
```

Replace the `adapters = {...}` block in `create_app()` with:

```python
    adapter_registry = AdapterRegistry(
        {
            "fake": lambda: fake_adapter,
            "mock_web": lambda: MockWebAdapter(
                page_url=mock_url,
                screenshot_dir=os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", "data/demo/mock-web-screenshots"),
                headless=os.getenv("FOOD_OPS_MOCK_WEB_HEADLESS", "1") != "0",
            ),
            "shadow": lambda: ShadowPlatformAdapter(
                page_url=shadow_target_url,
                screenshot_dir=shadow_evidence_dir,
                headless=os.getenv("FOOD_OPS_SHADOW_HEADLESS", "1") != "0",
            ),
        },
        shared_modes={"fake"},
    )
```

Modify `TaskManager` creation:

```python
    manager = TaskManager(
        adapter=fake_adapter,
        adapter_registry=adapter_registry,
        default_adapter_mode="fake",
        audit_log=audit_log,
        database=database,
    )
```

Modify parse route:

```python
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
```

- [ ] **Step 5: Run focused API and workflow tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py tests/test_workflow.py tests/test_workflow_adapter_modes.py tests/test_workflow_shadow_mode.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 6: Run the live lifecycle regression**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_live_playwright_lifecycle.py -v
```

Expected after implementation:

```text
1 passed
```

- [ ] **Step 7: Commit lifecycle wiring**

Run:

```powershell
git add food_ops_demo/app.py food_ops_demo/workflow.py tests/test_api.py tests/test_workflow_adapter_modes.py tests/test_live_playwright_lifecycle.py
git commit -m "fix: scope browser adapters per operation"
```

---

## Task 4: Define Multi-Store Orchestration Units

**Files:**
- Create: `food_ops_demo/orchestration.py`
- Create: `tests/test_orchestration.py`

- [ ] **Step 1: Write orchestration tests**

Create `tests/test_orchestration.py`:

```python
from food_ops_demo.models import OperationPlan
from food_ops_demo.orchestration import (
    BatchPriceChange,
    StorePriceChange,
    build_child_plans,
    lock_key_for_plan,
)


def test_build_child_plans_for_multi_store_price_changes():
    batch = BatchPriceChange(
        instruction="把三个门店的招牌牛肉饭分别改成不同价格",
        platform_account_id="meituan_account_001",
        changes=[
            StorePriceChange(store_name="人民广场店", item_name="招牌牛肉饭", price="29.90"),
            StorePriceChange(store_name="五角场店", item_name="招牌牛肉饭", price="31.90"),
            StorePriceChange(store_name="徐家汇店", item_name="招牌牛肉饭", price="26.50"),
        ],
    )

    plans = build_child_plans(batch)

    assert [plan.store_name for plan in plans] == ["人民广场店", "五角场店", "徐家汇店"]
    assert [plan.changes["price"] for plan in plans] == ["29.90", "31.90", "26.50"]
    assert all(plan.operation_type == "menu.update_price" for plan in plans)
    assert all(plan.requires_approval is True for plan in plans)


def test_lock_key_uses_platform_account_and_store():
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
        risk_level="medium",
        requires_approval=True,
    )

    assert lock_key_for_plan("meituan_account_001", plan) == "meituan_account_001:人民广场店"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_orchestration.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'food_ops_demo.orchestration'
```

- [ ] **Step 3: Implement orchestration models**

Create `food_ops_demo/orchestration.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from food_ops_demo.models import OperationPlan, new_id


class StorePriceChange(BaseModel):
    store_name: str
    item_name: str
    price: str


class BatchPriceChange(BaseModel):
    batch_id: str = Field(default_factory=lambda: new_id("batch"))
    instruction: str
    platform_account_id: str
    changes: list[StorePriceChange]


def build_child_plans(batch: BatchPriceChange) -> list[OperationPlan]:
    return [
        OperationPlan(
            instruction=batch.instruction,
            operation_type="menu.update_price",
            store_name=change.store_name,
            target_name=change.item_name,
            changes={"price": change.price},
            risk_level="medium",
            requires_approval=True,
        )
        for change in batch.changes
    ]


def lock_key_for_plan(platform_account_id: str, plan: OperationPlan) -> str:
    return f"{platform_account_id}:{plan.store_name}"
```

- [ ] **Step 4: Run orchestration tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_orchestration.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit orchestration units**

Run:

```powershell
git add food_ops_demo/orchestration.py tests/test_orchestration.py
git commit -m "feat: add multi-store orchestration units"
```

---

## Task 5: Add Local Job Queue And Store Locks

**Files:**
- Modify: `food_ops_demo/storage.py`
- Create: `tests/test_job_queue.py`

- [ ] **Step 1: Write queue and lock tests**

Create `tests/test_job_queue.py`:

```python
from food_ops_demo.models import OperationPlan
from food_ops_demo.storage import DemoDatabase


def _plan(store_name: str, price: str) -> OperationPlan:
    return OperationPlan(
        instruction=f"把{store_name}的招牌牛肉饭改成 {price}",
        operation_type="menu.update_price",
        store_name=store_name,
        target_name="招牌牛肉饭",
        changes={"price": price},
        risk_level="medium",
        requires_approval=True,
    )


def test_job_queue_acquires_one_job_per_lock_key(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_002",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "31.90"),
    )

    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)
    second = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert first is not None
    assert first["task_id"] == "task_001"
    assert second is None


def test_job_queue_allows_different_store_locks(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_002",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:五角场店",
        plan=_plan("五角场店", "31.90"),
    )

    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)
    second = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert first is not None
    assert second is not None
    assert {first["task_id"], second["task_id"]} == {"task_001", "task_002"}


def test_complete_job_releases_lock(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="mock_web",
        platform_account_id="account_001",
        lock_key="account_001:人民广场店",
        plan=_plan("人民广场店", "29.90"),
    )
    first = db.acquire_next_job(worker_id="runner_001", lease_seconds=30)

    db.complete_job(first["job_id"], state="succeeded", result={"success": True})
    next_job = db.acquire_next_job(worker_id="runner_002", lease_seconds=30)

    assert next_job is None
```

- [ ] **Step 2: Run queue tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_job_queue.py -v
```

Expected:

```text
AttributeError: 'DemoDatabase' object has no attribute 'enqueue_job'
```

- [ ] **Step 3: Add queue schema**

Modify `food_ops_demo/storage.py` in `_init_schema()`:

```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_jobs (
                    job_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    adapter_mode TEXT NOT NULL,
                    platform_account_id TEXT NOT NULL,
                    lock_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    worker_id TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
```

- [ ] **Step 4: Add queue methods**

Modify imports in `food_ops_demo/storage.py`:

```python
from datetime import UTC, datetime, timedelta

from food_ops_demo.models import OperationPlan, Task, new_id, utc_now_iso
```

Add methods to `DemoDatabase`:

```python
    def enqueue_job(
        self,
        batch_id: str,
        task_id: str,
        adapter_mode: str,
        platform_account_id: str,
        lock_key: str,
        plan: OperationPlan,
    ) -> str:
        job_id = new_id("job")
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operation_jobs (
                    job_id, batch_id, task_id, adapter_mode, platform_account_id,
                    lock_key, state, plan_json, result_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, '{}', ?, ?)
                """,
                (
                    job_id,
                    batch_id,
                    task_id,
                    adapter_mode,
                    platform_account_id,
                    lock_key,
                    plan.model_dump_json(),
                    now,
                    now,
                ),
            )
        return job_id

    def acquire_next_job(self, worker_id: str, lease_seconds: int) -> dict | None:
        now = datetime.now(UTC)
        lease_expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
        now_text = now.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM operation_jobs
                WHERE state = 'queued'
                ORDER BY created_at
                """
            ).fetchall()
            for row in rows:
                active_lock = conn.execute(
                    """
                    SELECT 1
                    FROM operation_jobs
                    WHERE lock_key = ?
                      AND state = 'running'
                      AND lease_expires_at > ?
                    LIMIT 1
                    """,
                    (row["lock_key"], now_text),
                ).fetchone()
                if active_lock is not None:
                    continue
                conn.execute(
                    """
                    UPDATE operation_jobs
                    SET state = 'running',
                        worker_id = ?,
                        lease_expires_at = ?,
                        updated_at = ?
                    WHERE job_id = ?
                    """,
                    (worker_id, lease_expires_at, now_text, row["job_id"]),
                )
                return dict(conn.execute("SELECT * FROM operation_jobs WHERE job_id = ?", (row["job_id"],)).fetchone())
        return None

    def complete_job(self, job_id: str, state: str, result: dict) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE operation_jobs
                SET state = ?,
                    result_json = ?,
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (state, json.dumps(result, ensure_ascii=False), now, job_id),
            )
```

- [ ] **Step 5: Run queue tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_job_queue.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit queue foundation**

Run:

```powershell
git add food_ops_demo/storage.py tests/test_job_queue.py
git commit -m "feat: add local job queue and store locks"
```

---

## Task 6: Add Local Runner Entry Point

**Files:**
- Create: `food_ops_demo/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write runner test**

Create `tests/test_runner.py`:

```python
from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.models import OperationPlan
from food_ops_demo.runner import LocalRunner
from food_ops_demo.storage import DemoDatabase


def test_local_runner_processes_one_fake_job(tmp_path):
    database = DemoDatabase(tmp_path / "demo.sqlite3")
    fake = FakePlatformAdapter(database=database)
    registry = AdapterRegistry({"fake": lambda: fake}, shared_modes={"fake"})
    plan = OperationPlan(
        instruction="把人民广场店的招牌牛肉饭改成 29.9",
        operation_type="menu.update_price",
        store_name="人民广场店",
        target_name="招牌牛肉饭",
        changes={"price": "29.90"},
        risk_level="medium",
        requires_approval=True,
    )
    database.enqueue_job(
        batch_id="batch_001",
        task_id="task_001",
        adapter_mode="fake",
        platform_account_id="local_demo",
        lock_key="local_demo:人民广场店",
        plan=plan,
    )
    runner = LocalRunner(database=database, adapter_registry=registry, worker_id="runner_001")

    processed = runner.run_once()
    snapshot = database.get_store_snapshot("人民广场店")

    assert processed == 1
    assert snapshot.items[0].price == "29.90"
```

- [ ] **Step 2: Run runner test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_runner.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'food_ops_demo.runner'
```

- [ ] **Step 3: Implement `LocalRunner`**

Create `food_ops_demo/runner.py`:

```python
from __future__ import annotations

import json

from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.models import OperationPlan
from food_ops_demo.storage import DemoDatabase


class LocalRunner:
    def __init__(self, database: DemoDatabase, adapter_registry: AdapterRegistry, worker_id: str) -> None:
        self.database = database
        self.adapter_registry = adapter_registry
        self.worker_id = worker_id

    def run_once(self) -> int:
        job = self.database.acquire_next_job(worker_id=self.worker_id, lease_seconds=60)
        if job is None:
            return 0

        plan = OperationPlan.model_validate_json(job["plan_json"])
        with self.adapter_registry.use(job["adapter_mode"]) as adapter:
            if adapter is None:
                self.database.complete_job(
                    job["job_id"],
                    state="failed",
                    result={"success": False, "error_code": "adapter_mode_not_found"},
                )
                return 1
            result = self._apply_plan(plan, adapter)
            self.database.complete_job(
                job["job_id"],
                state="succeeded" if result.success else "failed",
                result=result.model_dump(mode="json"),
            )
        return 1

    def _apply_plan(self, plan: OperationPlan, adapter) -> object:
        if plan.operation_type == "menu.update_price":
            return adapter.update_menu_price(plan.store_name, plan.target_name or "", plan.changes["price"])
        if plan.operation_type == "menu.update_sale_status":
            return adapter.update_menu_sale_status(plan.store_name, plan.target_name or "", plan.changes["sale_status"])
        if plan.operation_type == "store.update_business_hours":
            return adapter.update_business_hours(plan.store_name, plan.changes["business_hours"])
        if plan.operation_type == "store.update_phone":
            return adapter.update_store_phone(plan.store_name, plan.changes["phone"])
        raise ValueError(f"unsupported operation type: {plan.operation_type}")
```

Remove `import json` if it is not used after implementation.

- [ ] **Step 4: Run runner tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_runner.py tests/test_job_queue.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 5: Commit runner**

Run:

```powershell
git add food_ops_demo/runner.py tests/test_runner.py
git commit -m "feat: add local operation runner"
```

---

## Task 7: Document Production Alignment

**Files:**
- Modify: `README.md`
- Modify: `docs/project-structure.md`
- Create: `docs/superpowers/specs/2026-06-02-runner-orchestration-alignment.md`

- [ ] **Step 1: Add design note**

Create `docs/superpowers/specs/2026-06-02-runner-orchestration-alignment.md`:

```markdown
# Runner Orchestration Alignment Design

## Problem

Phase 4 real-user testing showed that app-level browser adapter instances can leak Playwright Sync API state across FastAPI requests. This is incompatible with production browser automation because multi-store tasks require retries, locks, manual intervention, screenshots, and batch progress outside a single HTTP request.

## Direction

FastAPI is the control plane. It parses instructions, validates plans, creates tasks, exposes status, and enqueues browser work.

The runner is the execution plane. It owns Playwright lifecycle, browser sessions, evidence capture, retries, and manual-intervention recovery.

## Locking Rule

The lock key is:

```text
platform_account_id:store_name
```

Only one write job can run for the same lock key at a time. Different store locks can run concurrently if the platform account policy allows it.

## Multi-Store Flow

```text
Batch instruction
  -> child OperationPlan per store/item/price
  -> child Task per OperationPlan
  -> queued OperationJob per child Task
  -> runner acquires jobs by lock
  -> browser adapter executes one job
  -> evidence and state are persisted
  -> parent batch aggregates child states
```

## Safety

Shadow Mode remains no-submit. MockWebAdapter and future real adapters are committed modes and must write after approval only. Login, captcha, QR code, SMS, and platform review states move the job to `manual_required`.
```

- [ ] **Step 2: Update README**

Add this section to `README.md`:

```markdown
## Browser Runner And Multi-Store Orchestration

Browser automation must not run as a shared FastAPI adapter singleton. The API process is the control plane: it parses instructions, validates plans, creates tasks, and enqueues work. Playwright belongs to a runner-owned execution plane, where each browser job has an explicit lifecycle, screenshots, retry state, and account/store lock.

For multi-store price changes, the system decomposes one batch instruction into child `OperationPlan` records. Each child job uses a lock key of `platform_account_id:store_name`, so the same store is serialized while independent stores can proceed concurrently.
```

- [ ] **Step 3: Update project structure**

Add to `docs/project-structure.md`:

```markdown
- `food_ops_demo.adapter_registry.AdapterRegistry`: creates shared non-browser adapters and scoped browser adapters so Playwright state is not held by FastAPI route globals.
- `food_ops_demo.orchestration`: decomposes multi-store price changes into child operation plans and lock keys.
- `food_ops_demo.runner.LocalRunner`: local execution-plane prototype that acquires queued jobs, owns adapter lifecycle, and records completion.
- `operation_jobs` SQLite table: local queue used to model future runner dispatch and per-store locking.
```

- [ ] **Step 4: Run docs search**

Run:

```powershell
rg "control plane|execution plane|AdapterRegistry|LocalRunner|platform_account_id:store_name" README.md docs/project-structure.md docs/superpowers/specs/2026-06-02-runner-orchestration-alignment.md
```

Expected:

```text
Matches appear in all three files
```

- [ ] **Step 5: Commit docs**

Run:

```powershell
git add README.md docs/project-structure.md docs/superpowers/specs/2026-06-02-runner-orchestration-alignment.md
git commit -m "docs: align browser runner orchestration"
```

---

## Task 8: Final Verification And Browser Acceptance

**Files:**
- No source files should be modified in this task unless verification reveals a defect.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -q
```

Expected:

```text
All tests pass, with the existing expected xfail still marked xfailed
```

- [ ] **Step 2: Restart local app**

Run:

```powershell
$conn = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1
if ($conn) {
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
  if ($proc.CommandLine -like '*food_ops_demo.asgi:app*') {
    Stop-Process -Id $conn.OwningProcess -Force
  }
}
$env:FOOD_OPS_SHADOW_URL='http://127.0.0.1:8765/mock/merchant'
$env:FOOD_OPS_SHADOW_SCREENSHOT_DIR='data/demo/shadow-mode-evidence'
$env:FOOD_OPS_SHADOW_HEADLESS='1'
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

Expected health check:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health'
```

```json
{"status":"ok"}
```

- [ ] **Step 3: Browser smoke test**

Open `http://127.0.0.1:8765/` in the in-app browser and verify:

- ShadowMode price change reaches `pending_review`.
- `shadow_evidence.screenshot_path` exists.
- The store snapshot remains unchanged after ShadowMode.
- Without restarting the service, MockWebAdapter parse for the same price command returns a plan and no `HTTP 500`.
- MockWebAdapter confirm reaches `succeeded`.
- FakeAdapter confirm reaches `succeeded`.
- Browser console has no errors.

- [ ] **Step 4: Run live lifecycle test again**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_live_playwright_lifecycle.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Sync CodeGraph**

Run:

```powershell
codegraph sync .
codegraph status
```

Expected:

```text
The indexed Python file count includes adapter_registry.py, orchestration.py, and runner.py
```

- [ ] **Step 6: Check final git state**

Run:

```powershell
git status --short
git log --oneline -10
```

Expected:

```text
Working tree is clean.
Recent commits include lifecycle fix, orchestration units, queue, runner, and docs.
```

---

## Self-Review

Spec coverage:

- Real-user Playwright Sync API lifecycle failure: Tasks 1, 2, 3, and 8.
- FastAPI/control-plane versus runner/execution-plane alignment: Tasks 3, 6, 7, and 8.
- Multi-store different-price orchestration: Tasks 4, 5, 6, and 7.
- Per-store lock and queue semantics: Task 5.
- Browser lifecycle isolation: Tasks 2, 3, and 6.
- Regression protection for future work: Tasks 1 and 8.

Marker scan:

- No unresolved marker text remains.
- Every task includes exact paths, commands, expected failures or passes, concrete snippets, and commit messages.

Type consistency:

- Browser adapter lifecycle is represented by `AdapterRegistry.use(mode)`.
- `fake` remains a shared adapter mode.
- `mock_web` and `shadow` are scoped browser adapter modes.
- Multi-store locks use `platform_account_id:store_name`.
- `LocalRunner.run_once()` processes one leased job and records completion in `operation_jobs`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-browser-runner-orchestration-alignment.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
