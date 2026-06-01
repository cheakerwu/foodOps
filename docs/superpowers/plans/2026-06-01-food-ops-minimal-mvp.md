# Food Ops Minimal MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI demo that turns supported Chinese operations instructions into approved, verified FakeAdapter actions with audit logs and a single-page UI.

**Architecture:** A small modular Python app under `food_ops_demo/` provides models, parsing, risk checks, fake platform execution, workflow state, JSONL audit, and API routes. A static HTML page calls the API and renders the plan preview, timeline, current snapshot, manual intervention controls, and latest audit result.

**Tech Stack:** Python, FastAPI, Pydantic, Uvicorn, pytest, FastAPI TestClient, vanilla HTML/CSS/JS.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest config.
- Create `.env.example`: local configuration example.
- Create `food_ops_demo/__init__.py`: package marker.
- Create `food_ops_demo/models.py`: Pydantic models and enums.
- Create `food_ops_demo/parser.py`: local rules parser.
- Create `food_ops_demo/risk.py`: validation and risk assignment.
- Create `food_ops_demo/adapter.py`: `BasePlatformAdapter` and `FakePlatformAdapter`.
- Create `food_ops_demo/audit.py`: JSONL audit writer/reader.
- Create `food_ops_demo/workflow.py`: task lifecycle and execution.
- Create `food_ops_demo/app.py`: FastAPI routes and static page serving.
- Create `food_ops_demo/static/index.html`: local MVP workbench.
- Create `tests/`: behavior tests.
- Modify `README.md`: setup, run, and verification instructions.

## Tasks

### Task 1: Project Skeleton And Parser Tests

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `food_ops_demo/__init__.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write the failing parser tests**

```python
from food_ops_demo.parser import parse_instruction


def test_parse_price_update_instruction():
    plan = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    assert plan.operation_type == "menu.update_price"
    assert plan.store_name == "人民广场店"
    assert plan.target_name == "招牌牛肉饭"
    assert plan.changes["price"] == "29.90"


def test_parse_sale_status_instruction():
    plan = parse_instruction("把人民广场店的可乐下架")
    assert plan.operation_type == "menu.update_sale_status"
    assert plan.changes["sale_status"] == "off_sale"


def test_unknown_instruction_has_clear_error():
    result = parse_instruction("帮我优化一下菜单")
    assert result.errors[0].code == "unsupported_instruction"
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run: `python -m pytest tests/test_parser.py -v`

Expected: fail because `food_ops_demo.parser` does not exist.

- [ ] **Step 3: Implement minimal parser and models**

Create `models.py` with `OperationPlan`, `ParseError`, and `ParseResult`. Create `parser.py` with deterministic Chinese rules for supported examples.

- [ ] **Step 4: Run parser tests to verify they pass**

Run: `python -m pytest tests/test_parser.py -v`

Expected: all parser tests pass.

### Task 2: Risk And Adapter

**Files:**
- Create: `tests/test_risk.py`
- Create: `tests/test_adapter.py`
- Modify: `food_ops_demo/models.py`
- Create: `food_ops_demo/risk.py`
- Create: `food_ops_demo/adapter.py`

- [ ] **Step 1: Write failing risk and adapter tests**

Tests cover medium/high risk, rejecting price below 1, unknown item, price mutation, sale-status mutation, and business-hours mutation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_risk.py tests/test_adapter.py -v`

Expected: fail because `risk.py` and `adapter.py` do not exist.

- [ ] **Step 3: Implement minimal FakeAdapter and risk validator**

Seed one store `人民广场店` with `招牌牛肉饭`, `可乐`, and `宫保鸡丁`. Implement snapshot lookup and mutations in memory.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_risk.py tests/test_adapter.py -v`

Expected: all risk and adapter tests pass.

### Task 3: Workflow And Audit

**Files:**
- Create: `tests/test_workflow.py`
- Create: `food_ops_demo/audit.py`
- Create: `food_ops_demo/workflow.py`

- [ ] **Step 1: Write failing workflow tests**

Tests cover task creation in `awaiting_approval`, confirm execution to `succeeded`, JSONL audit writing, login-expired intervention to `manual_required`, and resume to `succeeded`.

- [ ] **Step 2: Run workflow tests to verify they fail**

Run: `python -m pytest tests/test_workflow.py -v`

Expected: fail because workflow code does not exist.

- [ ] **Step 3: Implement workflow and audit**

Implement `TaskManager` with in-memory tasks and injectable audit path for tests.

- [ ] **Step 4: Run workflow tests to verify they pass**

Run: `python -m pytest tests/test_workflow.py -v`

Expected: all workflow tests pass.

### Task 4: API And Static UI

**Files:**
- Create: `tests/test_api.py`
- Create: `tests/test_static_page.py`
- Create: `food_ops_demo/app.py`
- Create: `food_ops_demo/static/index.html`

- [ ] **Step 1: Write failing API and static page tests**

Tests cover `/health`, `/api/demo/snapshot`, `/api/demo/parse`, `/api/demo/tasks`, `/api/demo/tasks/{task_id}/confirm`, manual intervention routes, and page contains the core controls.

- [ ] **Step 2: Run API/UI tests to verify they fail**

Run: `python -m pytest tests/test_api.py tests/test_static_page.py -v`

Expected: fail because app and page do not exist.

- [ ] **Step 3: Implement FastAPI routes and static page**

Serve `/` from the static HTML file. Implement JSON routes against one process-local `TaskManager`.

- [ ] **Step 4: Run API/UI tests to verify they pass**

Run: `python -m pytest tests/test_api.py tests/test_static_page.py -v`

Expected: all API and static page tests pass.

### Task 5: Documentation, Index, And Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document install, test, and local run commands:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
uvicorn food_ops_demo.app:app --reload --host 127.0.0.1 --port 8765
```

- [ ] **Step 2: Sync CodeGraph**

Run: `codegraph sync .`

Expected: Python and HTML files are indexed.

- [ ] **Step 3: Run full verification**

Run: `python -m pytest -v`

Expected: all tests pass.

- [ ] **Step 4: Commit implementation**

Run: `git status --short`, review changed files, then commit the MVP.

