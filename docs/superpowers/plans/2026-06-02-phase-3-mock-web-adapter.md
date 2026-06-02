# Phase 3 Mock Web Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local simulated merchant backend and a Playwright-driven `MockWebAdapter` so the existing operation workflow can execute real browser interactions before any real platform integration.

**Architecture:** Keep the existing parser, risk validation, task state machine, SQLite persistence, and adapter contract boundary. Add a separate mock merchant page under the same FastAPI app, implement `MockWebAdapter` behind `BasePlatformAdapter`, and let API/UI choose execution mode per task while preserving `fake` as the default. Browser automation remains local-only and deterministic.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, sqlite3, pytest, Playwright Python sync API, vanilla HTML/CSS/JS.

---

## Scope

Build these user-facing and developer-facing capabilities:

- Serve a local mock merchant backend page at `/mock/merchant`.
- Drive that mock backend through Playwright using a new `MockWebAdapter`.
- Keep the current `FakePlatformAdapter` path working and default.
- Allow the workbench/API to choose `fake` or `mock_web` execution mode per task.
- Extend adapter contract tests so memory fake, SQLite fake, and mock web modes are all checked where applicable.
- Add deterministic screenshot/DOM verification for the mock web execution path.
- Add small, local fault-injection cases for auth-required and save-failed behavior.
- Document how to install Playwright browser dependencies and run the Phase 3 demo.

Do not build:

- Real external merchant-platform connectors.
- Real login, captcha solving, SMS verification, or QR-code scanning.
- Cross-store batch execution.
- Real LLM parsing.
- React/Vite or a frontend build system.
- Production-grade Playwright trace storage.

## File Structure

- Modify `pyproject.toml`: add Playwright to dev dependencies.
- Create `tests/test_playwright_dependency.py`: verify Playwright sync API import.
- Create `food_ops_demo/static/mock_merchant.html`: local mock merchant backend page.
- Modify `food_ops_demo/app.py`: serve `/mock/merchant`, accept adapter mode in API requests, and wire adapter registry.
- Create `food_ops_demo/mock_web_adapter.py`: Playwright-backed adapter implementing `BasePlatformAdapter`.
- Modify `food_ops_demo/models.py`: persist `Task.adapter_mode`.
- Modify `food_ops_demo/workflow.py`: route execution through the adapter selected for each task and handle auth-required failures.
- Modify `food_ops_demo/static/index.html`: add execution-mode selector and pass adapter mode to parse/create APIs.
- Modify `tests/test_static_page.py`: verify mode selector and mock backend link/control.
- Create `tests/test_mock_merchant_page.py`: static and route tests for mock backend page.
- Create `tests/test_mock_web_adapter.py`: Playwright adapter tests.
- Modify `tests/test_adapter_contract.py`: include `mock_web` adapter contract cases.
- Create `tests/test_workflow_adapter_modes.py`: verify per-task adapter routing.
- Modify `tests/test_api.py`: verify `adapter_mode` request/response behavior.
- Modify `README.md`: document Phase 3 install and demo flow.
- Modify `docs/project-structure.md`: add Phase 3 module responsibilities.

## Phase 3 Design Notes

### Adapter Modes

Use these mode strings everywhere:

```python
FAKE_ADAPTER_MODE = "fake"
MOCK_WEB_ADAPTER_MODE = "mock_web"
```

The API and UI default to `fake`, so existing callers continue to work. `mock_web` is opt-in.

### Mock Web URL

In the running app, `MockWebAdapter` should default to:

```text
http://127.0.0.1:8765/mock/merchant
```

Tests should pass a `file://` URL or local test URL explicitly so they do not depend on a long-running server.

### Playwright Installation

After adding the dependency, the developer must run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pip install -e ".[dev]"
& 'E:\anaconda\envs\jobhellper\python.exe' -m playwright install chromium
```

All test commands below use:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest ...
```

---

## Task 1: Add Playwright Dev Dependency

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_playwright_dependency.py`

- [ ] **Step 1: Write the failing dependency test**

Create `tests/test_playwright_dependency.py`:

```python
def test_playwright_sync_api_is_available():
    from playwright.sync_api import sync_playwright

    assert callable(sync_playwright)
```

- [ ] **Step 2: Run the dependency test to verify it fails before dependency installation**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_playwright_dependency.py -v
```

Expected before dependency installation:

```text
ModuleNotFoundError: No module named 'playwright'
```

If Playwright is already installed in the Conda environment, this test may pass immediately. In that case, still add the dependency to `pyproject.toml` so future environments are reproducible.

- [ ] **Step 3: Add Playwright to dev dependencies**

Modify `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "httpx>=0.27,<1.0",
  "pytest>=8.0,<9.0",
  "playwright>=1.49,<2.0",
]
```

