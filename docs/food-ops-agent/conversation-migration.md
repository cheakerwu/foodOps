# 对话迁移记录：外卖运营 Agent 工作台

源对话 ID：`019e7e65-bbd4-7601-a3d8-13fc2d1027c5`  
源工作目录：`D:\code\job_helper`  
迁移目标目录：`D:\code\demov1`  
迁移日期：`2026-06-01`

本文不是逐字聊天记录，而是把原对话中已经形成的方案、判断、架构、PRD 和落地路线迁移为当前项目可继续使用的上下文。

## 1. 原对话主题

原对话从“查找 GitHub 上是否有电商自动化仓库”开始，逐步收敛到一个更具体的产品方向：

> 基于自然语言指令的外卖/本地生活运营 Agent 工作台，用于完成门店后台标准化操作，例如菜品改价、上下架、产品图替换、营业时间修改、联系电话修改、活动基础设置，并具备审批、回读校验、审计、失败转人工和后续中台化能力。

核心对象从泛电商扩展到了国内本地生活/外卖平台，包括美团外卖、饿了么、抖音生活服务等。

## 2. GitHub 调研结论

原对话检索了电商自动化、MCP Server、n8n、Shopify、WooCommerce、Amazon SP-API、eBay、Ozon、Shopee/Lazada 等方向。

结论：

- 成熟度最高的公开参考主要集中在 `Shopify`、`WooCommerce`、`Amazon SP-API`、`eBay` 这类有明确商品/库存/价格 API 的平台。
- 更贴近 Agent 接入的项目通常是 MCP Server 或工作流编排项目。
- Shopee、Lazada、TikTok Shop/国内平台这类方向，公开可直接复用的成熟 MCP 仓库较少，更现实的路线是自行封装平台 API 或在授权前提下做 RPA 适配器。
- 不建议把大模型直接接到浏览器页面上随机点击。更稳的方式是让大模型生成结构化操作计划，后续由确定性的工具、策略引擎、适配器和工作流执行。

可参考仓库：

| 仓库 | 平台/方向 | 参考点 |
|---|---|---|
| `callobuzz/cob-shopify-mcp` | Shopify | MCP + CLI + HTTP、商品/库存/订单工具、dry-run、audit log、rate limit |
| `GeLi2001/shopify-mcp` | Shopify | 商品 CRUD、variant 价格、商品状态、库存、标签 |
| `techspawn/woocommerce-mcp-server` | WooCommerce | WordPress/WooCommerce REST API 封装为 MCP/JSON-RPC |
| `christian-ramos/mcp-amazon-sp-api` | Amazon SP-API | 写操作确认、批量价格/库存、跨 marketplace |
| `enginterzi/amazon-seller-mcp` | Amazon SP-API | listings、inventory、orders、reports，注意许可证 |
| `YosefHayim/ebay-mcp` | eBay | Sell API 工具体量大，覆盖 inventory、orders、marketing |
| `dontsovcmc/mcp-server-ozon-seller` | Ozon | Seller API MCP/CLI 参考 |
| `n8n-io/n8n` | 工作流编排 | 适合作为审批、定时、通知、跨平台编排层 |
| `czlonkowski/n8n-mcp` | n8n + MCP | 让 Agent 辅助设计和校验 n8n workflow |

## 3. 国内外卖/本地生活平台的核心判断

对于美团、饿了么、抖音生活服务等国内平台，不能默认所有操作都有稳定公开 API。需要同时考虑：

- 官方 API：优先用于商品、库存、价格、门店、活动等可授权能力。
- RPA/浏览器自动化：只作为 API 不覆盖能力的兜底，例如门店装修、部分活动配置、某些图片审核或后台专有操作。
- 人工接管：登录失效、二维码、短信验证码、滑块、人脸验证、页面改版等场景必须转人工，不应该尝试绕过。
- 审计和回读：所有写操作必须有 before/after、截图、trace、回读校验和操作人/审批人记录。

推荐总体链路：

```text
自然语言指令
  -> 意图识别与参数抽取
  -> 标准化 OperationPlan
  -> 规则校验 / 风险分级 / 权限检查
  -> 人工确认 / 审批
  -> 平台适配器 ApiAdapter 或 RpaAdapter
  -> 执行后回读校验
  -> 审计日志 / 截图 / Trace / 失败转人工
```

关键原则：

- Agent 负责理解和生成计划，不直接执行高风险写操作。
- 平台差异由 Adapter 层吸收。
- API 优先，RPA 兜底。
- 所有写操作先 preview，再 commit。
- 中高风险操作必须审批。
- 执行后必须回读验证，不以“点击了保存”作为成功标准。

