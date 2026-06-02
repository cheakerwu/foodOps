# Phase 4 Shadow Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Shadow Mode that can open a configured merchant backend page, read current data, locate and prefill a low-risk change, capture evidence, and stop before any submit/save action.

**Architecture:** Keep the current parser, risk engine, task persistence, audit log, and adapter contract. Add a new `shadow` adapter mode behind `BasePlatformAdapter`, extend `OperationResult` and `Task` with explicit no-submit metadata, and teach `TaskManager` to end shadow executions in `pending_review` instead of verifying a committed mutation. The app remains locally testable against `/mock/merchant`, while the same adapter can be pointed at a real backend URL through environment configuration.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, sqlite3, pytest, Playwright Python sync API, vanilla HTML/CSS/JS, CodeGraph.

---

## Scope

Build these capabilities:

- Register a new adapter mode string: `shadow`.
- Let Shadow Mode target `FOOD_OPS_SHADOW_URL`, falling back to the local `/mock/merchant` page for deterministic demo and tests.
- Let Shadow Mode read the current store snapshot through the same adapter contract.
- Let Shadow Mode prefill `menu.update_price` inputs without clicking save.
- Persist evidence that proves Shadow Mode stopped before submission: screenshot path, target URL, target item, original value, intended value, and `submitted: false`.
- Make `TaskManager` stop shadow tasks at `pending_review` after prefill evidence is captured.
- Keep `fake` and `mock_web` behavior unchanged.
- Add workbench UI support for selecting Shadow Mode and displaying `pending_review`.
- Update README and project structure documentation.
- Run full tests, browser smoke, and CodeGraph sync after implementation.

Do not build in Phase 4:

- Real account login automation.
- QR code, SMS, captcha, or face verification handling.
- Real platform submit/save clicks.
- Sale-status shadow prefill when the available control is an immediate-action button.
- Multi-account runners, queues, WebSocket streaming, or remote desktop handoff.

## File Structure

- Modify `food_ops_demo/models.py`: add explicit `OperationResult.submitted`, `OperationResult.shadow_mode`, `OperationResult.evidence`, and `Task.shadow_evidence`.
- Create `food_ops_demo/shadow_adapter.py`: Playwright-backed no-submit adapter.
- Modify `food_ops_demo/app.py`: register the `shadow` adapter mode and load Shadow Mode environment variables.
- Modify `food_ops_demo/workflow.py`: add a shadow branch that records evidence and finishes at `pending_review` without verification.
- Modify `food_ops_demo/static/index.html`: add Shadow Mode option and render `pending_review` user feedback.
- Modify `.env.example`: document Shadow Mode local defaults.
- Create `tests/test_shadow_adapter.py`: verify prefill without mutation and screenshot evidence.
- Create `tests/test_workflow_shadow_mode.py`: verify workflow state and audit behavior.
- Modify `tests/test_api.py`: verify parse/create/confirm through `shadow`.
- Modify `tests/test_static_page.py`: verify workbench Shadow Mode controls.
- Modify `README.md`: document Phase 4 local and real-backend shadow flows.
- Modify `docs/project-structure.md`: document the new adapter and evidence folder.

## Design Notes

### Adapter Mode

Use this exact string everywhere:

```python
SHADOW_ADAPTER_MODE = "shadow"
```

The UI label should be:

```text
ShadowMode
```

The UI should show the safety meaning in status text after execution:

```text
Shadow Mode 已完成预填，未提交，等待人工复核。
```

### Safety Contract

Shadow Mode must return:

```python
OperationResult(
    success=True,
    submitted=False,
    shadow_mode=True,
    evidence={...},
)
```

For Shadow Mode, `success=True` means the page was opened, the target was located, the new value was prefilled, and evidence was captured. It does not mean the merchant backend was changed.

### Workflow State

The intended shadow timeline is:

```text
created
parsed
validated
previewed
awaiting_approval
queued
session_ready
pre_snapshot_done
executing
shadow_prefilled
pending_review
```