- [ ] **Step 4: Install dev dependencies and Chromium**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pip install -e ".[dev]"
& 'E:\anaconda\envs\jobhellper\python.exe' -m playwright install chromium
```

Expected: both commands complete successfully. If Chromium is already installed, Playwright may report that the browser is already present.

- [ ] **Step 5: Run the dependency test to verify it passes**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_playwright_dependency.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit Playwright dependency**

Run:

```powershell
git add pyproject.toml tests/test_playwright_dependency.py
git commit -m "test: add playwright dependency check"
```

---

## Task 2: Add Local Mock Merchant Backend Page

**Files:**
- Create: `food_ops_demo/static/mock_merchant.html`
- Modify: `food_ops_demo/app.py`
- Create: `tests/test_mock_merchant_page.py`

- [ ] **Step 1: Write failing tests for the mock backend route and page contract**

Create `tests/test_mock_merchant_page.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from food_ops_demo.app import create_app


def test_mock_merchant_page_file_contains_required_controls():
    html = Path("food_ops_demo/static/mock_merchant.html").read_text(encoding="utf-8")

    assert 'id="mockMerchantApp"' in html
    assert 'data-testid="store-phone-input"' in html
    assert 'data-testid="business-hours-start-input"' in html
    assert 'data-testid="business-hours-end-input"' in html
    assert 'data-testid="item-row-item_001"' in html
    assert 'data-testid="item-row-item_002"' in html
    assert 'data-testid="item-row-item_003"' in html
    assert "window.__mockMerchant.getSnapshot" in html
    assert "window.__mockMerchant.setScenario" in html