## 4. 建议抽象的标准工具

原对话建议把平台动作抽象为平台无关的工具，而不是绑定某个后台页面结构：

```text
store.get_snapshot              获取门店当前状态
store.update_phone              修改联系电话
store.update_business_hours     修改营业时间
store.update_decoration         更换门店装修/头图/相册
menu.search_items               查询菜品/套餐
menu.update_price               调整菜品或 SKU 价格
menu.update_sale_status         上架、下架、售罄、恢复销售
menu.replace_image              替换菜品图
promotion.create_basic          创建基础活动
promotion.update_basic          修改基础活动
promotion.pause_or_resume       暂停/恢复活动
media.upload                    上传并校验图片素材
operation.preview               生成变更预览
operation.commit                确认执行
operation.rollback              按上次快照生成反向任务
```

每个工具都应具备这些字段：

```json
{
  "platform": "meituan | eleme | douyin_local_life",
  "store_id": "平台门店 ID",
  "target": "菜品/门店/活动/素材",
  "changes": {},
  "dry_run": true,
  "confirm_token": "人工确认后生成",
  "operator": "操作人",
  "reason": "本次修改原因"
}
```

## 5. 平台适配器设计

核心系统只依赖 `PlatformAdapter`，真实平台、Mock 平台、Fake 数据都是不同实现。

建议接口：

```ts
interface PlatformAdapter {
  getStoreSnapshot(input: GetStoreSnapshotInput): Promise<StoreSnapshot>;
  searchMenuItems(input: SearchMenuItemsInput): Promise<MenuItem[]>;
  updateMenuPrice(input: UpdateMenuPriceInput): Promise<OperationResult>;
  updateMenuSaleStatus(input: UpdateMenuSaleStatusInput): Promise<OperationResult>;
  replaceMenuImage(input: ReplaceMenuImageInput): Promise<OperationResult>;
  updateBusinessHours(input: UpdateBusinessHoursInput): Promise<OperationResult>;
  updateStorePhone(input: UpdateStorePhoneInput): Promise<OperationResult>;
  createBasicPromotion(input: CreatePromotionInput): Promise<OperationResult>;
  verifyOperation(input: VerifyOperationInput): Promise<VerificationResult>;
}
```

建议先做三种实现：

```text
FakePlatformAdapter
  纯内存/数据库模拟，不打开浏览器。

MockWebPlatformAdapter
  操作本地仿真的商家后台页面。

RealRpaPlatformAdapter
  未来接真实美团/饿了么/抖音后台。
```

这样没有真实商家后台时，也可以先实现和验证 70%-80% 的核心系统。

## 6. 无真实商家后台时的验证方式

原对话重点确认：没有真实商家后台时，不应该卡住项目，可以先把核心模块解耦并验证。

建议测试路径：

```text
阶段 1：纯核心链路
自然语言 -> 标准计划 -> 审批 -> FakeAdapter -> 审计

阶段 2：仿真后台
自然语言 -> 标准计划 -> MockWebAdapter -> Playwright -> 截图校验

阶段 3：异常场景
验证码、登录过期、同名菜品、保存失败、审核中、权限不足

阶段 4：真实后台 Shadow Mode
只读、定位、预填，不提交

阶段 5：真实后台低风险自动化
单菜品改价、单菜品上下架，逐步开放
```

需要准备的测试资产：

- 自然语言指令样本库。
- Golden Plan 文件，用来对比结构化计划。
- Adapter 契约测试。
- 工作流状态机测试。
- Mock 后台页面。
- Playwright 截图和 trace。
- 故障注入场景，例如登录过期、同名菜品、权限不足、保存失败、审核中。

建议的自然语言样本：

```text
把人民广场店的招牌牛肉饭改成 29.9
把所有门店的可乐下架
把五角场店明天营业时间改成 11 点到 20 点
把宫保鸡丁图片换成素材库里的新版图
把所有套餐涨价 2 元，但不要改饮料
把浦东三家店的联系电话改成 400-xxx
创建满 50 减 5 的活动，明天开始，持续 7 天
把所有售罄商品恢复上架
```

## 7. 任务状态机

原对话中的状态机建议：

```text
created
  -> parsed
  -> validated
  -> previewed
  -> awaiting_approval
  -> queued
  -> session_ready
  -> pre_snapshot_done
  -> executing
  -> submitted
  -> verifying
  -> succeeded
```

