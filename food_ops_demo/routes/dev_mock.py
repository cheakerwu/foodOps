from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from food_ops_demo.constants import DEFAULT_STORE_NAME
from food_ops_demo.dependencies import AppServices


def _inject_mock_state(html: str, state: dict[str, Any]) -> str:
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    script = f"<script>window.__MOCK_MERCHANT_INITIAL_STATE__={state_json};</script>"
    return html.replace("<head>", f"<head>\n  {script}", 1)


def _mock_state_from_snapshot(snapshot) -> dict[str, Any]:
    return {
        "storeId": snapshot.store_id,
        "storeName": snapshot.store_name,
        "phone": snapshot.phone,
        "businessHours": snapshot.business_hours,
        "items": {
            item.item_id: {
                "name": item.name,
                "price": float(item.price),
                "saleStatus": item.sale_status,
            }
            for item in snapshot.items
        },
        "scenario": None,
    }


def build_router(services: AppServices, mock_merchant_page: Path) -> APIRouter:
    router = APIRouter()
    fake_adapter = services.fake_adapter

    @router.get("/mock/merchant", response_class=HTMLResponse)
    def mock_merchant() -> str:
        html = mock_merchant_page.read_text(encoding="utf-8")
        state = _mock_state_from_snapshot(fake_adapter.get_snapshot(DEFAULT_STORE_NAME))
        return _inject_mock_state(html, state)

    @router.get("/api/mock/merchant/snapshot")
    def mock_merchant_snapshot() -> dict[str, Any]:
        return _mock_state_from_snapshot(fake_adapter.get_snapshot(DEFAULT_STORE_NAME))

    return router
