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
        item = self._find_one(store_name, item_name)
        if item is None:
            return _not_found()
        page = self._ensure_page()
        page.locator(f'[data-testid="price-input-{item.item_id}"]').fill(price)
        page.locator(f'[data-testid="save-price-button-{item.item_id}"]').click()
        return self._result_from_status()

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
        error_toast = page.locator(".toast-error")
        if error_toast.count() and error_toast.is_visible():
            text = error_toast.inner_text()
            if "登录已过期" in text:
                return OperationResult(
                    success=False,
                    error=ErrorDetail(code="auth_required", message="Mock 后台登录已过期，需要人工处理。"),
                )
            if "保存失败" in text:
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


def _raw_to_snapshot(raw: dict) -> StoreSnapshot:
    """Transform the page's camelCase snapshot into a StoreSnapshot."""
    items = []
    for item_id, item_data in raw.get("items", {}).items():
        items.append(
            MenuItem(
                item_id=item_id,
                store_id=raw.get("storeId", ""),
                name=item_data["name"],
                price=f'{item_data["price"]:.2f}',
                sale_status=item_data.get("saleStatus", "on_sale"),
                image="",
            )
        )
    return StoreSnapshot(
        store_id=raw.get("storeId", ""),
        store_name=raw.get("storeName", ""),
        phone=raw.get("phone", ""),
        business_hours=raw.get("businessHours", []),
        items=items,
    )


def _not_found() -> OperationResult:
    return OperationResult(
        success=False,
        error=ErrorDetail(code="target_not_found", message="找不到目标菜品。"),
    )


