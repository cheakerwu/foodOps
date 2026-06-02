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
