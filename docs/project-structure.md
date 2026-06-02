# 项目内容整理

更新时间：2026-06-02
当前分支：`main`
合并提交：`14a9396 merge: phase 2 local ops workbench`

## 当前定位

本项目是外卖运营 Agent 的本地 MVP 工作台，用 FastAPI + SQLite + 静态 HTML 页面验证一个可回放的运营闭环：

```text
自然语言指令 -> 标准操作计划 -> 风险校验 -> 人工确认 -> FakeAdapter 执行 -> 回读校验 -> 审计留痕
```

当前版本支持 FakeAdapter、MockWebAdapter 和 ShadowMode 三种执行模式。ShadowMode 只读取、定位、预填和截图，不点击保存或提交。不接真实外卖平台、真实 LLM 或多用户权限体系。

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
- `food_ops_demo.static.mock_merchant.html`：本地仿真商家后台，用于 Playwright 点击、截图和异常注入。

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
72 passed
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

