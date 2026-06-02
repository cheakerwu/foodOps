# Phase 2 Checkpoint - Task 5 Paused

Date: 2026-06-01
Workspace: `D:\code\demov1`
Branch: `feat/minimal-mvp`
Code checkpoint commit before this document: `091c7c7 fix: harden task persistence isolation`
Python interpreter: `E:\anaconda\envs\jobhellper\python.exe`
Local app port used in prior validation: `http://127.0.0.1:8765/`

## Current Status

This node is intentionally paused before starting Task 6.

The working tree was clean before writing this checkpoint document. The code state to resume from is commit `091c7c7`, which includes Task 5 implementation plus the code-quality fix pass for task persistence isolation.

Latest reported verification from the Task 5 fix worker:

```powershell
E:\anaconda\envs\jobhellper\python.exe -m pytest tests/test_storage.py tests/test_workflow.py tests/test_api.py tests/test_static_page.py -v
# 37 passed

E:\anaconda\envs\jobhellper\python.exe -m pytest -v
# 63 passed
```

Important resume note: Task 5 has been implemented and its review findings have been fixed, but the post-fix spec/code-quality re-review gate has not yet been rerun because development was paused at this point.

## Completed Work

### Task 1 - SQLite Demo Storage

Status: completed and reviewed.

Commits:

- `c532860 feat: add sqlite demo storage`
- `119c790 fix: harden sqlite demo storage`

Implemented:

- Added `food_ops_demo/storage.py`.
- Added `DemoDatabase` with local SQLite schema and seed data.
- Added store/menu snapshot reads and update helpers.
- Added reset support for seed demo data.
- Hardened SQLite connection handling and reset atomicity after review.

### Task 2 - Persist FakeAdapter State

Status: completed and reviewed.

Commits:

- `624c3bd feat: persist fake adapter state`
- `b8e3e7e fix: align fake adapter error parity`

Implemented:

- `FakePlatformAdapter` can run in memory mode or SQLite-backed mode.
- SQLite-backed adapter persists menu/store updates across adapter instances.
- Error behavior was aligned between memory and SQLite modes.

### Task 3 - Store Phone Operation

Status: completed and reviewed.

Commit:

- `bd39d33 feat: add store phone update operation`

Implemented:

- Added parser support for `store.update_phone`.
- Added risk validation and preview fields for phone updates.
- Added adapter and workflow execution support for store phone changes.
- Added tests across parser, risk, adapter, and workflow layers.

Follow-up note:

- Task 7 adapter contract tests should include `update_store_phone()` coverage.

### Task 4 - Sale-Status Aliases

Status: completed and reviewed.

Commit:

- `a3b0630 feat: add sale status aliases`

Implemented:

- Added sold-out alias mapping to `menu.update_sale_status` with `sale_status=sold_out`.
- Added restore-sale alias mapping to `menu.update_sale_status` with `sale_status=on_sale`.
- Kept the existing sale-status operation behavior.
- Added parser and risk coverage.

### Task 5 - Persist Tasks And Add Task List API

Status: implemented, review findings fixed, awaiting post-fix re-review.

Commits:

- `ccf2561 feat: persist tasks and list recent tasks`
- `091c7c7 fix: harden task persistence isolation`

Implemented:

- Added `tasks` persistence to `DemoDatabase`.
- Added `save_task()`, `get_task()`, and `list_tasks()`.
- Wired `TaskManager` to persist tasks after state transitions.
- Added `TaskManager.get_task()` DB fallback and `TaskManager.list_tasks()`.
- Added `GET /api/demo/tasks`.
- Wired `create_app(database_path=...)` into `DemoDatabase`, `FakePlatformAdapter`, and `TaskManager`.
- Removed import-time default database creation from `food_ops_demo.app`.
- Added `food_ops_demo/asgi.py` as the runtime ASGI entrypoint.
- Updated tests to use temporary database paths.
- Added negative-limit rejection for `DemoDatabase.list_tasks()` and `TaskManager.list_tasks()`.
- Added DB-backed workflow coverage for cancel, manual-required, resume success, invalid-state failure, and execution failure paths.
- Added storage-level task persistence tests for round-trip, ordering, limit, missing lookup, and negative limits.