异常分支：

```text
parsed -> need_clarification
awaiting_approval -> cancelled
executing -> manual_required
manual_required -> executing
verifying -> pending_review
verifying -> failed
failed -> retrying
retrying -> executing
failed -> manual_required
```

对于登录态失效、二维码、短信验证码等情况，不应直接标记为 `failed`，应进入：

```text
auth_required
manual_required
waiting_operator
operator_submitted
verifying_auth
resuming
executing
```

只有确认无法恢复时才进入 `failed`。

## 8. 云端部署和 Runner 架构

原对话明确：如果产品要真正上线给运营使用，必须从一开始考虑部署问题。

推荐形态：

```text
云端控制平面 + 私有 RPA 执行节点
```

云端控制平面负责：

```text
运营 Web 工作台
后端 API
自然语言解析
标准操作计划
规则校验
审批
任务调度
权限控制
审计日志
截图/Trace 查看
状态监控
通知
```

私有 RPA 执行节点负责：

```text
保存浏览器登录态
打开商家后台
执行 Playwright 剧本
截图和 trace
遇到验证码/短信/人脸时转人工
回读校验结果
```

不建议所有 RPA 都跑在中心云服务器上，原因包括：

- 外卖后台可能更容易触发登录风控。
- 浏览器状态、账号 profile、人工接管是有状态的。
- RPA 卡死不应拖垮后端 API。
- 客户/品牌侧执行节点更容易通过安全审查。

## 9. 10 人左右团队的部署建议

对于 10 人左右运营团队，原对话推荐：

```text
单租户云端控制台 + 1-2 个固定 RPA 执行节点
```

更具体：

```text
运营 10 人
  -> 统一 Web 工作台
  -> 云服务器后端
  -> 队列 / 审批 / 审计 / 截图存储
  -> 固定 Runner 机器执行浏览器自动化
  -> 外卖商家后台
```

推荐机器拆分：

```text
机器 1：云端应用服务器
- Web 前端
- 后端 API
- 自然语言解析
- 任务编排
- PostgreSQL
- Redis
- 对象存储或本地文件存储

机器 2：RPA Runner 服务器
- Windows Server 或 Windows 桌面机
- Chrome / Edge
- Playwright
- 浏览器 Profile
- 远程接管工具

机器 3：可选备用 Runner
- 备用、高峰、测试新剧本
```

并发规则：

```text
同一平台账号：一次只执行 1 个任务
同一门店：一次只执行 1 个写操作
同一 Runner：同时最多 1-3 个浏览器任务
批量任务：拆成单任务串行或小批量执行
```

不推荐：

- 每个运营电脑都部署完整后端。
- 所有后端和 RPA 混在一台机器上。
- 一开始就做复杂多租户 SaaS。
- 一开始上 Kubernetes。
- 让运营各自手动跑脚本。

## 10. 前端人工介入交互

云端 Runner 执行时，登录态失效、二维码、短信验证码、滑块/人脸等场景必须在前端形成明确交互。

建议页面：

| 页面 | 作用 |
|---|---|
| 任务中心 | 显示所有任务状态、失败原因、当前卡点 |
| 人工介入队列 | 专门列出需要扫码、验证码、远程接管的任务 |
| 账号健康页 | 显示各平台账号在线状态、登录态、待处理任务 |
| 任务详情页 | 查看执行步骤、截图、Trace、重试记录 |
| 远程接管页 | 查看云端浏览器画面，人工完成验证或复杂操作 |

二维码登录推荐流程：

```text
1. Worker 检测到二维码登录页
2. 截取二维码区域
3. 上传截图或通过 WebSocket 推给前端
4. 前端弹窗显示二维码和倒计时
5. 运营用对应平台 App 扫码
6. Worker 轮询浏览器是否登录成功
7. 成功后自动关闭弹窗并恢复任务
8. 过期则自动刷新二维码或要求重新打开
```

人工介入面板应提供：

```text
继续检查
刷新验证
远程接管
转交他人
暂停账号
取消当前任务
标记为人工完成
```

其中“标记为人工完成”很重要：当 RPA 卡住但运营已经手动在后台完成操作时，系统可以只做回读校验和审计，不再继续执行点击动作。

## 11. 产品形态判断

原对话最后形成的产品判断：

> 不要一开始就做“大中台系统”。先做一个“外卖运营 Agent 工作台”，底层按中台能力预留，产品形态上先服务运营日常闭环。

建议名称阶段：

