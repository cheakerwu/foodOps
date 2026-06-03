"""Workflow tests for browser_use adapter mode.

Validates that the TaskManager correctly routes tasks through a
BrowserUseAdapter, and that the adapter lifecycle (create / close)
is managed by the AdapterRegistry.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.browser_use_adapter import BrowserUseAdapter, _PriceUpdateResult
from food_ops_demo.models import StoreSnapshot, MenuItem
from food_ops_demo.parser import parse_instruction
from food_ops_demo.risk import validate_plan
from food_ops_demo.workflow import TaskManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_history(
    *,
    structured_output: _PriceUpdateResult | None = None,
    screenshot_paths: list[str | None] | None = None,
    errors: list[str | None] | None = None,
    urls: list[str | None] | None = None,
    final_result: str | None = None,
) -> MagicMock:
    """Create a mock AgentHistoryList matching browser-use conventions."""
    history = MagicMock()
    history.structured_output = structured_output
    history.screenshot_paths.return_value = screenshot_paths or []
    history.errors.return_value = errors or []
    history.urls.return_value = urls or ["https://merchant.example.com/store/1"]
    history.final_result.return_value = final_result
    return history


def _fake_snapshot(price: str = "32.00") -> StoreSnapshot:
    """Return a realistic snapshot for plan validation."""
    return StoreSnapshot(
        store_id="store_001",
        store_name="人民广场店",
        phone="021-12345678",
        business_hours=[{"start": "09:00", "end": "21:00"}],
        items=[
            MenuItem(
                item_id="item_001",
                store_id="store_001",
                name="招牌牛肉饭",
                price=price,
                sale_status="on_sale",
                image="",
            ),
            MenuItem(
                item_id="item_002",
                store_id="store_001",
                name="可乐",
                price="5.00",
                sale_status="on_sale",
                image="",
            ),
        ],
    )


def _validated_price_plan():
    """Parse and validate a price update plan using FakePlatformAdapter."""
    adapter = FakePlatformAdapter()
    parsed = parse_instruction("把人民广场店的招牌牛肉饭改成 29.9")
    validated = validate_plan(parsed.plan, adapter)
    assert validated.plan is not None
    return validated.plan, validated.preview


def _make_browser_use_adapter(mock_browser, tmp_path) -> BrowserUseAdapter:
    """Create a BrowserUseAdapter with mocked browser for testing."""
    return BrowserUseAdapter(
        page_url="http://127.0.0.1:8765/mock/merchant",
        browser=mock_browser,
        llm=MagicMock(),
        screenshot_dir=tmp_path / "browser-use-screenshots",
        max_steps=10,
    )


# ---------------------------------------------------------------------------
# Workflow: successful price update via browser_use
# ---------------------------------------------------------------------------


class TestBrowserUseWorkflowSuccess:
    @patch("browser_use.Agent")
    def test_confirm_task_executes_through_browser_use_adapter(
        self, mock_agent_cls, tmp_path
    ):
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True,
                observed_price="29.90",
                evidence_text="Price updated successfully.",
            ),
            screenshot_paths=["/tmp/shot1.png"],
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        # Mock get_snapshot to return different values for before/after verification.
        # Before snapshot: old price 32.00, after snapshot: new price 29.90
        adapter.get_snapshot = MagicMock(
            side_effect=[_fake_snapshot("32.00"), _fake_snapshot("29.90")]
        )

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "succeeded"
        assert completed.adapter_mode == "browser_use"
        assert completed.result["success"] is True
        assert completed.result["verified"] is True
        assert completed.result["submitted"] is True
        assert completed.result["shadow_mode"] is False

    @patch("browser_use.Agent")
    def test_browser_use_adapter_receives_correct_task_prompt(
        self, mock_agent_cls, tmp_path
    ):
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True, observed_price="29.90"
            ),
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        manager.confirm_task(task.task_id)

        # Find the call to Agent for update_menu_price (not get_snapshot)
        agent_calls = mock_agent_cls.call_args_list
        update_call = None
        for call in agent_calls:
            task_text = call.kwargs.get("task") or (
                call[0][0] if call[0] else None
            )
            if task_text and "招牌牛肉饭" in task_text:
                update_call = task_text
                break

        assert update_call is not None
        assert "人民广场店" in update_call
        assert "29.90" in update_call


# ---------------------------------------------------------------------------
# Workflow: agent failure paths
# ---------------------------------------------------------------------------


class TestBrowserUseWorkflowFailure:
    @patch("browser_use.Agent")
    def test_agent_exception_fails_task(self, mock_agent_cls, tmp_path):
        mock_browser = MagicMock()
        mock_agent_cls.return_value.run_sync.side_effect = RuntimeError("LLM timeout")

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "failed"
        assert completed.error is not None
        assert completed.error.code == "browser_use_agent_failed"
        assert "LLM timeout" in completed.error.message

    @patch("browser_use.Agent")
    def test_agent_verification_failure_fails_task(self, mock_agent_cls, tmp_path):
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=False,
                observed_price="32.00",
                evidence_text="Price field did not update.",
            ),
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "failed"
        assert completed.error is not None
        assert completed.error.code == "browser_use_verification_failed"

    @patch("browser_use.Agent")
    def test_missing_structured_output_fails_task(self, mock_agent_cls, tmp_path):
        mock_browser = MagicMock()
        update_history = _make_history(structured_output=None)
        mock_agent_cls.return_value.run_sync.return_value = update_history

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "failed"
        assert completed.error is not None
        assert completed.error.code == "browser_use_structured_output_invalid"

    @patch("browser_use.Agent")
    def test_agent_history_errors_fails_task(self, mock_agent_cls, tmp_path):
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True, observed_price="29.90"
            ),
            errors=["Connection reset", None, "Page crashed"],
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        adapter = _make_browser_use_adapter(mock_browser, tmp_path)
        adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())

        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"browser_use": adapter},
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "failed"
        assert completed.error is not None
        assert completed.error.code == "browser_use_agent_failed"


# ---------------------------------------------------------------------------
# Workflow: adapter registry lifecycle
# ---------------------------------------------------------------------------


class TestBrowserUseRegistryLifecycle:
    @patch("browser_use.Agent")
    def test_registry_creates_and_closes_adapter_per_call(
        self, mock_agent_cls, tmp_path
    ):
        """Scoped mode: each use() creates a fresh adapter and closes it."""
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True, observed_price="29.90"
            ),
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        created_adapters: list[BrowserUseAdapter] = []
        close_calls: list[BrowserUseAdapter] = []

        def factory():
            adapter = BrowserUseAdapter(
                page_url="http://127.0.0.1:8765/mock/merchant",
                browser=mock_browser,
                llm=MagicMock(),
                screenshot_dir=tmp_path / "bu-screenshots",
                max_steps=5,
            )
            adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())
            created_adapters.append(adapter)
            original_close = adapter.close

            def tracked_close():
                close_calls.append(adapter)
                original_close()

            adapter.close = tracked_close
            return adapter

        registry = AdapterRegistry(
            factories={"browser_use": factory},
            shared_modes=set(),
        )
        manager = TaskManager(
            adapter_registry=registry,
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        plan, preview = _validated_price_plan()
        task = manager.create_task(plan, preview, adapter_mode="browser_use")
        manager.confirm_task(task.task_id)

        assert len(created_adapters) == 1
        assert len(close_calls) == 1
        assert close_calls[0] is created_adapters[0]

    @patch("browser_use.Agent")
    def test_registry_does_not_share_browser_use_adapter(
        self, mock_agent_cls, tmp_path
    ):
        """Two confirm calls should create two separate adapters."""
        mock_browser = MagicMock()
        update_history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True, observed_price="29.90"
            ),
        )
        mock_agent_cls.return_value.run_sync.return_value = update_history

        created_adapters: list[BrowserUseAdapter] = []

        def factory():
            adapter = BrowserUseAdapter(
                page_url="http://127.0.0.1:8765/mock/merchant",
                browser=mock_browser,
                llm=MagicMock(),
                screenshot_dir=tmp_path / "bu-screenshots",
                max_steps=5,
            )
            adapter.get_snapshot = MagicMock(return_value=_fake_snapshot())
            created_adapters.append(adapter)
            return adapter

        registry = AdapterRegistry(
            factories={"browser_use": factory},
            shared_modes=set(),
        )
        manager = TaskManager(
            adapter_registry=registry,
            default_adapter_mode="browser_use",
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        plan, preview = _validated_price_plan()

        task1 = manager.create_task(plan, preview, adapter_mode="browser_use")
        manager.confirm_task(task1.task_id)

        task2 = manager.create_task(plan, preview, adapter_mode="browser_use")
        manager.confirm_task(task2.task_id)

        assert len(created_adapters) == 2
        assert created_adapters[0] is not created_adapters[1]


# ---------------------------------------------------------------------------
# Unknown mode still fails
# ---------------------------------------------------------------------------


class TestUnknownMode:
    def test_unknown_adapter_mode_fails_with_adapter_mode_not_found(self, tmp_path):
        fake = FakePlatformAdapter()
        plan, preview = _validated_price_plan()
        manager = TaskManager(
            adapters={"fake": fake},
            audit_log=AuditLog(tmp_path / "audit.jsonl"),
        )

        task = manager.create_task(plan, preview, adapter_mode="nonexistent")
        completed = manager.confirm_task(task.task_id)

        assert completed.state == "failed"
        assert completed.error is not None
        assert completed.error.code == "adapter_mode_not_found"


# ---------------------------------------------------------------------------
# API integration: parse accepts browser_use mode
# ---------------------------------------------------------------------------


class TestAPIBrowserUseMode:
    @patch("browser_use.ChatBrowserUse")
    @patch("browser_use.Agent")
    def test_parse_accepts_browser_use_adapter_mode(
        self, mock_agent_cls, mock_chat_cls, tmp_path
    ):
        from fastapi.testclient import TestClient
        from food_ops_demo.app import create_app

        snapshot_history = _make_history(
            final_result="Store data extracted",
        )
        mock_agent_cls.return_value.run_sync.return_value = snapshot_history

        client = TestClient(
            create_app(
                database_path=tmp_path / "demo.sqlite3",
                audit_path=tmp_path / "audit.jsonl",
            )
        )

        response = client.post(
            "/api/demo/parse",
            json={
                "text": "把人民广场店的招牌牛肉饭改成 29.9",
                "adapter_mode": "browser_use",
            },
        )

        assert response.status_code == 200
        body = response.json()
        # Should NOT be adapter_mode_not_found -- the mode is registered
        assert not any(e["code"] == "adapter_mode_not_found" for e in body["errors"])

    def test_parse_rejects_unknown_mode(self, tmp_path):
        from fastapi.testclient import TestClient
        from food_ops_demo.app import create_app

        client = TestClient(
            create_app(
                database_path=tmp_path / "demo.sqlite3",
                audit_path=tmp_path / "audit.jsonl",
            )
        )

        response = client.post(
            "/api/demo/parse",
            json={
                "text": "把人民广场店的招牌牛肉饭改成 29.9",
                "adapter_mode": "nonexistent",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["plan"] is None
        assert body["errors"][0]["code"] == "adapter_mode_not_found"
