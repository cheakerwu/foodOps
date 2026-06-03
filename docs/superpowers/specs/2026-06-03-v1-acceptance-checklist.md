# V1 验收清单

日期：2026-06-03
定位：正式版 V1 验证构建

## 自动化验证

- [ ] `pytest -v` 全量通过，基线为 `183 passed, 1 xpassed`。
- [ ] V1 完成后不应存在 browser-use close RuntimeWarning。
- [ ] `tests/test_v1_docs.py` 通过，确认文档和元数据已更新为 V1 定位。

## 本地适配器路径

- [ ] `FakeAdapter`：内存模式，无浏览器，用于单元测试和快速验证。
- [ ] `MockWebAdapter`：Playwright 驱动本地 mock 商家后台，验证 RPA 执行边界。
- [ ] `ShadowMode`：只读/预填，截图留证，不提交，用于真实后台接入前的安全验证。
- [ ] `BrowserUseAdapter`：通过 browser-use AI 代理驱动真实浏览器，当前仅支持 `menu.update_price`。

## 真实平台就绪

- [ ] `menu.update_price`：BrowserUseAdapter 正式支持，产生结构化结果、最终 URL、观测值、截图路径和审计记录。
- [ ] `menu.update_sale_status`：返回明确错误 `browser_use_unsupported_operation`。
- [ ] `store.update_business_hours`：返回明确错误 `browser_use_unsupported_operation`。
- [ ] `store.update_phone`：返回明确错误 `browser_use_unsupported_operation`。

## 证据与审计

- [ ] 每次 BrowserUseAdapter 执行都产生结构化结果。
- [ ] 截图保存到配置的目录（默认 `data/demo/browser-use-screenshots/`）。
- [ ] 审计记录包含任务 ID、操作类型、执行状态、截图路径和错误信息（如有）。
- [ ] `audit.jsonl` 记录所有任务状态变更。

## 控制面与执行面

- [ ] FastAPI 负责解析、校验、审批、入队、任务状态和审计查询。
- [ ] LocalRunner 负责获取 queued job、创建 scoped adapter、执行浏览器操作、回写任务状态和审计证据。
- [ ] 真实平台 adapter 不作为 FastAPI 全局单例长期持有浏览器会话。

## API 命名空间

- [ ] `/api/v1/*`：正式 V1 控制面接口。
- [ ] `/api/demo/*`：本地兼容接口，保留给既有验收脚本和演示页面。
- [ ] `/mock/merchant`：开发用 Mock 商家后台，不作为真实平台接口。