`pending_review` is the terminal state for Phase 4 shadow execution. It is not a failure and not a committed success.

### Environment Variables

Use these names:

```text
FOOD_OPS_SHADOW_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_SHADOW_SCREENSHOT_DIR=data/demo/shadow-mode-evidence
FOOD_OPS_SHADOW_HEADLESS=1
```

There is no environment variable that enables submit clicks in Shadow Mode.

---

## Task 1: Extend Models For Shadow Evidence

**Files:**
- Modify: `food_ops_demo/models.py`
- Create: `tests/test_workflow_shadow_mode.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_workflow_shadow_mode.py`:

```python
from food_ops_demo.models import OperationResult, Task
from food_ops_demo.parser import parse_instruction


def test_operation_result_can_describe_shadow_prefill_without_submit():
    result = OperationResult(
        success=True,
        submitted=False,
        shadow_mode=True,
        evidence={
            "adapter_mode": "shadow",
            "target_url": "http://127.0.0.1:8765/mock/merchant",
            "screenshot_path": "data/demo/shadow-mode-evidence/shadow-prefill-price.png",
        },
    )

    assert result.success is True
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.evidence["adapter_mode"] == "shadow"


def test_task_can_store_shadow_evidence():
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9").plan
    task = Task(
        instruction=plan.instruction,
        plan=plan,
        adapter_mode="shadow",
        shadow_evidence={"submitted": False, "intended_price": "29.90"},
    )

    assert task.adapter_mode == "shadow"
    assert task.shadow_evidence["submitted"] is False
    assert task.shadow_evidence["intended_price"] == "29.90"
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_shadow_mode.py::test_operation_result_can_describe_shadow_prefill_without_submit tests/test_workflow_shadow_mode.py::test_task_can_store_shadow_evidence -v
```

Expected before implementation:

```text
AttributeError or validation failure for submitted, shadow_mode, evidence, or shadow_evidence
```

- [ ] **Step 3: Extend `OperationResult` and `Task`**

Modify `food_ops_demo/models.py`:

```python
class OperationResult(BaseModel):
    success: bool
    error: ErrorDetail | None = None
    submitted: bool = True
    shadow_mode: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)
```

Modify `Task`:

```python
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
    shadow_evidence: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None
    manual_intervention_type: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
```

- [ ] **Step 4: Run model tests to verify they pass**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_shadow_mode.py::test_operation_result_can_describe_shadow_prefill_without_submit tests/test_workflow_shadow_mode.py::test_task_can_store_shadow_evidence -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run existing adapter tests to verify defaults preserve current behavior**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter.py tests/test_mock_web_adapter.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 6: Commit model support**

Run:

```powershell
git add food_ops_demo/models.py tests/test_workflow_shadow_mode.py
git commit -m "feat: add shadow evidence models"
```

---

## Task 2: Add No-Submit Shadow Adapter

**Files:**
- Create: `food_ops_demo/shadow_adapter.py`
- Create: `tests/test_shadow_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/test_shadow_adapter.py`:

```python
from pathlib import Path

import pytest

from food_ops_demo.shadow_adapter import ShadowPlatformAdapter


@pytest.fixture
def mock_page_url() -> str:
    return Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri()


def test_shadow_adapter_prefills_price_without_saving(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        before = adapter.get_snapshot("人民广场店")
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
        after = adapter.get_snapshot("人民广场店")
    finally:
        adapter.close()

    assert before.items[0].price == "32.00"
    assert after.items[0].price == "32.00"
    assert result.success is True
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.evidence["adapter_mode"] == "shadow"
    assert result.evidence["operation_type"] == "menu.update_price"
    assert result.evidence["store_name"] == "人民广场店"
    assert result.evidence["target_name"] == "招牌牛肉饭"
    assert result.evidence["original_value"] == "32.00"
    assert result.evidence["intended_value"] == "29.90"
    assert Path(result.evidence["screenshot_path"]).exists()


def test_shadow_adapter_returns_not_found_without_prefill(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "不存在的菜", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.error.code == "target_not_found"
```