def test_mock_merchant_route_serves_page(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    response = client.get("/mock/merchant")

    assert response.status_code == 200
    assert "Mock 商家后台" in response.text
    assert 'data-testid="save-phone-button"' in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_merchant_page.py -v
```

Expected:

```text
FileNotFoundError: food_ops_demo/static/mock_merchant.html
```

- [ ] **Step 3: Add the mock merchant page**

Create `food_ops_demo/static/mock_merchant.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mock 商家后台</title>
  <style>
    :root {
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: #172033;
      background: #f5f7fb;
    }
    body {
      margin: 0;
      padding: 24px;
    }
    main {
      max-width: 1080px;
      margin: 0 auto;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    section {
      background: #fff;
      border: 1px solid #dfe5ee;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      border-bottom: 1px solid #e8edf5;
      padding: 10px;
      text-align: left;
      vertical-align: middle;
    }
    input {
      border: 1px solid #cfd7e3;
      border-radius: 6px;
      padding: 8px;
      min-width: 120px;
    }
    button {
      border: 1px solid #ccd6e2;
      border-radius: 6px;
      background: #fff;
      padding: 8px 10px;
      cursor: pointer;
    }
    button.primary {
      background: #0b74de;
      border-color: #0b74de;
      color: #fff;
    }
    .status {
      min-height: 24px;
      color: #0f5132;
      font-weight: 600;
    }
    .error {
      color: #b42318;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
  </style>
</head>
<body>
  <main id="mockMerchantApp">
    <header>
      <div>
        <h1>Mock 商家后台</h1>
        <div data-testid="store-name">人民广场店</div>
      </div>
      <div data-testid="mock-status" class="status">就绪</div>
    </header>

    <section aria-labelledby="store-settings-title">
      <h2 id="store-settings-title">门店设置</h2>
      <label>
        联系电话
        <input data-testid="store-phone-input" value="021-88888888">
      </label>
      <button data-testid="save-phone-button" class="primary" type="button">保存电话</button>

      <label>
        开始时间
        <input data-testid="business-hours-start-input" value="09:30">
      </label>
      <label>
        结束时间
        <input data-testid="business-hours-end-input" value="21:30">
      </label>
      <button data-testid="save-hours-button" class="primary" type="button">保存营业时间</button>
    </section>

    <section aria-labelledby="menu-title">
      <h2 id="menu-title">菜单管理</h2>
      <table>
        <thead>
          <tr>
            <th>菜品</th>
            <th>价格</th>
            <th>售卖状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="menuRows"></tbody>
      </table>
    </section>
  </main>

  <script>
    const seedStore = {
      store_id: 'store_001',
      store_name: '人民广场店',
      phone: '021-88888888',
      business_hours: [{ start: '09:30', end: '21:30' }],
      items: [
        { item_id: 'item_001', store_id: 'store_001', name: '招牌牛肉饭', price: '32.00', sale_status: 'on_sale', image: 'beef_rice.jpg' },
        { item_id: 'item_002', store_id: 'store_001', name: '可乐', price: '6.00', sale_status: 'on_sale', image: 'cola.jpg' },
        { item_id: 'item_003', store_id: 'store_001', name: '宫保鸡丁', price: '28.00', sale_status: 'on_sale', image: 'kung_pao_chicken.jpg' },
      ],
    };

    const state = {
      store: structuredClone(seedStore),
      scenario: new URLSearchParams(window.location.search).get('scenario') || 'normal',
    };

    function setStatus(text, isError = false) {
      const node = document.querySelector('[data-testid="mock-status"]');
      node.textContent = text;
      node.classList.toggle('error', isError);
    }

    function maybeBlockSave() {
      if (state.scenario === 'auth_required') {
        setStatus('登录已过期，请人工处理。', true);
        return 'auth_required';
      }
      if (state.scenario === 'save_failure') {
        setStatus('保存失败，请稍后重试。', true);
        return 'save_failure';
      }
      return null;
    }

    function renderMenu() {
      const rows = state.store.items.map((item) => `
        <tr data-testid="item-row-${item.item_id}" data-item-id="${item.item_id}" data-item-name="${item.name}">
          <td>${item.name}</td>
          <td><input data-testid="price-input-${item.item_id}" value="${item.price}"></td>
          <td data-testid="sale-status-${item.item_id}">${item.sale_status}</td>
          <td>
            <div class="actions">
              <button data-testid="save-price-${item.item_id}" type="button" data-action="save-price" data-item-id="${item.item_id}">保存价格</button>
              <button data-testid="status-on_sale-${item.item_id}" type="button" data-action="status" data-status="on_sale" data-item-id="${item.item_id}">恢复销售</button>
              <button data-testid="status-off_sale-${item.item_id}" type="button" data-action="status" data-status="off_sale" data-item-id="${item.item_id}">下架</button>
              <button data-testid="status-sold_out-${item.item_id}" type="button" data-action="status" data-status="sold_out" data-item-id="${item.item_id}">设为售罄</button>
            </div>
          </td>
        </tr>
      `).join('');
      document.getElementById('menuRows').innerHTML = rows;
    }

    function getSnapshot() {
      return structuredClone(state.store);
    }

    function findItem(itemId) {
      return state.store.items.find((item) => item.item_id === itemId);
    }

    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      const blocked = maybeBlockSave();
      if (blocked) {
        return;
      }
      if (target.dataset.testid === 'save-phone-button') {
        state.store.phone = document.querySelector('[data-testid="store-phone-input"]').value;
        setStatus('电话已保存。');
        return;
      }
      if (target.dataset.testid === 'save-hours-button') {
        state.store.business_hours = [{
          start: document.querySelector('[data-testid="business-hours-start-input"]').value,
          end: document.querySelector('[data-testid="business-hours-end-input"]').value,
        }];
        setStatus('营业时间已保存。');
        return;
      }
      if (target.dataset.action === 'save-price') {
        const item = findItem(target.dataset.itemId);
        item.price = document.querySelector(`[data-testid="price-input-${item.item_id}"]`).value;
        setStatus('价格已保存。');
        renderMenu();
        return;
      }
      if (target.dataset.action === 'status') {
        const item = findItem(target.dataset.itemId);
        item.sale_status = target.dataset.status;
        setStatus('售卖状态已保存。');
        renderMenu();
      }
    });

    window.__mockMerchant = {
      getSnapshot,
      setScenario(nextScenario) {
        state.scenario = nextScenario;
        setStatus(`场景：${nextScenario}`);
      },
      reset() {
        state.store = structuredClone(seedStore);
        state.scenario = 'normal';
        document.querySelector('[data-testid="store-phone-input"]').value = state.store.phone;
        document.querySelector('[data-testid="business-hours-start-input"]').value = state.store.business_hours[0].start;
        document.querySelector('[data-testid="business-hours-end-input"]').value = state.store.business_hours[0].end;
        renderMenu();
        setStatus('就绪');
      },
    };

    renderMenu();
  </script>
</body>
</html>
```

- [ ] **Step 4: Add the FastAPI route**

Modify `food_ops_demo/app.py` inside `create_app()` after the root route:

```python
    mock_merchant_page = Path(__file__).parent / "static" / "mock_merchant.html"

    @app.get("/mock/merchant", response_class=HTMLResponse)
    def mock_merchant() -> str:
        return mock_merchant_page.read_text(encoding="utf-8")
```

Keep the existing `static_page` variable and `/` route unchanged.

- [ ] **Step 5: Run route/page tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_merchant_page.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit mock backend page**

Run:

```powershell
git add food_ops_demo/app.py food_ops_demo/static/mock_merchant.html tests/test_mock_merchant_page.py
git commit -m "feat: add mock merchant backend page"
```

---

## Task 3: Add MockWebAdapter Snapshot And Price Update

**Files:**
- Create: `food_ops_demo/mock_web_adapter.py`
- Create: `tests/test_mock_web_adapter.py`

- [ ] **Step 1: Write failing Playwright adapter tests**

Create `tests/test_mock_web_adapter.py`:

```python
from pathlib import Path

import pytest

from food_ops_demo.mock_web_adapter import MockWebAdapter


@pytest.fixture
def mock_page_url() -> str:
    return Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri()


@pytest.fixture
def adapter(mock_page_url):
    adapter = MockWebAdapter(page_url=mock_page_url, headless=True)
    try:
        yield adapter
    finally:
        adapter.close()


def test_mock_web_adapter_reads_seed_snapshot(adapter):
    snapshot = adapter.get_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.phone == "021-88888888"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


def test_mock_web_adapter_updates_price_through_page(adapter):
    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    item = adapter.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert result.success is True
    assert item.price == "29.90"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'food_ops_demo.mock_web_adapter'
```

- [ ] **Step 3: Implement minimal MockWebAdapter**

Create `food_ops_demo/mock_web_adapter.py`:

```python
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from food_ops_demo.adapter import BasePlatformAdapter
from food_ops_demo.models import ErrorDetail, MenuItem, OperationResult, StoreSnapshot


class MockWebAdapter(BasePlatformAdapter):
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
        payload = page.evaluate("() => window.__mockMerchant.getSnapshot()")
        snapshot = StoreSnapshot.model_validate(payload)
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
        item = self._find_one(store_name, item_name)
        if item is None:
            return _not_found()
        page = self._ensure_page()
        page.locator(f'[data-testid="price-input-{item.item_id}"]').fill(price)
        page.locator(f'[data-testid="save-price-{item.item_id}"]').click()
        return self._result_from_status()

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        return _unsupported("menu.update_sale_status")

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        return _unsupported("store.update_business_hours")

    def update_store_phone(self, store_name: str, phone: str) -> OperationResult:
        return _unsupported("store.update_phone")

    def _ensure_page(self) -> Page:
        if self._page is not None:
            return self._page
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
        self._page.goto(self.page_url)
        self._page.wait_for_load_state("load")
        return self._page

    def _find_one(self, store_name: str, item_name: str) -> MenuItem | None:
        matches = self.find_menu_items(store_name, item_name)
        return matches[0] if len(matches) == 1 else None

    def _result_from_status(self) -> OperationResult:
        page = self._ensure_page()
        status = page.locator('[data-testid="mock-status"]').inner_text()
        if "登录已过期" in status:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="auth_required", message="Mock 后台登录已过期，需要人工处理。"),
            )
        if "保存失败" in status:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="mock_save_failed", message="Mock 后台保存失败。"),
            )
        self._save_screenshot("last-success")
        return OperationResult(success=True)

    def _save_screenshot(self, name: str) -> None:
        if self.screenshot_dir is None:
            return
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_page().screenshot(path=str(self.screenshot_dir / f"{name}.png"), full_page=True)


