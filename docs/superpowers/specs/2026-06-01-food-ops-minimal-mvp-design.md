# Food Ops Minimal MVP Design

Date: 2026-06-01

## Goal

Build the smallest local demo of the food delivery operations Agent workbench:

```text
natural-language instruction -> OperationPlan -> risk validation -> approval -> FakeAdapter execution -> verification -> audit log
```

This MVP does not connect to real delivery platforms, browser RPA, real LLMs, real authentication, or a database.

## Scope

The first version supports one local store, a few seeded menu items, and three operations:

- `menu.update_price`
- `menu.update_sale_status`
- `store.update_business_hours`

The UI is a single static page served by FastAPI. Users can enter an instruction, generate a plan, confirm execution, simulate manual intervention, resume a task, view the timeline, inspect the current mock store snapshot, and see the latest audit result.

## Architecture

The backend is a small modular FastAPI application under `food_ops_demo/`.

- `models.py` defines the shared data contracts.
- `parser.py` converts supported Chinese instructions into `OperationPlan`.
- `risk.py` validates a plan against the current snapshot and assigns risk.
- `adapter.py` provides `BasePlatformAdapter` and an in-memory `FakePlatformAdapter`.
- `workflow.py` owns task state transitions, approval, execution, verification, intervention, and audit.
- `audit.py` writes JSONL audit records.
- `app.py` exposes the API and serves the static page.
- `static/index.html` contains the local workbench UI.

The implementation borrows the useful idea from the previous e-commerce automation repository: platform-specific execution is hidden behind an adapter boundary. The MVP keeps the runtime simple and local.

## Data Flow

1. The user enters an instruction on the page.
2. `POST /api/demo/parse` parses the instruction into an `OperationPlan`.
3. The backend validates the plan with current fake data and returns a preview.
4. `POST /api/demo/tasks` creates a task in `awaiting_approval` state.
5. `POST /api/demo/tasks/{task_id}/confirm` executes the task only after approval.
6. The workflow captures the before snapshot, executes through `FakePlatformAdapter`, reads back the after snapshot, verifies the change, appends an audit record, and returns the task.
7. The UI refreshes the timeline, snapshot, and audit result.

## Risk Rules

- Price below `1.00` is rejected.
- Single item price changes are medium risk and require approval.
- Price changes greater than 50% are high risk and require approval.
- Sale status changes are medium risk and require approval.
- Business-hours changes are high risk and require approval.
- Unknown store or menu item returns an explicit error.
- Ambiguous target names return an explicit error.

## Task States

The MVP state sequence is:

```text
created -> parsed -> validated -> previewed -> awaiting_approval -> queued -> executing -> verifying -> succeeded
```

Failure and manual branches:

```text
created|parsed|validated|previewed -> failed
executing -> manual_required
manual_required -> executing
manual_required -> cancelled
```

## Error Handling

Errors are returned as structured objects with `code` and `message`. Invalid plans are not converted into tasks. A task that reaches `manual_required` is not marked failed unless the user cancels it.

## Testing

Automated tests cover:

- instruction parsing
- risk validation
- FakeAdapter mutations
- workflow state transitions and audit writing
- FastAPI API endpoints
- static page key elements

The required verification command is:

```powershell
python -m pytest -v
```

## Runtime

The app runs locally with:

```powershell
uvicorn food_ops_demo.app:app --reload --host 127.0.0.1 --port 8765
```

The page is available at:

```text
http://127.0.0.1:8765
```