- [ ] **Step 2: Run adapter tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_shadow_adapter.py -v
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'food_ops_demo.shadow_adapter'
```

- [ ] **Step 3: Implement `ShadowPlatformAdapter`**

Create `food_ops_demo/shadow_adapter.py`:

```python
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from food_ops_demo.adapter import BasePlatformAdapter
from food_ops_demo.models import ErrorDetail, MenuItem, OperationResult, StoreSnapshot
from food_ops_demo.mock_web_adapter import _raw_to_snapshot


class ShadowPlatformAdapter(BasePlatformAdapter):
    def __init__(
        self,
        page_url: str,
        screenshot_dir: str | Path | None = None,
        headless: bool = True,
    ) -> None:
        self.page_url = page_url
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir else None
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None

    def get_snapshot(self, store_name: str) -> StoreSnapshot:
        page = self._ensure_page()
        raw = page.evaluate("() => window.__mockMerchant.getSnapshot()")
        snapshot = _raw_to_snapshot(raw)
        if snapshot.store_name != store_name:
            raise KeyError(store_name)
        return snapshot

    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        try:
            snapshot = self.get_snapshot(store_name)
        except KeyError:
            return []
        return [item for item in snapshot.items if item.name == item_name]

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        matches = self.find_menu_items(store_name, item_name)
        if len(matches) != 1:
            return self._shadow_error("target_not_found", "找不到目标菜品。")

        item = matches[0]
        page = self._ensure_page()
        page.locator(f'[data-testid="price-input-{item.item_id}"]').fill(price)
        screenshot_path = self._save_screenshot("shadow-prefill-price")
        return OperationResult(
            success=True,
            submitted=False,
            shadow_mode=True,
            evidence={
                "adapter_mode": "shadow",
                "operation_type": "menu.update_price",
                "target_url": self.page_url,
                "store_name": store_name,
                "target_name": item_name,
                "original_value": item.price,
                "intended_value": price,
                "screenshot_path": str(screenshot_path) if screenshot_path else "",
            },
        )

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        return self._shadow_error(
            "shadow_operation_not_supported",
            "Shadow Mode 暂不支持售卖状态预填，因为当前控件会直接提交变更。",
        )

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        if len(business_hours) != 1:
            return self._shadow_error("unsupported_business_hours", "Shadow Mode 只支持一个营业时间段预填。")
        self.get_snapshot(store_name)
        page = self._ensure_page()
        page.locator('[data-testid="business-hours-start-input"]').fill(business_hours[0]["start"])
        page.locator('[data-testid="business-hours-end-input"]').fill(business_hours[0]["end"])
        screenshot_path = self._save_screenshot("shadow-prefill-business-hours")
        return OperationResult(
            success=True,
            submitted=False,
            shadow_mode=True,
            evidence={
                "adapter_mode": "shadow",
                "operation_type": "store.update_business_hours",
                "target_url": self.page_url,
                "store_name": store_name,
                "intended_value": business_hours,
                "screenshot_path": str(screenshot_path) if screenshot_path else "",
            },
        )

    def update_store_phone(self, store_name: str, phone: str) -> OperationResult:
        snapshot = self.get_snapshot(store_name)
        page = self._ensure_page()
        page.locator('[data-testid="store-phone-input"]').fill(phone)
        screenshot_path = self._save_screenshot("shadow-prefill-phone")
        return OperationResult(
            success=True,
            submitted=False,
            shadow_mode=True,
            evidence={
                "adapter_mode": "shadow",
                "operation_type": "store.update_phone",
                "target_url": self.page_url,
                "store_name": store_name,
                "original_value": snapshot.phone,
                "intended_value": phone,
                "screenshot_path": str(screenshot_path) if screenshot_path else "",
            },
        )

    def _ensure_page(self) -> Page:
        if self._page is not None:
            return self._page
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
        self._page.goto(self.page_url)
        self._page.wait_for_load_state("load")
        return self._page

    def _save_screenshot(self, name: str) -> Path | None:
        if self.screenshot_dir is None:
            return None
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / f"{name}.png"
        self._ensure_page().screenshot(path=str(path), full_page=True)
        return path

    def _shadow_error(self, code: str, message: str) -> OperationResult:
        return OperationResult(
            success=False,
            submitted=False,
            shadow_mode=True,
            error=ErrorDetail(code=code, message=message),
        )
