# 外卖运营 Agent 工作台

本仓库当前实现一个最小本地 MVP，用于验证外卖/本地生活运营 Agent 的核心闭环：

```text
自然语言指令 -> 标准操作计划 -> 风险校验 -> 人工确认 -> FakeAdapter 执行 -> 回读校验 -> 审计留痕
```

第一版不接真实外卖平台、不接 Playwright、不接真实 LLM、不引入数据库。

## 当前能力

- 支持本地规则解析中文运营指令。
- 支持单门店 Mock 数据：`人民广场店`。
- 支持菜品改价、菜品上下架、营业时间修改。
- 支持风险分级和人工确认。
- 支持模拟登录失效、人工处理后继续执行。
- 支持 JSONL 审计记录。
- 提供 FastAPI 接口和单页静态工作台。

## 本地环境

推荐使用已配置的 Conda 环境解释器：

```powershell
E:\anaconda\envs\jobhellper\python.exe
```

安装开发依赖：

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pip install -e ".[dev]"
```

运行测试：

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m pytest -v
```

启动本地工作台：

```powershell
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --reload --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765
```

## Phase 2 本地演示流程

1. 按上面的命令启动本地工作台。
2. 在页面中点击“重置演示数据”。
3. 输入并执行联系电话更新指令：

   ```text
   把人民广场店联系电话改成 021-66668888
   ```

4. 输入并执行售罄更新指令：

   ```text
   把人民广场店的可乐设为售罄
   ```

5. 打开`任务中心`，选择并检查最近任务。
6. 确认页面中可以看到对应的审计记录。

## Phase 3 MockWebAdapter 演示流程

1. 安装 Playwright 依赖：

   ```powershell
   & 'E:\anaconda\envs\jobhellper\python.exe' -m pip install -e ".[dev]"
   & 'E:\anaconda\envs\jobhellper\python.exe' -m playwright install chromium
   ```

2. 启动本地工作台：

   ```powershell
   & 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
   ```

3. 打开 `http://127.0.0.1:8765/`。
4. 在执行模式中选择 `MockWebAdapter`。
5. 点击 `打开 Mock 后台`，确认本地 mock 商家后台能打开。
6. 运行指令：`把人民广场店的招牌牛肉饭改成 29.9`。
7. 确认任务执行成功，任务中心出现 `mock_web` 任务。
8. 打开 `data/demo/mock-web-screenshots/`，确认存在最新执行截图。

## Phase 4 Shadow Mode 演示流程

Shadow Mode 用于真实后台接入前的安全验证：系统会打开目标后台页面、读取当前数据、定位并预填目标值、截图留证，然后停在 `pending_review`。系统不会点击保存或提交。

本地演示默认指向 mock 商家后台：

```powershell
$env:FOOD_OPS_SHADOW_URL='http://127.0.0.1:8765/mock/merchant'
$env:FOOD_OPS_SHADOW_SCREENSHOT_DIR='data/demo/shadow-mode-evidence'
$env:FOOD_OPS_SHADOW_HEADLESS='1'
& 'E:\anaconda\envs\jobhellper\python.exe' -m uvicorn food_ops_demo.asgi:app --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765/` 后：

1. 执行模式选择 `ShadowMode`。
2. 输入 `把人民广场店的招牌牛肉饭改成 29.9`。
3. 点击 `生成计划`。
4. 点击 `开始预填`。
5. 任务状态应停在 `pending_review`。
6. `data/demo/shadow-mode-evidence/shadow-prefill-price.png` 应显示目标价格已预填为 `29.90`。
7. mock 门店快照仍应保留原价格 `32.00`，证明没有提交。

如果要指向真实后台，只修改 `FOOD_OPS_SHADOW_URL`。真实后台 Shadow Mode 仍然只预填不提交，提交动作必须由人工在后台完成或放弃。

## 示例指令

```text
把人民广场店的招牌牛肉饭改成 29.9
把人民广场店的可乐下架
把人民广场店的可乐上架
把人民广场店营业时间改成 10:00 到 21:00
```

## 主要目录

- `food_ops_demo/`：MVP 应用代码。
- `food_ops_demo/static/index.html`：单页工作台。
- `tests/`：自动化测试。
- `docs/food-ops-agent/`：原对话迁移资料和 PRD。
- `docs/superpowers/`：本次 MVP 设计和实现计划。

## 迁移资料

本目录用于承接原 Codex 对话 `019e7e65-bbd4-7601-a3d8-13fc2d1027c5` 中关于“电商/外卖运营自动化 Agent”的讨论资料。

已迁移文件：

- `docs/food-ops-agent/conversation-migration.md`：按原对话顺序整理的核心结论、架构、部署、测试和落地路线。
- `docs/food-ops-agent/food-ops-agent-local-demo-prd.md`：原对话生成的本地测试 Demo PRD。
- `docs/food-ops-agent/food-ops-agent-architecture.html`：原对话生成的可视化架构 HTML，可直接用浏览器打开。

原对话工作目录：`D:\code\job_helper`  
当前迁移目录：`D:\code\demov1`