def _not_found() -> OperationResult:
    return OperationResult(
        success=False,
        error=ErrorDetail(code="target_not_found", message="找不到目标菜品。"),
    )


def _unsupported(operation_type: str) -> OperationResult:
    return OperationResult(
        success=False,
        error=ErrorDetail(code="unsupported_operation", message=f"MockWebAdapter 暂不支持操作类型：{operation_type}"),
    )
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit MockWebAdapter price path**

Run:

```powershell
git add food_ops_demo/mock_web_adapter.py tests/test_mock_web_adapter.py
git commit -m "feat: add mock web adapter price path"
```

---

## Task 4: Complete MockWebAdapter Operations And Contract Tests

**Files:**
- Modify: `food_ops_demo/mock_web_adapter.py`
- Modify: `tests/test_mock_web_adapter.py`
- Modify: `tests/test_adapter_contract.py`

- [ ] **Step 1: Add failing tests for sale status, phone, hours, and screenshot**

Append to `tests/test_mock_web_adapter.py`:

```python
def test_mock_web_adapter_updates_sale_status_through_page(adapter):
    result = adapter.update_menu_sale_status("人民广场店", "可乐", "sold_out")
    item = adapter.find_menu_items("人民广场店", "可乐")[0]

    assert result.success is True
    assert item.sale_status == "sold_out"


def test_mock_web_adapter_updates_store_phone_through_page(adapter):
    result = adapter.update_store_phone("人民广场店", "021-66668888")
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.phone == "021-66668888"


def test_mock_web_adapter_updates_business_hours_through_page(adapter):
    result = adapter.update_business_hours("人民广场店", [{"start": "10:00", "end": "21:00"}])
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.business_hours == [{"start": "10:00", "end": "21:00"}]


def test_mock_web_adapter_saves_screenshot_after_success(mock_page_url, tmp_path):
    adapter = MockWebAdapter(page_url=mock_page_url, screenshot_dir=tmp_path, headless=True)
    try:
        adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert (tmp_path / "last-success.png").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py::test_mock_web_adapter_updates_sale_status_through_page tests/test_mock_web_adapter.py::test_mock_web_adapter_updates_store_phone_through_page tests/test_mock_web_adapter.py::test_mock_web_adapter_updates_business_hours_through_page tests/test_mock_web_adapter.py::test_mock_web_adapter_saves_screenshot_after_success -v
```

Expected: fail because these methods still return `unsupported_operation` or screenshot is not written for all paths.

- [ ] **Step 3: Implement remaining MockWebAdapter operations**

Replace the three unsupported methods in `food_ops_demo/mock_web_adapter.py` with:

```python
    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        item = self._find_one(store_name, item_name)
        if item is None:
            return _not_found()
        if sale_status not in {"on_sale", "off_sale", "sold_out"}:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="invalid_sale_status", message=f"不支持售卖状态：{sale_status}"),
            )
        page = self._ensure_page()
        page.locator(f'[data-testid="status-{sale_status}-{item.item_id}"]').click()
        return self._result_from_status()

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        if len(business_hours) != 1:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="unsupported_business_hours", message="Mock 后台只支持一个营业时间段。"),
            )
        self.get_snapshot(store_name)
        page = self._ensure_page()
        page.locator('[data-testid="business-hours-start-input"]').fill(business_hours[0]["start"])
        page.locator('[data-testid="business-hours-end-input"]').fill(business_hours[0]["end"])
        page.locator('[data-testid="save-hours-button"]').click()
        return self._result_from_status()

    def update_store_phone(self, store_name: str, phone: str) -> OperationResult:
        self.get_snapshot(store_name)
        page = self._ensure_page()
        page.locator('[data-testid="store-phone-input"]').fill(phone)
        page.locator('[data-testid="save-phone-button"]').click()
        return self._result_from_status()
```