```

- [ ] **Step 4: Run adapter tests to verify they pass**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_shadow_adapter.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run mock web adapter tests to catch shared helper regressions**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 6: Commit shadow adapter**

Run:

```powershell
git add food_ops_demo/shadow_adapter.py tests/test_shadow_adapter.py
git commit -m "feat: add no-submit shadow adapter"
```

---

## Task 3: Teach Workflow To Finish Shadow Tasks At Pending Review

**Files:**
- Modify: `food_ops_demo/workflow.py`
- Modify: `tests/test_workflow_shadow_mode.py`

- [ ] **Step 1: Add failing workflow tests**

Append to `tests/test_workflow_shadow_mode.py`:

```python
from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import OperationResult
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.workflow import TaskManager


class RecordingShadowAdapter(FakePlatformAdapter):
    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        return OperationResult(
            success=True,
            submitted=False,
            shadow_mode=True,
            evidence={
                "adapter_mode": "shadow",
                "operation_type": "menu.update_price",
                "store_name": store_name,
                "target_name": item_name,
                "original_value": "32.00",
                "intended_value": price,
                "screenshot_path": "data/demo/shadow-mode-evidence/shadow-prefill-price.png",
            },
        )


def _shadow_price_plan(adapter):
    parsed = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    validated = validate_plan(parsed.plan, adapter)
    assert validated.plan is not None
    return validated.plan, validated.preview


def test_task_manager_stops_shadow_result_at_pending_review(tmp_path):
    adapter = RecordingShadowAdapter()
    plan, preview = _shadow_price_plan(adapter)
    manager = TaskManager(
        adapters={"shadow": adapter},
        default_adapter_mode="shadow",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="shadow")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "pending_review"
    assert completed.adapter_mode == "shadow"
    assert completed.before_snapshot["items"][0]["price"] == "32.00"
    assert completed.after_snapshot == {}
    assert completed.result["success"] is True
    assert completed.result["submitted"] is False
    assert completed.result["shadow_mode"] is True
    assert completed.shadow_evidence["intended_value"] == "29.90"
    assert [event.state for event in completed.timeline][-5:] == [
        "session_ready",
        "pre_snapshot_done",
        "executing",
        "shadow_prefilled",
        "pending_review",
    ]


def test_task_manager_keeps_fake_mode_committed_success(tmp_path):
    adapter = FakePlatformAdapter()
    plan, preview = _shadow_price_plan(adapter)
    manager = TaskManager(
        adapters={"fake": adapter},
        default_adapter_mode="fake",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="fake")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.result["submitted"] is True
    assert completed.result["shadow_mode"] is False
    assert completed.after_snapshot["items"][0]["price"] == "29.90"
```

- [ ] **Step 2: Run workflow tests to verify the shadow test fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_shadow_mode.py -v
```

Expected before implementation:

```text
AssertionError: expected pending_review but got succeeded or verification_failed
```

- [ ] **Step 3: Add a workflow helper for shadow results**

Modify `food_ops_demo/workflow.py` inside `TaskManager`:

```python
    def _complete_shadow_task(self, task: Task, result: OperationResult) -> Task:
        task.result = result.model_dump(mode="json")
        task.shadow_evidence = result.evidence
        self._set_state(task, "shadow_prefilled", "Shadow Mode 已定位并预填，未提交。")
        self._set_state(task, "pending_review", "等待人工在后台复核后决定是否手动提交。")
        self._append_audit(task)
        self._persist(task)
        return self._copy(task)
```

- [ ] **Step 4: Update `_execute` for shadow-specific states**

Modify `food_ops_demo/workflow.py` in `_execute` so committed modes keep their current order and Shadow Mode waits until the pre-submit snapshot has been captured before entering `executing`:

