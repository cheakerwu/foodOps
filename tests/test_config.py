from __future__ import annotations

import pytest

from food_ops_demo.config import FoodOpsSettings


def test_settings_defaults_are_v1_ready(monkeypatch):
    for key in [
        "FOOD_OPS_ENV",
        "FOOD_OPS_API_PREFIX",
        "FOOD_OPS_DATA_DIR",
        "FOOD_OPS_DATABASE_PATH",
        "FOOD_OPS_AUDIT_PATH",
        "FOOD_OPS_BROWSER_USE_MAX_STEPS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = FoodOpsSettings.from_env()

    assert settings.env == "local"
    assert settings.api_prefix == "/api/v1"
    assert settings.data_dir.as_posix() == "data/local"
    assert settings.database_path.as_posix() == "data/local/food_ops.sqlite3"
    assert settings.audit_path.as_posix() == "data/local/audit.jsonl"
    assert settings.browser_use_max_steps == 25
    assert settings.browser_use_url == "http://127.0.0.1:8765/mock/merchant"


def test_settings_accept_legacy_demo_paths(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_DATABASE_PATH", "data/demo/demo.sqlite3")
    monkeypatch.setenv("FOOD_OPS_AUDIT_PATH", "data/demo/audit.jsonl")

    settings = FoodOpsSettings.from_env()

    assert settings.database_path.as_posix() == "data/demo/demo.sqlite3"
    assert settings.audit_path.as_posix() == "data/demo/audit.jsonl"


def test_settings_reject_invalid_browser_use_steps(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_BROWSER_USE_MAX_STEPS", "many")

    with pytest.raises(ValueError, match="FOOD_OPS_BROWSER_USE_MAX_STEPS must be an integer"):
        FoodOpsSettings.from_env()


def test_settings_reject_api_prefix_without_leading_slash(monkeypatch):
    monkeypatch.setenv("FOOD_OPS_API_PREFIX", "api/v1")

    with pytest.raises(ValueError, match="FOOD_OPS_API_PREFIX must start with '/'"):
        FoodOpsSettings.from_env()