- [ ] **Step 4: Extend adapter contract test fixture with mock web mode**

Modify `tests/test_adapter_contract.py`:

```python
from pathlib import Path

import pytest

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.mock_web_adapter import MockWebAdapter
from food_ops_demo.storage import DemoDatabase


@pytest.fixture(params=["memory", "sqlite", "mock_web"])
def adapter(request, tmp_path):
    if request.param == "memory":
        yield FakePlatformAdapter()
        return
    if request.param == "sqlite":
        yield FakePlatformAdapter(database=DemoDatabase(tmp_path / "demo.sqlite3"))
        return

    adapter = MockWebAdapter(
        page_url=Path("food_ops_demo/static/mock_merchant.html").resolve().as_uri(),
        screenshot_dir=tmp_path / "screenshots",
        headless=True,
    )
    try:
        yield adapter
    finally:
        adapter.close()
```

Leave the existing contract test functions in place.

- [ ] **Step 5: Run mock web and contract tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py tests/test_adapter_contract.py -v
```

Expected:

```text
All tests pass
```

- [ ] **Step 6: Commit completed MockWebAdapter contract**

Run:

```powershell
git add food_ops_demo/mock_web_adapter.py tests/test_mock_web_adapter.py tests/test_adapter_contract.py
git commit -m "feat: complete mock web adapter contract"
```

---

## Task 5: Route Tasks By Adapter Mode

**Files:**
- Modify: `food_ops_demo/models.py`
- Modify: `food_ops_demo/workflow.py`
- Modify: `food_ops_demo/app.py`
- Create: `tests/test_workflow_adapter_modes.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing workflow tests for per-task adapter mode**

Create `tests/test_workflow_adapter_modes.py`:

```python
from __future__ import annotations

from food_ops_demo.adapter import BasePlatformAdapter, FakePlatformAdapter
from food_ops_demo.audit import AuditLog
from food_ops_demo.models import ErrorDetail, OperationResult
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.workflow import TaskManager


class RecordingAdapter(FakePlatformAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.price_updates: list[tuple[str, str, str]] = []

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        self.price_updates.append((store_name, item_name, price))
        return super().update_menu_price(store_name, item_name, price)


def _validated_price_plan(adapter: BasePlatformAdapter):
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9").plan
    result = validate_plan(plan, adapter)
    assert result.plan is not None
    return result.plan, result.preview


def test_task_manager_routes_execution_to_task_adapter_mode(tmp_path):
    fake = RecordingAdapter()
    mock_web = RecordingAdapter()
    plan, preview = _validated_price_plan(mock_web)
    manager = TaskManager(
        adapters={"fake": fake, "mock_web": mock_web},
        default_adapter_mode="fake",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="mock_web")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.adapter_mode == "mock_web"
    assert fake.price_updates == []
    assert mock_web.price_updates == [("人民广场店", "招牌牛肉饭", "29.90")]


def test_task_manager_rejects_unknown_adapter_mode(tmp_path):
    fake = RecordingAdapter()
    plan, preview = _validated_price_plan(fake)
    manager = TaskManager(adapters={"fake": fake}, audit_log=AuditLog(tmp_path / "audit.jsonl"))

    task = manager.create_task(plan, preview, adapter_mode="missing")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "failed"
    assert completed.error.code == "adapter_mode_not_found"
```

- [ ] **Step 2: Run workflow adapter-mode tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_adapter_modes.py -v
```

Expected: fail because `TaskManager` does not accept `adapters`, `default_adapter_mode`, or `adapter_mode`.

- [ ] **Step 3: Add adapter mode to Task model**

Modify `food_ops_demo/models.py` in `class Task`:

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
    error: ErrorDetail | None = None
    manual_intervention_type: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
```

- [ ] **Step 4: Modify TaskManager to support adapter registry**

Modify `food_ops_demo/workflow.py`.

Change `__init__` signature and body:

```python
    def __init__(
        self,
        adapter: BasePlatformAdapter | None = None,
        audit_log: AuditLog | None = None,
        database: DemoDatabase | None = None,
        adapters: dict[str, BasePlatformAdapter] | None = None,
        default_adapter_mode: str = "fake",
    ) -> None:
        default_adapter = adapter or FakePlatformAdapter(database=database)
        self.adapters = adapters or {default_adapter_mode: default_adapter}
        self.default_adapter_mode = default_adapter_mode
        self.adapter = self.adapters[self.default_adapter_mode]
        self.audit_log = audit_log or AuditLog(Path("data/demo/audit.jsonl"))
        self.database = database
        self._tasks: dict[str, Task] = {}
```

Change `create_task`:

```python
    def create_task(self, plan: OperationPlan, preview: dict[str, Any], adapter_mode: str | None = None) -> Task:
        task = Task(
            instruction=plan.instruction,
            plan=plan,
            preview=preview,
            adapter_mode=adapter_mode or self.default_adapter_mode,
        )
        for state, message in [
            ("created", "任务已创建。"),
            ("parsed", "指令已解析为标准操作计划。"),
            ("validated", "风险规则已校验。"),
            ("previewed", "变更预览已生成。"),
            ("awaiting_approval", "等待人工确认。"),
        ]:
            self._set_state(task, state, message)
        self._tasks[task.task_id] = task
        self._persist(task)
        return self._copy(task)
```