```python
        if not skip_queue:
            self._set_state(task, "queued", "任务已进入执行队列。")
            if task.adapter_mode == "shadow":
                self._set_state(task, "session_ready", "Shadow Mode 页面会话已就绪。")
            else:
                self._set_state(task, "executing", f"正在通过 {task.adapter_mode} 执行。")
```

After the `before_snapshot` assignment, add:

```python
        if task.adapter_mode == "shadow":
            self._set_state(task, "pre_snapshot_done", "已读取提交前快照。")
            self._set_state(task, "executing", f"正在通过 {task.adapter_mode} 执行。")
```

After `result = self._apply_plan(task.plan, adapter)`, add this before the existing `if not result.success:` branch:

```python
        if result.shadow_mode and result.success:
            return self._complete_shadow_task(task, result)
```

In the normal committed branch, preserve existing behavior but record default result fields:

```python
        task.result = {
            "success": result.success,
            "verified": verified,
            "submitted": result.submitted,
            "shadow_mode": result.shadow_mode,
        }
```

- [ ] **Step 5: Run workflow tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_shadow_mode.py tests/test_workflow_adapter_modes.py tests/test_workflow.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 6: Commit workflow shadow branch**

Run:

```powershell
git add food_ops_demo/workflow.py tests/test_workflow_shadow_mode.py
git commit -m "feat: route shadow tasks to pending review"
```

---

## Task 4: Register Shadow Mode In FastAPI

**Files:**
- Modify: `food_ops_demo/app.py`
- Modify: `.env.example`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing API test for Shadow Mode**

Append to `tests/test_api.py`:

```python
from pathlib import Path


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
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py::test_shadow_mode_parse_create_confirm_flow -v
```

Expected before implementation:

```text
TypeError: create_app() got an unexpected keyword argument 'shadow_url'
```

- [ ] **Step 3: Register `ShadowPlatformAdapter`**

Modify imports in `food_ops_demo/app.py`:

```python
from food_ops_demo.shadow_adapter import ShadowPlatformAdapter
```

Modify `create_app` signature:

```python
def create_app(
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
    shadow_url: str | None = None,
    shadow_screenshot_dir: str | Path | None = None,
) -> FastAPI:
```

Modify adapter registration:

```python
    shadow_target_url = shadow_url or os.getenv("FOOD_OPS_SHADOW_URL") or mock_url
    shadow_evidence_dir = (
        shadow_screenshot_dir
        or os.getenv("FOOD_OPS_SHADOW_SCREENSHOT_DIR")
        or "data/demo/shadow-mode-evidence"
    )
    adapters = {
        "fake": fake_adapter,
        "mock_web": MockWebAdapter(
            page_url=mock_url,
            screenshot_dir=os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", "data/demo/mock-web-screenshots"),
            headless=os.getenv("FOOD_OPS_MOCK_WEB_HEADLESS", "1") != "0",
        ),
        "shadow": ShadowPlatformAdapter(
            page_url=shadow_target_url,
            screenshot_dir=shadow_evidence_dir,
            headless=os.getenv("FOOD_OPS_SHADOW_HEADLESS", "1") != "0",
        ),
    }
```

- [ ] **Step 4: Update `.env.example`**

Modify `.env.example`:

```text
FOOD_OPS_AUDIT_PATH=data/demo/audit.jsonl
FOOD_OPS_DATABASE_PATH=data/demo/demo.sqlite3
FOOD_OPS_MOCK_WEB_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR=data/demo/mock-web-screenshots
FOOD_OPS_MOCK_WEB_HEADLESS=1
FOOD_OPS_SHADOW_URL=http://127.0.0.1:8765/mock/merchant
FOOD_OPS_SHADOW_SCREENSHOT_DIR=data/demo/shadow-mode-evidence
FOOD_OPS_SHADOW_HEADLESS=1
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 6: Commit API registration**

Run:

```powershell
git add food_ops_demo/app.py .env.example tests/test_api.py
git commit -m "feat: register shadow adapter mode"
```

---

## Task 5: Add Workbench Shadow Mode Controls

**Files:**
- Modify: `food_ops_demo/static/index.html`
- Modify: `tests/test_static_page.py`

- [ ] **Step 1: Write failing static page test**

Append to `tests/test_static_page.py`:

```python
def test_static_page_contains_shadow_mode_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'value="shadow"' in html
    assert "ShadowMode" in html
    assert "开始预填" in html
    assert "pending_review" in html
    assert "未提交" in html
