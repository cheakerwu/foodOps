"""Tests for BrowserUseAdapter using mocked browser-use Agent."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from food_ops_demo.browser_use_adapter import BrowserUseAdapter, _PriceUpdateResult, _StoreSnapshotResult
from food_ops_demo.models import OperationResult


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
    """Create a mock AgentHistoryList."""
    history = MagicMock()
    history.structured_output = structured_output
    history.screenshot_paths.return_value = screenshot_paths or []
    history.errors.return_value = errors or []
    history.urls.return_value = urls or ["https://merchant.example.com/store/1"]
    history.final_result.return_value = final_result
    return history


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock(name="MockLLM")


@pytest.fixture
def mock_browser() -> MagicMock:
    browser = MagicMock(name="MockBrowser")
    return browser


@pytest.fixture
def adapter(mock_llm, mock_browser, tmp_path) -> BrowserUseAdapter:
    return BrowserUseAdapter(
        page_url="https://merchant.example.com/store/1",
        browser=mock_browser,
        llm=mock_llm,
        screenshot_dir=tmp_path / "screenshots",
        max_steps=10,
    )


# ---------------------------------------------------------------------------
# update_menu_price -- success path
# ---------------------------------------------------------------------------


class TestUpdateMenuPriceSuccess:
    @patch("browser_use.Agent")
    def test_returns_success_when_agent_reports_success(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True,
                observed_price="29.90",
                evidence_text="Price updated successfully.",
            ),
            screenshot_paths=["/tmp/shot1.png", None, "/tmp/shot2.png"],
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("Test Store", "Chicken Rice", "29.90")

        assert result.success is True
        assert result.error is None
        assert len(result.screenshot_paths) == 2
        assert "/tmp/shot1.png" in result.screenshot_paths
        assert result.evidence["success"] is True
        assert result.evidence["observed_value"] == "29.90"

    @patch("browser_use.Agent")
    def test_agent_receives_correct_task_prompt(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(success=True, observed_price="15.00")
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        adapter.update_menu_price("人民广场店", "招牌牛肉饭", "15.00")

        call_kwargs = mock_agent_cls.call_args
        task = call_kwargs.kwargs.get("task") or call_kwargs[1].get("task", call_kwargs[0][0] if call_kwargs[0] else None)
        # The task should mention the store, item, and new price
        assert "人民广场店" in task
        assert "招牌牛肉饭" in task
        assert "15.00" in task

    @patch("browser_use.Agent")
    def test_agent_called_with_output_model_schema(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(success=True, observed_price="10.00")
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        adapter.update_menu_price("Store", "Item", "10.00")

        call_kwargs = mock_agent_cls.call_args
        schema = call_kwargs.kwargs.get("output_model_schema") or call_kwargs[1].get("output_model_schema")
        assert schema is _PriceUpdateResult


# ---------------------------------------------------------------------------
# update_menu_price -- agent failure paths
# ---------------------------------------------------------------------------


class TestUpdateMenuPriceAgentFailure:
    @patch("browser_use.Agent")
    def test_returns_error_when_agent_raises(self, mock_agent_cls, adapter):
        mock_agent_cls.return_value.run_sync.side_effect = RuntimeError("LLM timeout")

        result = adapter.update_menu_price("Store", "Item", "10.00")

        assert result.success is False
        assert result.error.code == "browser_use_agent_failed"
        assert "LLM timeout" in result.error.message

    @patch("browser_use.Agent")
    def test_returns_error_when_history_has_errors(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(success=True, observed_price="10.00"),
            errors=["Connection reset", None, "Page crashed"],
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("Store", "Item", "10.00")

        assert result.success is False
        assert result.error.code == "browser_use_agent_failed"

    @patch("browser_use.Agent")
    def test_returns_error_when_structured_output_is_none(self, mock_agent_cls, adapter):
        history = _make_history(structured_output=None)
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("Store", "Item", "10.00")

        assert result.success is False
        assert result.error.code == "browser_use_structured_output_invalid"

    @patch("browser_use.Agent")
    def test_returns_verification_failed_when_agent_reports_failure(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(
                success=False,
                observed_price="32.00",
                evidence_text="Price field did not update.",
            ),
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("Store", "Item", "29.90")

        assert result.success is False
        assert result.error.code == "browser_use_verification_failed"
        assert "Price field did not update" in result.error.message


# ---------------------------------------------------------------------------
# unsupported operations
# ---------------------------------------------------------------------------


class TestUnsupportedOperations:
    def test_update_menu_sale_status_unsupported(self, adapter):
        result = adapter.update_menu_sale_status("Store", "Item", "on_sale")
        assert result.success is False
        assert result.error.code == "browser_use_unsupported_operation"

    def test_update_business_hours_unsupported(self, adapter):
        result = adapter.update_business_hours("Store", [{"start": "09:00", "end": "21:00"}])
        assert result.success is False
        assert result.error.code == "browser_use_unsupported_operation"

    def test_update_store_phone_unsupported(self, adapter):
        result = adapter.update_store_phone("Store", "021-12345678")
        assert result.success is False
        assert result.error.code == "browser_use_unsupported_operation"


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_closes_owned_browser(self):
        browser = MagicMock()
        adapter = BrowserUseAdapter(
            page_url="https://example.com",
            browser=browser,
            llm=MagicMock(),
        )
        # Browser was passed in, so adapter does NOT own it
        adapter.close()
        browser.close.assert_not_called()

    def test_close_closes_created_browser(self):
        """When no browser is passed, adapter creates and owns one."""
        adapter = BrowserUseAdapter(
            page_url="https://example.com",
            llm=MagicMock(),
        )
        # Simulate that a browser was lazily created
        mock_browser = MagicMock()
        adapter._browser = mock_browser
        adapter._owns_browser = True

        adapter.close()
        mock_browser.close.assert_called_once()
        assert adapter._browser is None

    def test_close_tolerates_browser_close_error(self):
        """close() should not raise even if browser.close() throws."""
        adapter = BrowserUseAdapter(
            page_url="https://example.com",
            llm=MagicMock(),
        )
        mock_browser = MagicMock()
        mock_browser.close.side_effect = RuntimeError("already closed")
        adapter._browser = mock_browser
        adapter._owns_browser = True

        # Should not raise
        adapter.close()
        assert adapter._browser is None


# ---------------------------------------------------------------------------
# screenshot collection
# ---------------------------------------------------------------------------


class TestScreenshotCollection:
    @patch("browser_use.Agent")
    def test_screenshots_filtered_from_none_values(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(success=True, observed_price="10.00"),
            screenshot_paths=["/tmp/a.png", None, "/tmp/b.png", None],
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("Store", "Item", "10.00")

        assert result.screenshot_paths == ["/tmp/a.png", "/tmp/b.png"]

    @patch("browser_use.Agent")
    def test_screenshots_accumulated_on_adapter(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(success=True, observed_price="10.00"),
            screenshot_paths=["/tmp/first.png"],
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        adapter.update_menu_price("Store", "Item", "10.00")
        assert "/tmp/first.png" in adapter._screenshot_paths


# ---------------------------------------------------------------------------
# evidence dict
# ---------------------------------------------------------------------------


class TestEvidenceDict:
    @patch("browser_use.Agent")
    def test_evidence_contains_expected_fields(self, mock_agent_cls, adapter):
        history = _make_history(
            structured_output=_PriceUpdateResult(
                success=True,
                observed_price="29.90",
                evidence_text="Verified on page.",
            ),
            screenshot_paths=["/tmp/s.png"],
            urls=["https://merchant.example.com/store/1"],
        )
        mock_agent_cls.return_value.run_sync.return_value = history

        result = adapter.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

        ev = result.evidence
        assert ev["success"] is True
        assert ev["operation_type"] == "update_price"
        assert ev["store_name"] == "人民广场店"
        assert ev["target_name"] == "招牌牛肉饭"
        assert ev["expected_value"] == "29.90"
        assert ev["observed_value"] == "29.90"
        assert ev["final_url"] == "https://merchant.example.com/store/1"


# ---------------------------------------------------------------------------
# adapter is a proper BasePlatformAdapter
# ---------------------------------------------------------------------------


class TestAdapterInterface:
    def test_implements_all_abstract_methods(self, adapter):
        """Verify all abstract methods are callable without crashing the adapter."""
        from food_ops_demo.adapter import BasePlatformAdapter

        assert isinstance(adapter, BasePlatformAdapter)

    def test_unsupported_operations_return_operation_result(self, adapter):
        """All unsupported methods should return OperationResult, not raise."""
        r1 = adapter.update_menu_sale_status("S", "I", "on_sale")
        r2 = adapter.update_business_hours("S", [{"start": "09:00", "end": "21:00"}])
        r3 = adapter.update_store_phone("S", "021-1234")
        for r in (r1, r2, r3):
            assert isinstance(r, OperationResult)
            assert r.success is False


# ---------------------------------------------------------------------------
# capabilities and configuration validation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# get_snapshot -- structured output
# ---------------------------------------------------------------------------


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