Add helper:

```python
    def _adapter_for(self, task: Task) -> BasePlatformAdapter | None:
        return self.adapters.get(task.adapter_mode)
```

Update `_execute` to use the selected adapter:

```python
    def _execute(self, task: Task, skip_queue: bool = False) -> Task:
        adapter = self._adapter_for(task)
        if adapter is None:
            self._fail(task, "adapter_mode_not_found", f"找不到执行模式：{task.adapter_mode}")
            self._persist(task)
            return self._copy(task)

        if not skip_queue:
            self._set_state(task, "queued", "任务已进入执行队列。")
            self._set_state(task, "executing", f"正在通过 {task.adapter_mode} 执行。")

        try:
            task.before_snapshot = adapter.get_snapshot(task.plan.store_name).model_dump(mode="json")
        except KeyError:
            self._fail(task, "store_not_found", f"找不到门店：{task.plan.store_name}")
            self._append_audit(task)
            self._persist(task)
            return self._copy(task)

        result = self._apply_plan(task.plan, adapter)
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
        task.result = {"success": result.success, "verified": verified}
        if verified:
            self._set_state(task, "succeeded", "任务执行成功，回读校验通过。")
        else:
            self._fail(task, "verification_failed", "执行后回读校验未通过。")
        self._append_audit(task)
        self._persist(task)
        return self._copy(task)
```

Change `_apply_plan` signature:

```python
    def _apply_plan(self, plan: OperationPlan, adapter: BasePlatformAdapter) -> OperationResult:
```

Inside `_apply_plan`, replace `self.adapter` with `adapter`.

- [ ] **Step 5: Add failing API tests for adapter mode**

Append to `tests/test_api.py`:

```python
def test_parse_and_create_task_accept_adapter_mode(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))

    parsed = client.post(
        "/api/demo/parse",
        json={"text": "把人民广场店的招牌牛肉饭改成 29.9", "adapter_mode": "fake"},
    ).json()
    created = client.post(
        "/api/demo/tasks",
        json={"plan": parsed["plan"], "preview": parsed["preview"], "adapter_mode": "fake"},
    ).json()

    assert created["adapter_mode"] == "fake"
```

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py::test_parse_and_create_task_accept_adapter_mode -v
```

Expected: fail because request models do not accept or use `adapter_mode`.

- [ ] **Step 6: Wire adapter mode in app API**

Modify imports in `food_ops_demo/app.py`:

```python
from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.mock_web_adapter import MockWebAdapter
```

Modify request models:

```python
class ParseRequest(BaseModel):
    text: str
    adapter_mode: str = "fake"


class CreateTaskRequest(BaseModel):
    plan: OperationPlan
    preview: dict[str, Any] = Field(default_factory=dict)
    adapter_mode: str = "fake"
