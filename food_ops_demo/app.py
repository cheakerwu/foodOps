from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from food_ops_demo.config import FoodOpsSettings
from food_ops_demo.dependencies import build_services
from food_ops_demo.routes import dev_mock, health, tasks


def create_app(
    settings: FoodOpsSettings | None = None,
    # Legacy kwargs for backward compatibility with existing tests
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
    shadow_url: str | None = None,
    shadow_screenshot_dir: str | Path | None = None,
    browser_use_url: str | None = None,
    browser_use_screenshot_dir: str | Path | None = None,
    browser_use_max_steps: int | None = None,
) -> FastAPI:
    if settings is not None:
        base_settings = settings
    else:
        base_settings = _settings_from_kwargs(
            audit_path=audit_path,
            database_path=database_path,
            mock_web_url=mock_web_url,
            shadow_url=shadow_url,
            shadow_screenshot_dir=shadow_screenshot_dir,
            browser_use_url=browser_use_url,
            browser_use_screenshot_dir=browser_use_screenshot_dir,
            browser_use_max_steps=browser_use_max_steps,
        )

    services = build_services(base_settings)
    api_prefix = base_settings.api_prefix

    static_page = Path(__file__).parent / "static" / "index.html"
    mock_merchant_page = Path(__file__).parent / "static" / "mock_merchant.html"

    app = FastAPI(title="Food Ops Agent MVP")

    # Index route
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static_page.read_text(encoding="utf-8")

    # Health: /health and /api/v1/health
    health_router = health.build_router()
    app.include_router(health_router)
    app.include_router(health_router, prefix=api_prefix)

    # Task routes: /api/v1/* and /api/demo/*
    task_router = tasks.build_router(services)
    app.include_router(task_router, prefix=api_prefix)
    app.include_router(task_router, prefix="/api/demo")

    # Dev mock routes
    mock_router = dev_mock.build_router(services, mock_merchant_page)
    app.include_router(mock_router)

    return app


def _settings_from_kwargs(
    audit_path: str | Path | None = None,
    database_path: str | Path | None = None,
    mock_web_url: str | None = None,
    shadow_url: str | None = None,
    shadow_screenshot_dir: str | Path | None = None,
    browser_use_url: str | None = None,
    browser_use_screenshot_dir: str | Path | None = None,
    browser_use_max_steps: int | None = None,
) -> FoodOpsSettings:
    """Build FoodOpsSettings from legacy individual kwargs."""
    base = FoodOpsSettings.from_env()

    overrides: dict[str, Any] = {}
    if database_path is not None:
        overrides["database_path"] = Path(database_path)
    if audit_path is not None:
        overrides["audit_path"] = Path(audit_path)
    if mock_web_url is not None:
        overrides["mock_web_url"] = mock_web_url
    if shadow_url is not None:
        overrides["shadow_url"] = shadow_url
    if shadow_screenshot_dir is not None:
        overrides["shadow_screenshot_dir"] = Path(shadow_screenshot_dir)
    if browser_use_url is not None:
        overrides["browser_use_url"] = browser_use_url
    if browser_use_screenshot_dir is not None:
        overrides["browser_use_screenshot_dir"] = Path(browser_use_screenshot_dir)
    if browser_use_max_steps is not None:
        overrides["browser_use_max_steps"] = browser_use_max_steps

    if overrides:
        return FoodOpsSettings(**{**base.__dict__, **overrides})
    return base