Pending before marking Task 5 fully complete:

- Rerun spec compliance review for Task 5 after commit `091c7c7`.
- Rerun code-quality review for Task 5 after commit `091c7c7`.
- If both approve, mark Task 5 complete and proceed to Task 6.

## Paused Subagent Workflow State

Recommended resume sequence:

1. Review Task 5 diff range:

   ```powershell
   git diff a3b0630..091c7c7 -- food_ops_demo tests README.md
   ```

2. Run Task 5 focused tests:

   ```powershell
   E:\anaconda\envs\jobhellper\python.exe -m pytest tests/test_storage.py tests/test_workflow.py tests/test_api.py tests/test_static_page.py -v
   ```

3. Run full test suite:

   ```powershell
   E:\anaconda\envs\jobhellper\python.exe -m pytest -v
   ```

4. Dispatch Task 5 spec reviewer with the Task 5 requirements and commits `ccf2561` plus `091c7c7`.

5. Dispatch Task 5 code-quality reviewer only after spec review passes.

6. Continue to Task 6 only after both Task 5 review gates pass.

## Remaining Work

### Task 6 - Reset API And Demo Replay

Status: not started.

Planned files:

- `food_ops_demo/app.py`
- `food_ops_demo/static/index.html`
- `tests/test_api.py`
- `tests/test_static_page.py`

Planned implementation:

- Add `POST /api/demo/reset`.
- Reset should restore seed store/menu data through `DemoDatabase.reset_demo_data()`.
- Add UI reset control.
- Add task center shell in the static page.
- Add JavaScript to load recent tasks from `GET /api/demo/tasks`.
- Refresh snapshot, tasks, and audit after reset.

Expected commit:

- `feat: add demo reset and task center`

### Task 7 - Adapter Contract Tests

Status: not started.

Planned files:

- `tests/test_adapter_contract.py`
- `food_ops_demo/adapter.py` only if a contract mismatch is discovered.

Planned implementation:

- Add parametrized contract tests for memory and SQLite-backed `FakePlatformAdapter`.
- Cover menu price updates.
- Cover sale-status updates, including `sold_out`.
- Cover store phone updates.
- Cover store business-hours updates.
- Keep adapter behavior consistent across memory and SQLite modes.

Expected commit:

- `test: add adapter contract coverage`

### Task 8 - Documentation, CodeGraph, Browser Check, And Final Verification

Status: not started.

Planned files:

- `README.md`
- Plan document only if a verified correction is required.

Planned implementation:

- Document Phase 2 demo flow.
- Use the ASGI runtime target:

  ```powershell
  E:\anaconda\envs\jobhellper\python.exe -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
  ```

- Sync CodeGraph:

  ```powershell
  codegraph sync .
  ```

- Run full test suite:

  ```powershell
  E:\anaconda\envs\jobhellper\python.exe -m pytest -v
  ```

- Browser-smoke-test the local app at `http://127.0.0.1:8765/`.
- Verify reset, phone update, sold-out alias, recent task list, and audit visibility.

Expected commit:

- `docs: document phase 2 demo flow`

## Resume Prompt

Use this prompt when resuming:

```text
继续从 D:\code\demov1 的 checkpoint 恢复 Phase 2。当前分支 feat/minimal-mvp，代码 checkpoint 为 091c7c7，checkpoint 文档在 docs/superpowers/checkpoints/2026-06-01-phase-2-task5-paused.md。先不要直接做 Task 6；请先对 Task 5 的修复提交 091c7c7 重新跑 spec/code-quality 复审，通过后再按 subagent-driven-development 流程继续 Task 6、Task 7、Task 8。使用 E:\anaconda\envs\jobhellper\python.exe 跑测试。
```