```

Modify `create_app` signature:

```python
def create_app(
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
) -> FastAPI:
```

Create adapters before `TaskManager`:

```python
    database = DemoDatabase(database_path or os.getenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3"))
    fake_adapter = FakePlatformAdapter(database=database)
    mock_url = mock_web_url or os.getenv("FOOD_OPS_MOCK_WEB_URL", "http://127.0.0.1:8765/mock/merchant")
    adapters = {
        "fake": fake_adapter,
        "mock_web": MockWebAdapter(
            page_url=mock_url,
            screenshot_dir=os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", "data/demo/mock-web-screenshots"),
            headless=os.getenv("FOOD_OPS_MOCK_WEB_HEADLESS", "1") != "0",
        ),
    }
    adapter = fake_adapter
    audit_log = AuditLog(audit_path or os.getenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl"))
    manager = TaskManager(
        adapter=fake_adapter,
        adapters=adapters,
        default_adapter_mode="fake",
        audit_log=audit_log,
        database=database,
    )
```

Change parse route:

```python
    @app.post("/api/demo/parse")
    def parse(payload: ParseRequest) -> dict[str, Any]:
        selected_adapter = adapters.get(payload.adapter_mode)
        if selected_adapter is None:
            return {
                "plan": None,
                "preview": {},
                "errors": [{"code": "adapter_mode_not_found", "message": f"找不到执行模式：{payload.adapter_mode}"}],
            }
        parsed = parse_instruction(payload.text)
        if parsed.errors or parsed.plan is None:
            return {"plan": None, "preview": {}, "errors": [error.model_dump(mode="json") for error in parsed.errors]}

        validated = validate_plan(parsed.plan, selected_adapter)
        return {
            "plan": validated.plan.model_dump(mode="json") if validated.plan else None,
            "preview": validated.preview,
            "errors": [error.model_dump(mode="json") for error in validated.errors],
        }
```

Change create task route:

```python
    @app.post("/api/demo/tasks")
    def create_task(payload: CreateTaskRequest) -> dict[str, Any]:
        task = manager.create_task(payload.plan, payload.preview, adapter_mode=payload.adapter_mode)
        return task.model_dump(mode="json")
```

- [ ] **Step 7: Run workflow and API tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow.py tests/test_workflow_adapter_modes.py tests/test_api.py -v
```

Expected:

```text
All tests pass
```

- [ ] **Step 8: Commit adapter-mode routing**

Run:

```powershell
git add food_ops_demo/models.py food_ops_demo/workflow.py food_ops_demo/app.py tests/test_workflow_adapter_modes.py tests/test_api.py
git commit -m "feat: route tasks by adapter mode"
```

---

## Task 6: Add Workbench Adapter Mode Controls

**Files:**
- Modify: `food_ops_demo/static/index.html`
- Modify: `tests/test_static_page.py`

- [ ] **Step 1: Write failing static page test**

Append to `tests/test_static_page.py`:

```python
def test_static_page_contains_adapter_mode_controls():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'id="adapterMode"' in html
    assert 'value="fake"' in html
    assert 'value="mock_web"' in html
    assert "FakeAdapter" in html
    assert "MockWebAdapter" in html
```

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py::test_static_page_contains_adapter_mode_controls -v
```

Expected: fail because `adapterMode` is not present.

- [ ] **Step 2: Add execution mode selector to the command panel**

Modify `food_ops_demo/static/index.html` near the instruction input:

```html
<label for="adapterMode">执行模式</label>
<select id="adapterMode">
  <option value="fake">FakeAdapter</option>
  <option value="mock_web">MockWebAdapter</option>
</select>
<a href="/mock/merchant" target="_blank" rel="noreferrer">打开 Mock 后台</a>
```

Add `adapterMode` to the `els` object:

```js
adapterMode: document.getElementById('adapterMode'),
```

- [ ] **Step 3: Pass adapter mode to parse and create APIs**

In `parseAndCreateTask()`, build payloads like this:

```js
const adapterMode = els.adapterMode.value;
const parsed = await request('/api/demo/parse', {
  method: 'POST',
  body: JSON.stringify({ text: els.instruction.value, adapter_mode: adapterMode }),
});
if (parsed.errors.length) {
  renderErrors(parsed.errors);
  return;
}
const task = await request('/api/demo/tasks', {
  method: 'POST',
  body: JSON.stringify({ plan: parsed.plan, preview: parsed.preview, adapter_mode: adapterMode }),
});
state.taskId = task.task_id;
state.taskState = task.state;
renderTask(task);
await loadTasks();
setStatus('计划已生成，等待确认。');
```

- [ ] **Step 4: Show adapter mode in task rendering**

In task preview and task cards, include `task.adapter_mode || 'fake'`.

For the operation-plan details, add:

```js
['执行模式', task.adapter_mode || 'fake'],
```

For recent task cards, include:

```html
<span>${task.adapter_mode || 'fake'}</span>
```

- [ ] **Step 5: Run static page tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py -v
```

Expected:

```text
All tests pass
```

- [ ] **Step 6: Commit UI mode selector**

Run:

```powershell
git add food_ops_demo/static/index.html tests/test_static_page.py
git commit -m "feat: add workbench adapter mode selector"
```

---

## Task 7: Add Mock Web Fault Injection

**Files:**
- Modify: `food_ops_demo/mock_web_adapter.py`
- Modify: `food_ops_demo/workflow.py`
- Modify: `tests/test_mock_web_adapter.py`
- Modify: `tests/test_workflow_adapter_modes.py`

- [ ] **Step 1: Add failing adapter fault tests**

Append to `tests/test_mock_web_adapter.py`:

```python
def test_mock_web_adapter_reports_auth_required(mock_page_url):
    adapter = MockWebAdapter(page_url=f"{mock_page_url}?scenario=auth_required", headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.error.code == "auth_required"


def test_mock_web_adapter_reports_save_failure(mock_page_url):
    adapter = MockWebAdapter(page_url=f"{mock_page_url}?scenario=save_failure", headless=True)
    try:
        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    finally:
        adapter.close()

    assert result.success is False
    assert result.error.code == "mock_save_failed"
```

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py::test_mock_web_adapter_reports_auth_required tests/test_mock_web_adapter.py::test_mock_web_adapter_reports_save_failure -v
```

Expected: fail if status parsing or scenario handling is not wired correctly.

- [ ] **Step 2: Add failing workflow test for auth-required mapping**

Append to `tests/test_workflow_adapter_modes.py`:

```python
class AuthRequiredAdapter(RecordingAdapter):
    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        return OperationResult(
            success=False,
            error=ErrorDetail(code="auth_required", message="Mock 后台登录已过期，需要人工处理。"),
        )


def test_task_manager_maps_auth_required_to_manual_required(tmp_path):
    adapter = AuthRequiredAdapter()
    plan, preview = _validated_price_plan(adapter)
    manager = TaskManager(
        adapters={"mock_web": adapter},
        default_adapter_mode="mock_web",
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )

    task = manager.create_task(plan, preview, adapter_mode="mock_web")
    completed = manager.confirm_task(task.task_id)

    assert completed.state == "manual_required"
    assert completed.manual_intervention_type == "auth_required"
    assert completed.error.code == "auth_required"
```

- [ ] **Step 3: Run workflow fault test**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow_adapter_modes.py::test_task_manager_maps_auth_required_to_manual_required -v
```

Expected: fail if auth-required still becomes `failed`.

- [ ] **Step 4: Implement fault mapping**

In `food_ops_demo/workflow.py`, ensure the non-success branch in `_execute()` contains:

```python
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
```

In `food_ops_demo/mock_web_adapter.py`, keep `_result_from_status()` returning:

```python
        if "登录已过期" in status:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="auth_required", message="Mock 后台登录已过期，需要人工处理。"),
            )
        if "保存失败" in status:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="mock_save_failed", message="Mock 后台保存失败。"),
            )
```

- [ ] **Step 5: Run fault tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_mock_web_adapter.py tests/test_workflow_adapter_modes.py -v
```

Expected:

```text
All tests pass
```

- [ ] **Step 6: Commit fault injection behavior**

Run:

```powershell
git add food_ops_demo/mock_web_adapter.py food_ops_demo/workflow.py tests/test_mock_web_adapter.py tests/test_workflow_adapter_modes.py
git commit -m "feat: add mock web fault handling"
```

---

## Task 8: Documentation, CodeGraph, Tests, And Browser Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/project-structure.md`

- [ ] **Step 1: Update README Phase 3 usage**

Add this section to `README.md` after the Phase 2 flow:

```markdown
## Phase 3 MockWebAdapter 演示流程

1. 安装 Playwright 依赖：

   ```powershell
   & 'E:\anaconda\envs\jobhellper\python.exe' -m pip install -e ".[dev]"
   & 'E:\anaconda\envs\jobhellper\python.exe' -m playwright install chromium
   ```

2. 启动本地工作台：

   ```powershell
   & 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
   ```

3. 打开 `http://127.0.0.1:8765/`。
4. 在执行模式中选择 `MockWebAdapter`。
5. 点击 `打开 Mock 后台`，确认本地 mock 商家后台能打开。
6. 运行指令：`把人民广场店的招牌牛肉饭改成 29.9`。
7. 确认任务执行成功，任务中心出现 `mock_web` 任务。
8. 打开 `data/demo/mock-web-screenshots/`，确认存在最新执行截图。
```

- [ ] **Step 2: Update project structure document**

In `docs/project-structure.md`, add:

```markdown
- `food_ops_demo.mock_web_adapter.MockWebAdapter`：通过 Playwright 驱动本地 mock 商家后台页面，验证未来真实 RPA 适配器的执行边界。
- `food_ops_demo/static/mock_merchant.html`：本地仿真商家后台，用于 Playwright 点击、截图和异常注入。
```

- [ ] **Step 3: Sync CodeGraph**

Run:

```powershell
codegraph sync .
```

Expected:

```text
Done
```

- [ ] **Step 4: Run full test suite**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -v
```

Expected:

```text
All tests pass
```

- [ ] **Step 5: Restart local app**

If port `8765` is already occupied, identify the process:

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Stop the old local demo server if it belongs to this project:

```powershell
Stop-Process -Id <PID>
```

Start the app:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

Expected health check:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health'
```

```json
{"status":"ok"}
```

- [ ] **Step 6: Browser smoke test**

Open `http://127.0.0.1:8765/` in the in-app browser and verify:

- Page title is `外卖运营 Agent 工作台`.
- Execution mode selector contains `FakeAdapter` and `MockWebAdapter`.
- `/mock/merchant` opens and shows `Mock 商家后台`.
- In `MockWebAdapter` mode, `把人民广场店的招牌牛肉饭改成 29.9` reaches `succeeded`.
- Task center shows the new task with `mock_web`.
- `data/demo/mock-web-screenshots/last-success.png` exists.
- In `FakeAdapter` mode, the existing Phase 2 phone and sold-out flows still work.
- Browser console has no errors.

- [ ] **Step 7: Commit documentation**

Run:

```powershell
git add README.md docs/project-structure.md
git commit -m "docs: document phase 3 mock web flow"
```

- [ ] **Step 8: Final branch status**

Run:

```powershell
git status --short
git log --oneline -10
```

Expected:

```text
Working tree is clean.
Recent commits include Phase 3 implementation.
```

---

## Self-Review

Spec coverage:

- Mock merchant backend page: Task 2.
- Playwright browser dependency: Task 1.
- MockWebAdapter: Tasks 3 and 4.
- Adapter contract extension: Task 4.
- Per-task execution mode: Task 5.
- Static workbench mode selector: Task 6.
- Fault injection for auth-required/save-failed: Task 7.
- README, CodeGraph, full tests, browser validation: Task 8.

Placeholder scan:

- No unresolved marker text remains in the implementation steps.
- Each task includes exact paths, test commands, expected failures, implementation snippets, and commit messages.

Type consistency:

- Adapter modes use the exact strings `fake` and `mock_web`.
- `Task.adapter_mode` is the persisted execution metadata.
- `TaskManager.create_task(..., adapter_mode=...)` matches the API payload field `adapter_mode`.
- `MockWebAdapter` implements all methods in `BasePlatformAdapter`.
- `OperationResult.error.code == "auth_required"` maps to `manual_required`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-phase-3-mock-web-adapter.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