```

- [ ] **Step 2: Run static page test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py::test_static_page_contains_shadow_mode_controls -v
```

Expected before implementation:

```text
AssertionError: assert 'value="shadow"' in html
```

- [ ] **Step 3: Add Shadow Mode option**

Modify the adapter mode selector in `food_ops_demo/static/index.html`:

```html
<select id="adapterMode" aria-label="执行模式">
  <option value="fake">FakeAdapter</option>
  <option value="mock_web">MockWebAdapter</option>
  <option value="shadow">ShadowMode</option>
</select>
```

- [ ] **Step 4: Add dynamic confirm button text**

In `food_ops_demo/static/index.html`, add this helper near other render helpers:

```js
function updateConfirmButtonLabel() {
  els.confirmButton.textContent = els.adapterMode.value === 'shadow' ? '开始预填' : '确认执行';
}
```

Call it after the `els` object is initialized and when the adapter mode changes:

```js
els.adapterMode.addEventListener('change', updateConfirmButtonLabel);
updateConfirmButtonLabel();
```

- [ ] **Step 5: Render `pending_review` status clearly**

In the task rendering logic that handles successful responses, add:

```js
if (task.state === 'pending_review') {
  setStatus('Shadow Mode 已完成预填，未提交，等待人工复核。');
} else if (task.state === 'succeeded') {
  setStatus('执行成功。');
}
```

In the task preview grid, keep adapter mode visible:

```js
['执行模式', task.adapter_mode || 'fake'],
```

If `task.shadow_evidence` has a screenshot path, include a compact evidence row:

```js
if (task.shadow_evidence && task.shadow_evidence.screenshot_path) {
  rows.push(['Shadow 证据', task.shadow_evidence.screenshot_path]);
}
```

- [ ] **Step 6: Run static page tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 7: Commit workbench controls**

Run:

```powershell
git add food_ops_demo/static/index.html tests/test_static_page.py
git commit -m "feat: add shadow mode workbench controls"
```

---

## Task 6: Add Safety Regression Tests

**Files:**
- Modify: `tests/test_shadow_adapter.py`
- Modify: `tests/test_workflow_shadow_mode.py`

- [ ] **Step 1: Add no-submit regression test for store phone**

Append to `tests/test_shadow_adapter.py`:

```python
def test_shadow_adapter_prefills_phone_without_saving(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        result = adapter.update_store_phone("人民广场店", "021-66668888")
        snapshot = adapter.get_snapshot("人民广场店")
    finally:
        adapter.close()

    assert result.success is True
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.evidence["operation_type"] == "store.update_phone"
    assert result.evidence["original_value"] == "021-88888888"
    assert result.evidence["intended_value"] == "021-66668888"
    assert snapshot.phone == "021-88888888"
```

- [ ] **Step 2: Add unsupported immediate-action safety test**

Append to `tests/test_shadow_adapter.py`:

```python
def test_shadow_adapter_rejects_sale_status_because_button_would_submit(mock_page_url, tmp_path):
    adapter = ShadowPlatformAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        result = adapter.update_menu_sale_status("人民广场店", "可乐", "sold_out")
        snapshot = adapter.get_snapshot("人民广场店")
    finally:
        adapter.close()

    assert result.success is False
    assert result.submitted is False
    assert result.shadow_mode is True
    assert result.error.code == "shadow_operation_not_supported"
    assert snapshot.items[1].sale_status == "on_sale"
```

- [ ] **Step 3: Add workflow test for unsupported shadow operation**