| 名称 | 适合阶段 | 面向对象 |
|---|---|---|
| 外卖运营 Agent 工作台 | 现在最适合 | 内部运营团队 |
| 本地生活商家运营自动化平台 | 中期适合 | 多门店、多品牌、代运营团队 |
| 本地生活运营智能中台 | 后期适合 | 多业务线或对外 SaaS |

Agent 能力建议分层：

```text
第一层：基础能力层
- 知识库 Agent
- 账号/权限
- 任务编排
- 平台适配器
- 审计日志

第二层：业务操作层
- 执行 Agent
- 菜单 Agent
- 内容 Agent

第三层：运营分析层
- 问数 Agent
- 日报 Agent
- 预警 Agent

第四层：经营决策层
- 增长 Agent
- 算法 Agent
- 提案 Agent
```

优先实现顺序：

```text
第一优先级：
1. 执行Agent
2. 菜单Agent
3. 知识库Agent
4. 日报Agent
5. 预警Agent

第二优先级：
6. 问数Agent
7. 内容Agent
8. 增长Agent

第三优先级：
9. 算法Agent
10. 提案Agent
```

## 12. MVP 主线

原对话建议下一步聚焦一个 MVP 主线：

```text
运营人员输入一句话
  -> 系统生成标准操作计划
  -> 经确认后完成门店/菜品/活动的模拟或半自动操作
  -> 生成结果记录和审计日志
```

第一版应该做：

```text
自然语言输入
识别门店、菜品、价格、时间、电话、活动等意图
生成标准操作计划
人工确认
模拟执行或半自动执行
执行结果回读
失败转人工
操作日志
简单日报
```

第一版不做：

```text
完整多租户 SaaS
复杂组织架构
全量 BI 系统
真正算法优化
全平台全功能覆盖
十个 Agent 全部独立服务化
全自动无人工审核
```

## 13. 本地测试 Demo PRD

原对话已经生成了一份 Markdown PRD，并已迁移到：

```text
docs/food-ops-agent/food-ops-agent-local-demo-prd.md
```

PRD 定义的本地 Demo 链路：

```text
自然语言指令
  -> 标准操作计划
  -> 风险校验
  -> 审批确认
  -> Fake 执行
  -> 回读校验
  -> 审计留痕
```

本地 Demo 技术约束：

```text
Python + FastAPI + Pydantic + Uvicorn
单文件静态 HTML/CSS/JS 前端
不引入数据库
第一版使用内存状态和 JSONL 审计
不引入 Playwright
不调用真实 LLM
不接真实外卖平台
```

后端模块规划：

```text
models.py      OperationPlan、TaskState、StoreSnapshot、MenuItem、OperationResult
parser.py      本地规则版自然语言解析
policy.py      风险分级、审批要求、价格边界校验
workflow.py    任务状态机、确认、执行、失败转人工
adapters.py    PlatformAdapter 接口、FakePlatformAdapter 实现
server.py      FastAPI 路由和静态页面服务
```

前端功能规划：

```text
指令输入
标准计划预览
审批确认按钮
任务状态时间线
Mock 门店/菜品快照
人工介入模拟区
审计结果区
```

验收样例：

```text
输入：把人民广场店的招牌牛肉饭改成 29.9
预览：32.00 -> 29.90
确认：点击审批确认
执行：FakeAdapter 修改 mock 数据
校验：回读价格为 29.90
审计：记录 before/after、状态时间线、操作结果
```

## 14. 可视化架构 HTML

原对话生成了一个独立 HTML 架构视图，已迁移到：

```text
docs/food-ops-agent/food-ops-agent-architecture.html
```

该 HTML 主要包含：

- 整体架构拓扑。
- 标准执行链路。
- 核心模块解耦。
- 上线部署形态。
- 任务状态机。
- 产品落地分层。

可以直接用浏览器打开，不需要启动服务。

## 15. 后续可执行路线

如果在当前目录继续开发，建议按这个顺序：

1. 建立 `food_ops_demo` 本地工程骨架。
2. 按 PRD 实现 `models/parser/policy/workflow/adapters/server`。
3. 先做 FakeAdapter，不接真实平台。
4. 前端实现单页工作台，跑通示例指令。
5. 补齐自动化测试：解析、风险规则、FakeAdapter、状态机、接口、前端关键元素。
6. 增加 MockWebAdapter 和 mock 商家后台页面。
7. 再引入 Playwright 验证页面自动化。
8. 最后才考虑真实平台 shadow mode、assisted mode、full auto。

本迁移记录可以作为后续 PRD、任务拆分和代码实现的上下文入口。
