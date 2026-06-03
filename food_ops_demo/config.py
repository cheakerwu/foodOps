from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_bool(name: str, default: str) -> bool:
    return os.getenv(name, default) not in {"0", "false", "False", "no", "NO"}


def _get_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class FoodOpsSettings:
    env: str
    api_prefix: str
    data_dir: Path
    database_path: Path
    audit_path: Path
    mock_web_url: str
    mock_web_screenshot_dir: Path
    mock_web_headless: bool
    shadow_url: str
    shadow_screenshot_dir: Path
    shadow_headless: bool
    browser_use_url: str
    browser_use_screenshot_dir: Path
    browser_use_max_steps: int
    browser_use_required_api_key: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "FoodOpsSettings":
        data_dir = Path(os.getenv("FOOD_OPS_DATA_DIR", "data/local"))
        api_prefix = os.getenv("FOOD_OPS_API_PREFIX", "/api/v1")
        if not api_prefix.startswith("/"):
            raise ValueError("FOOD_OPS_API_PREFIX must start with '/'")

        mock_url = os.getenv("FOOD_OPS_MOCK_WEB_URL", "http://127.0.0.1:8765/mock/merchant")
        return cls(
            env=os.getenv("FOOD_OPS_ENV", "local"),
            api_prefix=api_prefix.rstrip("/"),
            data_dir=data_dir,
            database_path=Path(os.getenv("FOOD_OPS_DATABASE_PATH", str(data_dir / "food_ops.sqlite3"))),
            audit_path=Path(os.getenv("FOOD_OPS_AUDIT_PATH", str(data_dir / "audit.jsonl"))),
            mock_web_url=mock_url,
            mock_web_screenshot_dir=Path(
                os.getenv("FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR", str(data_dir / "mock-web-screenshots"))
            ),
            mock_web_headless=_get_bool("FOOD_OPS_MOCK_WEB_HEADLESS", "1"),
            shadow_url=os.getenv("FOOD_OPS_SHADOW_URL", mock_url),
            shadow_screenshot_dir=Path(
                os.getenv("FOOD_OPS_SHADOW_SCREENSHOT_DIR", str(data_dir / "shadow-mode-evidence"))
            ),
            shadow_headless=_get_bool("FOOD_OPS_SHADOW_HEADLESS", "1"),
            browser_use_url=os.getenv("FOOD_OPS_BROWSER_USE_URL", mock_url),
            browser_use_screenshot_dir=Path(
                os.getenv("FOOD_OPS_BROWSER_USE_SCREENSHOT_DIR", str(data_dir / "browser-use-screenshots"))
            ),
            browser_use_max_steps=_get_int("FOOD_OPS_BROWSER_USE_MAX_STEPS", "25"),
            browser_use_required_api_key=_get_bool("FOOD_OPS_BROWSER_USE_REQUIRE_API_KEY", "0"),
            log_level=os.getenv("FOOD_OPS_LOG_LEVEL", "INFO"),
        )
