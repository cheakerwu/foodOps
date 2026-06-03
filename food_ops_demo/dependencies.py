from __future__ import annotations

from dataclasses import dataclass

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry
from food_ops_demo.audit import AuditLog
from food_ops_demo.browser_use_adapter import BrowserUseAdapter
from food_ops_demo.config import FoodOpsSettings
from food_ops_demo.constants import AdapterMode
from food_ops_demo.mock_web_adapter import MockWebAdapter
from food_ops_demo.shadow_adapter import ShadowPlatformAdapter
from food_ops_demo.storage import DemoDatabase
from food_ops_demo.workflow import TaskManager


@dataclass
class AppServices:
    settings: FoodOpsSettings
    database: DemoDatabase
    fake_adapter: FakePlatformAdapter
    adapter_registry: AdapterRegistry
    audit_log: AuditLog
    task_manager: TaskManager


def build_services(settings: FoodOpsSettings) -> AppServices:
    database = DemoDatabase(settings.database_path)
    fake_adapter = FakePlatformAdapter(database=database)
    adapter_registry = AdapterRegistry(
        {
            AdapterMode.FAKE: lambda: fake_adapter,
            AdapterMode.MOCK_WEB: lambda: MockWebAdapter(
                page_url=settings.mock_web_url,
                screenshot_dir=settings.mock_web_screenshot_dir,
                headless=settings.mock_web_headless,
                database=database,
            ),
            AdapterMode.SHADOW: lambda: ShadowPlatformAdapter(
                page_url=settings.shadow_url,
                screenshot_dir=settings.shadow_screenshot_dir,
                headless=settings.shadow_headless,
            ),
            AdapterMode.BROWSER_USE: lambda: BrowserUseAdapter(
                page_url=settings.browser_use_url,
                screenshot_dir=settings.browser_use_screenshot_dir,
                max_steps=settings.browser_use_max_steps,
            ),
        },
        shared_modes={AdapterMode.FAKE},
    )
    audit_log = AuditLog(settings.audit_path)
    task_manager = TaskManager(
        adapter=fake_adapter,
        adapter_registry=adapter_registry,
        default_adapter_mode=AdapterMode.FAKE,
        audit_log=audit_log,
        database=database,
    )
    return AppServices(
        settings=settings,
        database=database,
        fake_adapter=fake_adapter,
        adapter_registry=adapter_registry,
        audit_log=audit_log,
        task_manager=task_manager,
    )