Append to `tests/test_workflow_shadow_mode.py`:

```python
class UnsupportedShadowAdapter(FakePlatformAdapter):
    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        return OperationResult(
            success=False,
            submitted=False,
            shadow_mode=True,
            error=ErrorDetail(
                code="shadow_operation_not_supported",
                message="Shadow Mode 暂不支持售卖状态预填，因为当前控件会直接提交变更。",
            ),
        )


def test_unsupported_shadow_operation_fails_without_submission(tmp_path):
    adapter = UnsupportedShadowAdapter()
    parsed = parse_instruction("把人民广场店的可乐设为售罄")
    validated = validate_plan(parsed.plan, adapter)
    assert validated.plan is not None
    manager = TaskManager(
        adapters={"shadow": adapter},
        default_adapter_mode="shadow",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(validated.plan, validated.preview, adapter_mode="shadow")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "failed"
    assert completed.error.code == "shadow_operation_not_supported"
    assert completed.result == {}
```

Add `ErrorDetail` to the existing imports in `tests/test_workflow_shadow_mode.py`:

```python
from food_ops_demo.models import ErrorDetail, OperationResult, Task
```

- [ ] **Step 4: Run safety tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_shadow_adapter.py tests/test_workflow_shadow_mode.py -v
```

Expected:

```text
All selected tests pass
```

- [ ] **Step 5: Commit safety tests**

Run:

```powershell
git add tests/test_shadow_adapter.py tests/test_workflow_shadow_mode.py
git commit -m "test: cover shadow mode no-submit safety"
```

---

## Task 7: Document Phase 4 Usage

**Files:**
- Modify: `README.md`
- Modify: `docs/project-structure.md`

- [ ] **Step 1: Update README with Phase 4 local flow**

Add this section after the Phase 3 flow in `README.md`:

```markdown
## Phase 4 Shadow Mode 演示流程

Shadow Mode 用于真实后台接入前的安全验证：系统会打开目标后台页面、读取当前数据、定位并预填目标值、截图留证，然后停在 `pending_review`。系统不会点击保存或提交。

本地演示默认指向 mock 商家后台：

```powershell
$env:FOOD_OPS_SHADOW_URL='http://127.0.0.1:8765/mock/merchant'
$env:FOOD_OPS_SHADOW_SCREENSHOT_DIR='data/demo/shadow-mode-evidence'
$env:FOOD_OPS_SHADOW_HEADLESS='1'
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765/` 后：

1. 执行模式选择 `ShadowMode`。
2. 输入 `把人民广场店的招牌牛肉饭改成 29.9`。
3. 点击 `生成计划`。
4. 点击 `开始预填`。
5. 任务状态应停在 `pending_review`。
6. `data/demo/shadow-mode-evidence/shadow-prefill-price.png` 应显示目标价格已预填为 `29.90`。
7. mock 门店快照仍应保留原价格 `32.00`，证明没有提交。

如果要指向真实后台，只修改 `FOOD_OPS_SHADOW_URL`。真实后台 Shadow Mode 仍然只预填不提交，提交动作必须由人工在后台完成或放弃。
```

- [ ] **Step 2: Update project structure document**

In `docs/project-structure.md`, add:

```markdown
- `food_ops_demo.shadow_adapter.ShadowPlatformAdapter`：Phase 4 的只读/预填适配器，通过 Playwright 打开配置的后台页面，预填低风险输入并截图，明确返回 `submitted=false`。
- `data/demo/shadow-mode-evidence/`：本地 Shadow Mode 截图证据目录，不进入 Git。
```

Update the current positioning paragraph to mention Shadow Mode:

```markdown
当前版本支持 FakeAdapter、MockWebAdapter 和 ShadowMode 三种执行模式。ShadowMode 只读取、定位、预填和截图，不点击保存或提交。
```

- [ ] **Step 3: Run documentation smoke checks**

Run:

```powershell
rg "Phase 4 Shadow Mode|ShadowMode|submitted=false|shadow-mode-evidence" README.md docs/project-structure.md
```

Expected:

```text
Matches appear in README.md and docs/project-structure.md
```

- [ ] **Step 4: Commit documentation**

Run:

```powershell
git add README.md docs/project-structure.md
git commit -m "docs: document phase 4 shadow mode"
```

---

## Task 8: Full Verification, Browser Smoke, And CodeGraph Sync

**Files:**
- No source files should be modified in this task unless verification reveals a defect.

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -q
```

