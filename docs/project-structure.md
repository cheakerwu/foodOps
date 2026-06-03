# 项目内容整理

更新时间：2026-06-03
当前定位：正式版 V1 验证构建
当前验收基线：`183 passed, 1 xpassed`，且 V1 完成后不应存在 browser-use close RuntimeWarning。

## 当前定位

本项目是外卖运营 Agent 的正式版 V1 验证构建，用 FastAPI + SQLite + 静态 HTML 页面验证一个可回放的运营闭环：

```text
自然语言指令 -> 标准操作计划 -> 风险校验 -> 人工确认 -> 任务入队/执行 -> 回读校验 -> 证据与审计留痕
```

当前版本支持 FakeAdapter、MockWebAdapter、ShadowMode 和 BrowserUseAdapter 四种执行模式。ShadowMode 只读取、定位、预填和截图，不点击保存或提交。BrowserUseAdapter 通过 browser-use AI 代理驱动真实浏览器，当前正式支持菜品改价操作。

## 控制面与执行面

- 控制面：FastAPI 负责解析、校验、审批、入队、任务状态和审计查询。
- 执行面：LocalRunner 负责获取 queued job、创建 scoped adapter、执行浏览器操作、回写任务状态和审计证据。
- 真实平台 adapter 不应作为 FastAPI 全局单例长期持有浏览器会话。

## 目录结构

```text
D:\code\demov1
├── README.md
├── pyproject.toml
├── .env.example
├── food_ops_demo/
│   ├── app.py              # FastAPI app factory and API routes
│   ├── asgi.py             # Uvicorn runtime entrypoint
│   ├── adapter.py          # BasePlatformAdapter and FakePlatformAdapter
│   ├── audit.py            # JSONL audit log reader/writer
│   ├── models.py           # Pydantic request, plan, task, snapshot models
│   ├── mock_web_adapter.py # MockWebAdapter with Playwright fault injection
│   ├── shadow_adapter.py   # ShadowPlatformAdapter: read-only prefill with screenshots
│   ├── browser_use_adapter.py # BrowserUseAdapter: AI agent-driven via browser-use (experimental)
│   ├── parser.py           # Rule-based Chinese instruction parser
│   ├── risk.py             # Risk validation and preview generation
│   ├── storage.py          # SQLite demo data and task persistence
│   ├── workflow.py         # Task state machine, execution, verification
│   └── static/
│       ├── index.html      # Vanilla HTML/CSS/JS workbench
│       └── mock_merchant.html  # Simulated merchant backend for Playwright
├── tests/
│   ├── test_adapter.py
│   ├── test_adapter_contract.py
│   ├── test_api.py
│   ├── test_mock_merchant_page.py
│   ├── test_mock_web_adapter.py
│   ├── test_parser.py
│   ├── test_playwright_dependency.py
│   ├── test_risk.py
│   ├── test_static_page.py
│   ├── test_storage.py
│   ├── test_workflow.py
│   └── test_workflow_adapter_modes.py
└── docs/
    ├── food-ops-agent/     # Migrated source discussion and PRD artifacts
    └── superpowers/        # Implementation plans, specs, and checkpoints
```

## 主要模块职责

- `food_ops_demo.app.create_app()`：构建 FastAPI 应用，统一创建 `DemoDatabase`、`FakePlatformAdapter`、`TaskManager` 和 `AuditLog`。
- `food_ops_demo.asgi`：运行入口，避免导入 `food_ops_demo.app` 时自动创建默认数据库。
- `food_ops_demo.storage.DemoDatabase`：管理 SQLite schema、种子数据、重置、菜单/门店更新、任务保存和任务列表。
- `food_ops_demo.adapter.FakePlatformAdapter`：提供内存模式和 SQLite 模式，两者由契约测试保持行为一致。
- `food_ops_demo.workflow.TaskManager`：维护任务状态流转、人工介入、执行、回读验证和任务持久化。
- `food_ops_demo.parser`：把中文运营指令解析为标准 `OperationPlan`。
- `food_ops_demo.risk`：生成风险等级、审批要求和变更预览。
- `food_ops_demo.static.index.html`：本地工作台页面，包含指令输入、人工确认、任务中心、快照和审计结果。
- `food_ops_demo.mock_web_adapter.MockWebAdapter`：通过 Playwright 驱动本地 mock 商家后台页面，验证未来真实 RPA 适配器的执行边界。
- `food_ops_demo.shadow_adapter.ShadowPlatformAdapter`：Phase 4 的只读/预填适配器，通过 Playwright 打开配置的后台页面，预填低风险输入并截图，明确返回 `submitted=false`。
- `food_ops_demo.browser_use_adapter.BrowserUseAdapter`：Phase 5 的实验性适配器，通过 browser-use AI 代理驱动真实浏览器完成操作。默认使用 `ChatBrowserUse` 模型，支持云端浏览器（`Browser(use_cloud=True)`）。当前仅支持菜品改价操作。需要安装 `browser-use` 包和设置 `BROWSER_USE_API_KEY` 环境变量。
- `food_ops_demo.adapter_registry.AdapterRegistry`：创建共享非浏览器适配器和作用域浏览器适配器，使 Playwright 状态不由 FastAPI 路由全局持有。
- `food_ops_demo.orchestration`：将多门店改价分解为子操作计划和锁键。
- `food_ops_demo.runner.LocalRunner`：本地执行面原型，获取排队的任务、拥有适配器生命周期并记录完成状态。
- `operation_jobs` SQLite 表：本地队列，用于建模未来 runner 调度和按门店加锁。
- `food_ops_demo.static.mock_merchant.html`：本地仿真商家后台，用于 Playwright 点击、截图和异常注入。

