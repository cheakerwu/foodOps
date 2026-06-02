# Phase 2 Local Ops Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the minimal local MVP into a more usable operations workbench with durable demo data, a task center, expanded supported instructions, adapter contract tests, and clearer local reset/replay flows.

**Architecture:** Keep the app as a modular FastAPI service and avoid new infrastructure. Add a small SQLite-backed storage boundary using Python's standard `sqlite3`, keep `FakePlatformAdapter` behind the existing adapter interface, and expand the static page rather than introducing a frontend build system.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, sqlite3, pytest, FastAPI TestClient, vanilla HTML/CSS/JS.

---

## Scope

This phase should produce a stronger local demo without connecting to real platforms, Playwright, real LLMs, or a database server.

Build these user-facing capabilities:

- Persist store/menu/task/audit data across server restarts with local SQLite.
- Add a reset demo-data action so demos can be replayed predictably.
- Add a task center panel with recent tasks and selectable task details.
- Add `store.update_phone` instruction support.
- Add `menu.mark_sold_out` and `menu.restore_sale` aliases while keeping the existing sale-status operation.
- Add adapter contract tests so future API/RPA adapters must satisfy the same behavior.
- Improve API responses and UI copy for validation errors and manual intervention.

Do not build:

- Real external platform connectors.
- Browser automation or Playwright.
- Multi-user auth or approval roles.
- Batch cross-store execution.
- A React/Vite frontend.

## File Structure

- Create `food_ops_demo/storage.py`: SQLite schema, seed data, reset, store/menu/task persistence helpers.
- Modify `food_ops_demo/adapter.py`: allow `FakePlatformAdapter` to read and write through `DemoDatabase`.
- Modify `food_ops_demo/models.py`: add `store.update_phone` data support, phone preview fields, and task-list response shapes if needed.
- Modify `food_ops_demo/parser.py`: add phone-update and sold-out/restore aliases.
- Modify `food_ops_demo/risk.py`: validate phone updates and normalize sale-status aliases.
- Modify `food_ops_demo/workflow.py`: persist task changes after state transitions.
- Modify `food_ops_demo/audit.py`: optionally read audit records from SQLite while keeping JSONL compatibility for tests that still use file audit.
- Modify `food_ops_demo/app.py`: add task list, reset, and enriched task detail endpoints.
- Modify `food_ops_demo/static/index.html`: add task center, reset button, phone-update example, and better error display.
- Create `tests/test_storage.py`: SQLite persistence and reset tests.
- Create `tests/test_adapter_contract.py`: reusable adapter behavior tests.
- Modify existing tests to use temporary SQLite files where persistence matters.
- Modify `README.md`: document Phase 2 commands and demo flow.

## Task 1: SQLite Demo Storage

**Files:**
- Create: `food_ops_demo/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing storage tests**

Create `tests/test_storage.py`:

```python
from food_ops_demo.storage import DemoDatabase