Expected:

```text
All tests pass
```

- [ ] **Step 2: Restart local app with current code**

If port `8765` is occupied, inspect the process:

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Only stop the process if it is the local `food_ops_demo.asgi:app` uvicorn server:

```powershell
Stop-Process -Id <PID>
```

Start the app:

```powershell
$env:FOOD_OPS_SHADOW_URL='http://127.0.0.1:8765/mock/merchant'
$env:FOOD_OPS_SHADOW_SCREENSHOT_DIR='data/demo/shadow-mode-evidence'
$env:FOOD_OPS_SHADOW_HEADLESS='1'
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

Health check:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health'
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 3: Browser smoke test for Shadow Mode**

Open `http://127.0.0.1:8765/` in the in-app browser and verify:

- The execution mode selector contains `FakeAdapter`, `MockWebAdapter`, and `ShadowMode`.
- Selecting `ShadowMode` changes the confirm button text to `开始预填`.
- Running `把人民广场店的招牌牛肉饭改成 29.9` reaches `pending_review`.
- Task center shows the new task with `shadow`.
- The page status says `Shadow Mode 已完成预填，未提交，等待人工复核。`
- `data/demo/shadow-mode-evidence/shadow-prefill-price.png` exists.
- Opening the screenshot shows the price input prefilled with `29.90`.
- The workbench snapshot still shows the original price `32.00`.
- Browser console has no errors.

- [ ] **Step 4: Browser regression test for committed modes**

In the same browser session verify:

- `MockWebAdapter` mode can still execute `把人民广场店的招牌牛肉饭改成 29.9` and reach `succeeded`.
- `FakeAdapter` mode can still execute `把人民广场店的可乐设为售罄` and reach `succeeded`.
- Browser console has no errors after both flows.

- [ ] **Step 5: Sync CodeGraph**

Run:

```powershell
codegraph sync .
```

Expected:

```text
Done
```

Then check index health:

```powershell
codegraph status
```

Expected:

```text
The indexed Python file count includes food_ops_demo/shadow_adapter.py
```

- [ ] **Step 6: Check final git state**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected:

```text
Working tree is clean.
Recent commits include:
feat: add shadow evidence models
feat: add no-submit shadow adapter
feat: route shadow tasks to pending review
feat: register shadow adapter mode
feat: add shadow mode workbench controls
test: cover shadow mode no-submit safety
docs: document phase 4 shadow mode
```

---

## Self-Review

Spec coverage:

- Real backend Shadow Mode boundary from migrated roadmap: Tasks 2, 3, 4, 5, and 8.
- Read, locate, prefill, no submit: Tasks 2, 3, and 6.
- Evidence capture and audit persistence: Tasks 1, 2, 3, 4, and 8.
- UI mode selection and user-visible `pending_review`: Task 5.
- Safety regression for direct-submit controls: Task 6.
- Documentation and local run instructions: Task 7.
- Full verification and CodeGraph sync: Task 8.

Placeholder scan:

- No unresolved marker text is used.
- Each task names exact files, tests, commands, expected failures, expected passes, and commit messages.
- Code-changing steps include concrete snippets for the intended implementation.

Type consistency:

- Adapter mode uses `shadow`.
- `OperationResult.submitted` defaults to `True` for existing adapters.
- `OperationResult.shadow_mode` defaults to `False` for existing adapters.
- `Task.shadow_evidence` is a dictionary and mirrors `OperationResult.evidence` for shadow tasks.
- `TaskManager` uses `pending_review` as the terminal shadow state.
- Shadow adapter returns `submitted=False` for both success and failure paths.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-phase-4-shadow-mode.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
