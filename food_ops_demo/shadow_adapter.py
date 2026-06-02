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
        snapshot = self.get_snapshot(store_name)
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
                "original_value": snapshot.business_hours,
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