def test_database_seeds_demo_store(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    snapshot = db.get_store_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.phone == "021-88888888"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


def test_database_persists_menu_price_across_instances(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)
    first.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    second = DemoDatabase(path)
    item = second.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "29.90"


def test_database_reset_restores_seed_data(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    db.reset_demo_data()
    item = db.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "32.00"
```

- [ ] **Step 2: Run storage tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_storage.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'food_ops_demo.storage'`.

- [ ] **Step 3: Implement minimal SQLite storage**

Create `food_ops_demo/storage.py` with:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from food_ops_demo.models import MenuItem, StoreSnapshot


class DemoDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_if_empty()

    def get_store_snapshot(self, store_name: str) -> StoreSnapshot:
        with self._connect() as conn:
            store = conn.execute(
                "SELECT store_id, store_name, phone, business_hours_json FROM stores WHERE store_name = ?",
                (store_name,),
            ).fetchone()
            if store is None:
                raise KeyError(store_name)
            rows = conn.execute(
                "SELECT item_id, store_id, name, price, sale_status, image FROM menu_items WHERE store_id = ? ORDER BY sort_order",
                (store["store_id"],),
            ).fetchall()
        return StoreSnapshot(
            store_id=store["store_id"],
            store_name=store["store_name"],
            phone=store["phone"],
            business_hours=json.loads(store["business_hours_json"]),
            items=[MenuItem(**dict(row)) for row in rows],
        )

    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        try:
            snapshot = self.get_store_snapshot(store_name)
        except KeyError:
            return []
        return [item for item in snapshot.items if item.name == item_name]

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> bool:
        return self._update_menu_field(store_name, item_name, "price", price)

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> bool:
        return self._update_menu_field(store_name, item_name, "sale_status", sale_status)

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE stores SET business_hours_json = ? WHERE store_name = ?",
                (json.dumps(business_hours, ensure_ascii=False), store_name),
            )
            return cursor.rowcount == 1

    def update_store_phone(self, store_name: str, phone: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("UPDATE stores SET phone = ? WHERE store_name = ?", (phone, store_name))
            return cursor.rowcount == 1

    def reset_demo_data(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM menu_items")
            conn.execute("DELETE FROM stores")
        self._insert_seed_data()

    def _update_menu_field(self, store_name: str, item_name: str, field: str, value: str) -> bool:
        if field not in {"price", "sale_status"}:
            raise ValueError(field)
        snapshot = self.get_store_snapshot(store_name)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE menu_items SET {field} = ? WHERE store_id = ? AND name = ?",
                (value, snapshot.store_id, item_name),
            )
            return cursor.rowcount == 1

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stores (
                    store_id TEXT PRIMARY KEY,
                    store_name TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL,
                    business_hours_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_items (
                    item_id TEXT PRIMARY KEY,
                    store_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price TEXT NOT NULL,
                    sale_status TEXT NOT NULL,
                    image TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    FOREIGN KEY (store_id) REFERENCES stores(store_id)
                )
                """
            )

    def _seed_if_empty(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
        if count == 0:
            self._insert_seed_data()

    def _insert_seed_data(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO stores VALUES (?, ?, ?, ?)",
                ("store_001", "人民广场店", "021-88888888", '[{"start":"09:30","end":"21:30"}]'),
            )
            conn.executemany(
                "INSERT INTO menu_items VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("item_001", "store_001", "招牌牛肉饭", "32.00", "on_sale", "beef_rice.jpg", 1),
                    ("item_002", "store_001", "可乐", "6.00", "on_sale", "cola.jpg", 2),
                    ("item_003", "store_001", "宫保鸡丁", "28.00", "on_sale", "kung_pao_chicken.jpg", 3),
                ],
            )
```

- [ ] **Step 4: Run storage tests to verify they pass**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_storage.py -v
```

Expected: all storage tests pass.

- [ ] **Step 5: Commit storage**

Run:

```powershell
git add food_ops_demo/storage.py tests/test_storage.py
git commit -m "feat: add sqlite demo storage"
```

## Task 2: Persist FakeAdapter State

**Files:**
- Modify: `food_ops_demo/adapter.py`
- Test: `tests/test_adapter.py`

- [ ] **Step 1: Write the failing adapter persistence test**

Append to `tests/test_adapter.py`:

```python
from food_ops_demo.storage import DemoDatabase


def test_fake_adapter_can_persist_through_database(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = FakePlatformAdapter(database=DemoDatabase(path))
    first.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    second = FakePlatformAdapter(database=DemoDatabase(path))
    item = second.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "29.90"
```

- [ ] **Step 2: Run adapter tests to verify the new test fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter.py -v
```

Expected: fail with `TypeError` because `FakePlatformAdapter` does not accept `database`.

- [ ] **Step 3: Modify `FakePlatformAdapter` to accept optional storage**

In `food_ops_demo/adapter.py`, change the constructor and methods so:

```python
class FakePlatformAdapter(BasePlatformAdapter):
    def __init__(self, database: DemoDatabase | None = None) -> None:
        self.database = database
        self._stores = _seed_memory_stores() if database is None else {}
```

Extract the current hard-coded seed dictionary into this helper in `adapter.py`:

```python
def _seed_memory_stores() -> dict[str, StoreSnapshot]:
    return {
        "人民广场店": StoreSnapshot(
            store_id="store_001",
            store_name="人民广场店",
            phone="021-88888888",
            business_hours=[{"start": "09:30", "end": "21:30"}],
            items=[
                MenuItem(item_id="item_001", store_id="store_001", name="招牌牛肉饭", price="32.00", sale_status="on_sale", image="beef_rice.jpg"),
                MenuItem(item_id="item_002", store_id="store_001", name="可乐", price="6.00", sale_status="on_sale", image="cola.jpg"),
                MenuItem(item_id="item_003", store_id="store_001", name="宫保鸡丁", price="28.00", sale_status="on_sale", image="kung_pao_chicken.jpg"),
            ],
        )
    }
```

Then route each public method:

```python
def get_snapshot(self, store_name: str) -> StoreSnapshot:
    if self.database:
        return self.database.get_store_snapshot(store_name)
    ...
```

For updates, call the corresponding `DemoDatabase` method and convert `False` to the existing `OperationResult` errors.

- [ ] **Step 4: Run adapter tests to verify they pass**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter.py -v
```

Expected: all adapter tests pass.

- [ ] **Step 5: Commit adapter persistence**

Run:

```powershell
git add food_ops_demo/adapter.py tests/test_adapter.py
git commit -m "feat: persist fake adapter state"
```

## Task 3: Store Phone Operation

**Files:**
- Modify: `food_ops_demo/models.py`
- Modify: `food_ops_demo/parser.py`
- Modify: `food_ops_demo/risk.py`
- Modify: `food_ops_demo/adapter.py`
- Modify: `food_ops_demo/workflow.py`
- Test: `tests/test_parser.py`
- Test: `tests/test_risk.py`
- Test: `tests/test_adapter.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing parser test for phone update**

Append to `tests/test_parser.py`:

```python
def test_parse_store_phone_update_instruction():
    result = parse_instruction("把人民广场店联系电话改成 021-66668888")

    assert not result.errors
    assert result.plan is not None
    assert result.plan.operation_type == "store.update_phone"
    assert result.plan.store_name == "人民广场店"
    assert result.plan.changes["phone"] == "021-66668888"
```

- [ ] **Step 2: Run parser test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_parser.py::test_parse_store_phone_update_instruction -v
```

Expected: fail because parser returns `unsupported_instruction`.

- [ ] **Step 3: Implement phone parsing**

Add to `food_ops_demo/parser.py`:

```python
PHONE_PATTERN = re.compile(r"^把(?P<store>.+?店)(?:联系电话|电话)改成\s*(?P<phone>[0-9\\-]{7,20})$")
```

Handle it before the unsupported fallback:

```python
if match := PHONE_PATTERN.match(instruction):
    return ParseResult(
        plan=OperationPlan(
            instruction=instruction,
            operation_type="store.update_phone",
            store_name=match.group("store"),
            changes={"phone": match.group("phone")},
        )
    )
```

- [ ] **Step 4: Run parser tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_parser.py -v
```

Expected: parser tests pass.

- [ ] **Step 5: Write failing risk, adapter, workflow tests**

Append to `tests/test_risk.py`:

```python
def test_phone_update_is_high_risk():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店联系电话改成 021-66668888").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.plan.risk_level == "high"
    assert result.plan.requires_approval is True
    assert result.preview["current_phone"] == "021-88888888"
    assert result.preview["target_phone"] == "021-66668888"
```

Append to `tests/test_adapter.py`:

```python
def test_fake_adapter_updates_store_phone():
    adapter = FakePlatformAdapter()

    result = adapter.update_store_phone("人民广场店", "021-66668888")
    snapshot = adapter.get_snapshot("人民广场店")

    assert result.success is True
    assert snapshot.phone == "021-66668888"
```

Append to `tests/test_workflow.py`:

```python
def test_confirm_phone_update_changes_snapshot(tmp_path):
    adapter = FakePlatformAdapter()
    manager = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"))
    plan, preview = _validated_plan("把人民广场店联系电话改成 021-66668888", adapter)
    task = manager.create_task(plan, preview)

    completed = manager.confirm_task(task.task_id)

    assert completed.state == "succeeded"
    assert completed.after_snapshot["phone"] == "021-66668888"
```

- [ ] **Step 6: Run targeted tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_risk.py::test_phone_update_is_high_risk tests/test_adapter.py::test_fake_adapter_updates_store_phone tests/test_workflow.py::test_confirm_phone_update_changes_snapshot -v
```

Expected: fail because adapter, risk, and workflow do not support `store.update_phone`.

- [ ] **Step 7: Implement phone update across adapter, risk, workflow**

In `BasePlatformAdapter`, add:

```python
@abstractmethod
def update_store_phone(self, store_name: str, phone: str) -> OperationResult:
    raise NotImplementedError
```

In `FakePlatformAdapter`, implement `update_store_phone`.

In `risk.py`, add:

```python
if plan.operation_type == "store.update_phone":
    validated = plan.model_copy(update={"risk_level": "high", "requires_approval": True})
    return ValidationResult(
        plan=validated,
        preview={
            "operation_type": plan.operation_type,
            "store_name": snapshot.store_name,
            "current_phone": snapshot.phone,
            "target_phone": plan.changes["phone"],
            "risk_level": "high",
        },
    )
```

In `workflow.py`, add `store.update_phone` to `_apply_plan` and `_verify`.

- [ ] **Step 8: Run full operation tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_parser.py tests/test_risk.py tests/test_adapter.py tests/test_workflow.py -v
```

Expected: all operation tests pass.

- [ ] **Step 9: Commit phone operation**

Run:

```powershell
git add food_ops_demo tests
git commit -m "feat: add store phone update operation"
```

## Task 4: Sale-Status Aliases For Sold Out And Restore

**Files:**
- Modify: `food_ops_demo/parser.py`
- Modify: `food_ops_demo/risk.py`
- Test: `tests/test_parser.py`
- Test: `tests/test_risk.py`

- [ ] **Step 1: Write failing alias parser tests**

Append to `tests/test_parser.py`:

```python
def test_parse_mark_sold_out_alias():
    result = parse_instruction("把人民广场店的可乐设为售罄")

    assert not result.errors
    assert result.plan.operation_type == "menu.update_sale_status"
    assert result.plan.changes["sale_status"] == "sold_out"


def test_parse_restore_sale_alias():
    result = parse_instruction("把人民广场店的可乐恢复销售")

    assert not result.errors
    assert result.plan.operation_type == "menu.update_sale_status"
    assert result.plan.changes["sale_status"] == "on_sale"
```

- [ ] **Step 2: Run alias tests to verify they fail**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_parser.py::test_parse_mark_sold_out_alias tests/test_parser.py::test_parse_restore_sale_alias -v
```

Expected: fail because parser only supports 上架/下架.

- [ ] **Step 3: Implement alias parsing**

Update the sale-status regex in `parser.py`:

```python
SALE_STATUS_PATTERN = re.compile(r"^把(?P<store>.+?店)的(?P<target>.+?)(?P<action>下架|上架|设为售罄|恢复销售)$")
```

Map action:

```python
status_map = {
    "下架": "off_sale",
    "上架": "on_sale",
    "设为售罄": "sold_out",
    "恢复销售": "on_sale",
}
status = status_map[match.group("action")]
```

- [ ] **Step 4: Write failing risk test for sold-out preview**

Append to `tests/test_risk.py`:

```python
def test_sold_out_alias_uses_sale_status_preview():
    adapter = FakePlatformAdapter()
    plan = parse_instruction("把人民广场店的可乐设为售罄").plan

    result = validate_plan(plan, adapter)

    assert not result.errors
    assert result.preview["current_sale_status"] == "on_sale"
    assert result.preview["target_sale_status"] == "sold_out"
```

- [ ] **Step 5: Run parser and risk tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_parser.py tests/test_risk.py -v
```

Expected: parser and risk tests pass.

- [ ] **Step 6: Commit sale-status aliases**

Run:

```powershell
git add food_ops_demo/parser.py tests/test_parser.py tests/test_risk.py
git commit -m "feat: add sale status aliases"
```

## Task 5: Persist Tasks And Add Task List API

**Files:**
- Modify: `food_ops_demo/storage.py`
- Modify: `food_ops_demo/workflow.py`
- Modify: `food_ops_demo/app.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing task persistence test**

Append to `tests/test_workflow.py`:

```python
from food_ops_demo.storage import DemoDatabase


def test_task_manager_persists_tasks_across_instances(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    adapter = FakePlatformAdapter(database=db)
    first = TaskManager(adapter=adapter, audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    plan, preview = _validated_plan("把人民广场店的招牌牛肉饭改成 29.9", adapter)
    task = first.create_task(plan, preview)
    first.confirm_task(task.task_id)

    second = TaskManager(adapter=FakePlatformAdapter(database=db), audit_log=AuditLog(tmp_path / "audit.jsonl"), database=db)
    loaded = second.get_task(task.task_id)

    assert loaded is not None
    assert loaded.state == "succeeded"
    assert loaded.result["verified"] is True
```

- [ ] **Step 2: Run workflow test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow.py::test_task_manager_persists_tasks_across_instances -v
```

Expected: fail because `TaskManager` does not accept `database`.

- [ ] **Step 3: Add task table and repository methods**

In `storage.py`, extend schema:

```python
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

Update the imports at the top of `storage.py`:

```python
from food_ops_demo.models import MenuItem, StoreSnapshot, Task
```

Add methods:

```python
def save_task(self, task: Task) -> None:
    payload = task.model_dump_json()
    with self._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, task_json, updated_at) VALUES (?, ?, ?)",
            (task.task_id, payload, task.updated_at),
        )

def get_task(self, task_id: str) -> Task | None:
    with self._connect() as conn:
        row = conn.execute("SELECT task_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return Task.model_validate_json(row["task_json"]) if row else None

def list_tasks(self, limit: int = 20) -> list[Task]:
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT task_json FROM tasks ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [Task.model_validate_json(row["task_json"]) for row in rows]
```

- [ ] **Step 4: Modify `TaskManager` to persist tasks**

Allow `TaskManager(database: DemoDatabase | None = None)`. After every state change returned to the caller, call `database.save_task(task)` when a database exists. `get_task` should read from memory first and then from database.

- [ ] **Step 5: Run workflow tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_workflow.py -v
```

Expected: workflow tests pass.

- [ ] **Step 6: Write failing task list API test**

Append to `tests/test_api.py`:

```python
def test_task_list_endpoint_returns_recent_tasks(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的可乐下架"}).json()
    created = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()

    response = client.get("/api/demo/tasks")

    assert response.status_code == 200
    assert response.json()["items"][0]["task_id"] == created["task_id"]
```

- [ ] **Step 7: Add `GET /api/demo/tasks` route**

In `app.py`, add:

```python
@app.get("/api/demo/tasks")
def list_tasks() -> dict[str, Any]:
    return {"items": [task.model_dump(mode="json") for task in manager.list_tasks()]}
```

Also update `create_app` to accept and wire a persistent database:

```python
def create_app(audit_path: str | Path | None = None, database_path: str | Path | None = None) -> FastAPI:
    database = DemoDatabase(database_path or os.getenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3"))
    adapter = FakePlatformAdapter(database=database)
    audit_log = AuditLog(audit_path or os.getenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl"))
    manager = TaskManager(adapter=adapter, audit_log=audit_log, database=database)
```

- [ ] **Step 8: Run API tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py -v
```

Expected: API tests pass.

- [ ] **Step 9: Commit task persistence**

Run:

```powershell
git add food_ops_demo/storage.py food_ops_demo/workflow.py food_ops_demo/app.py tests/test_workflow.py tests/test_api.py
git commit -m "feat: persist tasks and list recent tasks"
```

## Task 6: Reset API And Demo Replay

**Files:**
- Modify: `food_ops_demo/app.py`
- Modify: `food_ops_demo/static/index.html`
- Test: `tests/test_api.py`
- Test: `tests/test_static_page.py`

- [ ] **Step 1: Write failing reset API test**

Append to `tests/test_api.py`:

```python
def test_reset_demo_data_restores_snapshot(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "demo.sqlite3", audit_path=tmp_path / "audit.jsonl"))
    parsed = client.post("/api/demo/parse", json={"text": "把人民广场店的招牌牛肉饭改成 29.9"}).json()
    task = client.post("/api/demo/tasks", json={"plan": parsed["plan"], "preview": parsed["preview"]}).json()
    client.post(f"/api/demo/tasks/{task['task_id']}/confirm")

    reset = client.post("/api/demo/reset")
    snapshot = client.get("/api/demo/snapshot").json()

    assert reset.status_code == 200
    assert snapshot["items"][0]["price"] == "32.00"
```

- [ ] **Step 2: Run reset API test to verify it fails**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py::test_reset_demo_data_restores_snapshot -v
```

Expected: fail with `404 Not Found`.

- [ ] **Step 3: Add reset route**

In `app.py`, add:

```python
@app.post("/api/demo/reset")
def reset_demo() -> dict[str, str]:
    database.reset_demo_data()
    return {"status": "reset"}
```

If `create_app` is called without a database path, create a `DemoDatabase` at `data/demo/demo.sqlite3`.

- [ ] **Step 4: Run API tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_api.py -v
```

Expected: API tests pass.

- [ ] **Step 5: Write failing static page reset-control test**

Append to `tests/test_static_page.py`:

```python
def test_static_page_contains_task_center_and_reset_control():
    html = Path("food_ops_demo/static/index.html").read_text(encoding="utf-8")

    assert 'id="taskList"' in html
    assert 'id="resetButton"' in html
    assert "任务中心" in html
```

- [ ] **Step 6: Add task center and reset button to page**

In `index.html`, add:

```html
<button id="resetButton" type="button">重置 Demo 数据</button>
<section>
  <div class="panel">
    <h2 class="panel-title">任务中心</h2>
    <div id="taskList"></div>
  </div>
</section>
```

Add JavaScript:

```js
async function resetDemo() {
  await request('/api/demo/reset', { method: 'POST' });
  state.taskId = null;
  state.taskState = null;
  renderTimeline(null);
  renderPreview(null, {});
  await loadSnapshot();
  await loadTasks();
  await loadAudit();
  setStatus('Demo 数据已重置。');
}

async function loadTasks() {
  const data = await request('/api/demo/tasks');
  document.getElementById('taskList').innerHTML = data.items.map((task) => `
    <button type="button" data-task-id="${task.task_id}">
      ${task.state} · ${task.instruction}
    </button>
  `).join('');
}
```

Wire `resetButton` to `resetDemo`.

- [ ] **Step 7: Run static page tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_static_page.py -v
```

Expected: static page tests pass.

- [ ] **Step 8: Commit reset and task center shell**

Run:

```powershell
git add food_ops_demo/app.py food_ops_demo/static/index.html tests/test_api.py tests/test_static_page.py
git commit -m "feat: add demo reset and task center"
```

## Task 7: Adapter Contract Tests

**Files:**
- Create: `tests/test_adapter_contract.py`
- Modify: `food_ops_demo/adapter.py`

- [ ] **Step 1: Write adapter contract tests**

Create `tests/test_adapter_contract.py`:

```python
import pytest

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.storage import DemoDatabase


@pytest.fixture(params=["memory", "sqlite"])
def adapter(request, tmp_path):
    if request.param == "memory":
        return FakePlatformAdapter()
    return FakePlatformAdapter(database=DemoDatabase(tmp_path / "demo.sqlite3"))


def test_adapter_contract_price_update(adapter):
    result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")
    item = adapter.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert result.success is True
    assert item.price == "29.90"


def test_adapter_contract_sale_status_update(adapter):
    result = adapter.update_menu_sale_status("人民广场店", "可乐", "sold_out")
    item = adapter.find_menu_items("人民广场店", "可乐")[0]

    assert result.success is True
    assert item.sale_status == "sold_out"


def test_adapter_contract_store_updates(adapter):
    phone_result = adapter.update_store_phone("人民广场店", "021-66668888")
    hours_result = adapter.update_business_hours("人民广场店", [{"start": "10:00", "end": "21:00"}])
    snapshot = adapter.get_snapshot("人民广场店")

    assert phone_result.success is True
    assert hours_result.success is True
    assert snapshot.phone == "021-66668888"
    assert snapshot.business_hours == [{"start": "10:00", "end": "21:00"}]
```

- [ ] **Step 2: Run contract tests**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest tests/test_adapter_contract.py -v
```

Expected: pass for memory and SQLite adapters.

- [ ] **Step 3: Commit contract tests**

Run:

```powershell
git add tests/test_adapter_contract.py food_ops_demo/adapter.py
git commit -m "test: add adapter contract coverage"
```

## Task 8: Documentation, Browser Check, And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-06-01-phase-2-local-ops-workbench.md` only if implementation discovers a verified correction to this plan.

- [ ] **Step 1: Update README Phase 2 usage**

Add:

```markdown
## Phase 2 Demo Flow

1. Start the app.
2. Click `重置 Demo 数据`.
3. Run one phone update: `把人民广场店联系电话改成 021-66668888`.
4. Run one sold-out update: `把人民广场店的可乐设为售罄`.
5. Select recent tasks from `任务中心`.
6. Confirm audit records are visible.
```

- [ ] **Step 2: Sync CodeGraph**

Run:

```powershell
codegraph sync .
```

Expected: index updates successfully.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Start local app**

Run:

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.app:app --host 127.0.0.1 --port 8765
```

Expected: `/health` returns `{"status":"ok"}`.

- [ ] **Step 5: Browser smoke test**

Open `http://127.0.0.1:8765/` and verify:

- Page title contains `外卖运营 Agent 工作台`.
- `重置 Demo 数据` restores `招牌牛肉饭` to `32.00`.
- Phone update reaches `succeeded`.
- Sold-out alias reaches `succeeded`.
- Task center lists recent tasks.
- Audit panel contains the completed task IDs.

- [ ] **Step 6: Commit documentation**

Run:

```powershell
git add README.md
git commit -m "docs: document phase 2 demo flow"
```

- [ ] **Step 7: Final branch status**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: working tree is clean and recent commits show the Phase 2 implementation.

## Self-Review

Spec coverage:

- Persistence: covered by Tasks 1, 2, and 5.
- Task center: covered by Tasks 5 and 6.
- Expanded operations: covered by Tasks 3 and 4.
- Adapter contract hardening: covered by Task 7.
- Local demo replay and docs: covered by Tasks 6 and 8.

Placeholder scan:

- This plan intentionally avoids open-ended implementation instructions.
- Each task has concrete files, tests, commands, expected results, and commit messages.

Type consistency:

- `DemoDatabase`, `TaskManager`, `FakePlatformAdapter`, `OperationPlan`, `Task`, and API route names are consistent across tasks.
- The plan preserves the current operation-type names and only adds `store.update_phone`.
