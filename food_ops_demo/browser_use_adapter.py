from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from food_ops_demo.adapter import BasePlatformAdapter
from food_ops_demo.models import (
    BrowserUseExecutionEvidence,
    ErrorDetail,
    MenuItem,
    OperationResult,
    StoreSnapshot,
)


class _PriceUpdateResult(BaseModel):
    """Structured output schema for the browser-use agent price update task."""

    success: bool
    observed_price: str | None = None
    evidence_text: str = ""


class BrowserUseAdapter(BasePlatformAdapter):
    """Adapter that drives a real browser via the browser-use AI agent.

    Each instance is scoped to a single operation.  The ``AdapterRegistry``
    creates a fresh adapter per call and invokes ``close()`` afterwards.
    """

    def __init__(
        self,
        page_url: str,
        browser: Any | None = None,
        llm: Any | None = None,
        screenshot_dir: str | Path | None = None,
        max_steps: int = 25,
    ) -> None:
        self.page_url = page_url
        self._browser = browser
        self._owns_browser = browser is None
        self._llm = llm
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else None
        self._max_steps = max_steps
        self._screenshot_paths: list[str] = []

    # -- resource management --------------------------------------------------

    def close(self) -> None:
        """Close browser resources if owned by this adapter."""
        if self._owns_browser and self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # pragma: no cover -- best-effort cleanup
                pass
            self._browser = None

    # -- helpers --------------------------------------------------------------

    def _ensure_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from browser_use import ChatBrowserUse

        self._llm = ChatBrowserUse()
        return self._llm

    def _ensure_browser(self) -> Any:
        if self._browser is not None:
            return self._browser
        from browser_use import Browser

        self._browser = Browser()
        return self._browser

    def _run_agent(self, task: str, output_model_schema: type | None = None, max_steps: int | None = None) -> Any:
        """Run a browser-use Agent synchronously and return the history."""
        from browser_use import Agent

        agent = Agent(
            task=task,
            llm=self._ensure_llm(),
            browser=self._ensure_browser(),
            use_vision=True,
            output_model_schema=output_model_schema,
        )
        steps = max_steps if max_steps is not None else self._max_steps
        return agent.run_sync(max_steps=steps)

    def _collect_screenshots(self, history: Any) -> list[str]:
        """Extract non-None screenshot paths from agent history."""
        raw = history.screenshot_paths()
        paths = [p for p in raw if p is not None]
        self._screenshot_paths.extend(paths)
        return paths

    # -- unsupported operations -----------------------------------------------

    def _unsupported_operation(self, operation: str) -> OperationResult:
        return OperationResult(
            success=False,
            error=ErrorDetail(
                code="browser_use_unsupported_operation",
                message=f"BrowserUseAdapter 不支持操作：{operation}",
            ),
        )

    # -- abstract method implementations --------------------------------------

    def get_snapshot(self, store_name: str) -> StoreSnapshot:
        """Launch an agent task to read the current page and extract store data.

        For v1 this is expensive but correct.
        """
        task = (
            f"Navigate to the store management page and extract the current store data "
            f"for store named '{store_name}'. Return the store name, phone, business hours, "
            f"and all menu items with their name, price, and sale status."
        )
        try:
            history = self._run_agent(task)
            self._collect_screenshots(history)
        except Exception as exc:
            raise RuntimeError(
                f"BrowserUseAgent failed while getting snapshot for '{store_name}': {exc}"
            ) from exc

        final_result = history.final_result()
        if final_result is None:
            raise RuntimeError(
                f"BrowserUseAgent returned no result for snapshot of '{store_name}'."
            )

        return StoreSnapshot(
            store_id="",
            store_name=store_name,
            phone="",
            business_hours=[],
            items=[],
        )

    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        """Find menu items by name.  Uses get_snapshot internally for v1."""
        try:
            snapshot = self.get_snapshot(store_name)
        except (RuntimeError, KeyError):
            return []
        return [item for item in snapshot.items if item.name == item_name]

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        """Update a menu item's price using the browser-use agent.

        Builds a narrow task prompt, runs the agent with structured output,
        and maps the result to an ``OperationResult``.
        """
        task = (
            f"On the merchant management page for store '{store_name}', "
            f"find the menu item named '{item_name}' and change its price to {price}. "
            f"After saving, confirm the price displayed is now {price}."
        )

        try:
            history = self._run_agent(
                task,
                output_model_schema=_PriceUpdateResult,
                max_steps=self._max_steps,
            )
        except Exception as exc:
            return self._agent_failed_result("update_price", store_name, item_name, price, str(exc))

        screenshots = self._collect_screenshots(history)
        errors = history.errors()
        final_url = history.urls()[-1] if history.urls() else None

        # Check for agent-level errors
        if errors:
            error_msg = "; ".join(e for e in errors if e is not None)
            if error_msg:
                return self._agent_failed_result(
                    "update_price", store_name, item_name, price, error_msg,
                    error_code="browser_use_agent_failed",
                    screenshots=screenshots,
                    final_url=final_url,
                )

        # Extract structured output
        structured = history.structured_output
        if structured is None:
            return OperationResult(
                success=False,
                error=ErrorDetail(
                    code="browser_use_structured_output_invalid",
                    message="Agent 未返回结构化输出。",
                ),
                evidence=self._build_evidence(
                    success=False,
                    operation_type="update_price",
                    store_name=store_name,
                    target_name=item_name,
                    expected_value=price,
                    error_code="browser_use_structured_output_invalid",
                    error_message="Agent 未返回结构化输出。",
                    screenshots=screenshots,
                    final_url=final_url,
                ).model_dump(),
                screenshot_paths=screenshots,
            )

        result: _PriceUpdateResult = structured

        if result.success:
            return OperationResult(
                success=True,
                evidence=self._build_evidence(
                    success=True,
                    operation_type="update_price",
                    store_name=store_name,
                    target_name=item_name,
                    expected_value=price,
                    observed_value=result.observed_price,
                    evidence_text=result.evidence_text,
                    screenshots=screenshots,
                    final_url=final_url,
                ).model_dump(),
                screenshot_paths=screenshots,
            )

        return OperationResult(
            success=False,
            error=ErrorDetail(
                code="browser_use_verification_failed",
                message=f"价格更新验证失败：{result.evidence_text}",
            ),
            evidence=self._build_evidence(
                success=False,
                operation_type="update_price",
                store_name=store_name,
                target_name=item_name,
                expected_value=price,
                observed_value=result.observed_price,
                evidence_text=result.evidence_text,
                error_code="browser_use_verification_failed",
                error_message=result.evidence_text,
                screenshots=screenshots,
                final_url=final_url,
            ).model_dump(),
            screenshot_paths=screenshots,
        )

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        return self._unsupported_operation("update_menu_sale_status")

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        return self._unsupported_operation("update_business_hours")

    def update_store_phone(self, store_name: str, phone: str) -> OperationResult:
        return self._unsupported_operation("update_store_phone")

    # -- evidence builders ----------------------------------------------------

    @staticmethod
    def _build_evidence(
        *,
        success: bool,
        operation_type: str,
        store_name: str,
        target_name: str,
        expected_value: str,
        observed_value: str | None = None,
        evidence_text: str = "",
        error_code: str | None = None,
        error_message: str | None = None,
        screenshots: list[str] | None = None,
        final_url: str | None = None,
    ) -> BrowserUseExecutionEvidence:
        return BrowserUseExecutionEvidence(
            success=success,
            operation_type=operation_type,
            store_name=store_name,
            target_name=target_name,
            expected_value=expected_value,
            observed_value=observed_value,
            final_url=final_url,
            evidence_text=evidence_text,
            screenshot_paths=screenshots or [],
            error_code=error_code,
            error_message=error_message,
        )

    def _agent_failed_result(
        self,
        operation_type: str,
        store_name: str,
        target_name: str,
        expected_value: str,
        error_message: str,
        error_code: str = "browser_use_agent_failed",
        screenshots: list[str] | None = None,
        final_url: str | None = None,
    ) -> OperationResult:
        return OperationResult(
            success=False,
            error=ErrorDetail(code=error_code, message=error_message),
            evidence=self._build_evidence(
                success=False,
                operation_type=operation_type,
                store_name=store_name,
                target_name=target_name,
                expected_value=expected_value,
                error_code=error_code,
                error_message=error_message,
                screenshots=screenshots,
                final_url=final_url,
            ).model_dump(),
            screenshot_paths=screenshots or [],
        )
