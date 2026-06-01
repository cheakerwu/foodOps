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