## 适配器模式

| 模式 | 说明 | 默认 |
|------|------|------|
| `fake` | 内存模式，无浏览器 | 是 |
| `mock_web` | Playwright 驱动本地 mock 页面 | 否 |
| `shadow` | Playwright 只读/预填，不提交 | 否 |
| `browser_use` | AI 代理驱动真实浏览器（实验性） | 否 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FOOD_OPS_DATABASE_PATH` | SQLite 数据库路径 | `data/demo/demo.sqlite3` |
| `FOOD_OPS_AUDIT_PATH` | 审计日志路径 | `data/demo/audit.jsonl` |
| `FOOD_OPS_MOCK_WEB_URL` | MockWebAdapter 目标地址 | `http://127.0.0.1:8765/mock/merchant` |
| `FOOD_OPS_MOCK_WEB_SCREENSHOT_DIR` | MockWeb 截图目录 | `data/demo/mock-web-screenshots` |
| `FOOD_OPS_MOCK_WEB_HEADLESS` | MockWeb 无头模式 | `1` |
| `FOOD_OPS_SHADOW_URL` | Shadow 目标地址 | 同 MOCK_WEB_URL |
| `FOOD_OPS_SHADOW_SCREENSHOT_DIR` | Shadow 截图目录 | `data/demo/shadow-mode-evidence` |
| `FOOD_OPS_SHADOW_HEADLESS` | Shadow 无头模式 | `1` |
| `FOOD_OPS_BROWSER_USE_URL` | BrowserUse 目标地址 | `http://127.0.0.1:8765/mock/merchant` |
| `FOOD_OPS_BROWSER_USE_SCREENSHOT_DIR` | BrowserUse 截图目录 | `data/demo/browser-use-screenshots` |
| `FOOD_OPS_BROWSER_USE_MAX_STEPS` | BrowserUse 单次最大步数 | `25` |
| `BROWSER_USE_API_KEY` | browser-use LLM API 密钥 | 必填（使用 browser_use 模式时） |

## 已支持指令

```text
把人民广场店的招牌牛肉饭改成 29.9
把人民广场店的可乐下架
把人民广场店的可乐上架
把人民广场店的可乐设为售罄
把人民广场店的可乐恢复销售
把人民广场店营业时间改成 10:00 到 21:00
把人民广场店联系电话改成 021-66668888
```

## 本地运行

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765/
```

## 验证命令

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -v
```

当前 `main` 合并后验证结果：

```text
183 passed, 1 xpassed
```

## 本地运行产物

以下目录和文件属于本地运行/工具缓存，不进入 Git：

```text
.codegraph/
.pytest_cache/
.venv/
data/
food_ops_demo.egg-info/
food_ops_demo/__pycache__/
tests/__pycache__/
```

其中 `data/demo/` 存放演示数据库、审计日志、服务 PID 和验收截图。它们用于本地回放，不作为源码提交。

- `data/demo/shadow-mode-evidence/`：本地 Shadow Mode 截图证据目录，不进入 Git。

## 后续开发建议

- 将任务中心从“最近任务列表”扩展为可选择的任务详情浏览。
- 为审计结果增加更紧凑的展示格式，避免直接显示完整 JSON。
- 在真实平台适配前继续保持 adapter contract tests，新增平台适配器时必须先满足同一套契约。
- 如接入真实 LLM，建议继续保留规则解析器作为 deterministic fallback 和测试基准。

