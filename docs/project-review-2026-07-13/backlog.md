# 更新与增强 Backlog

> P0：上线前必须处理；P1：下一阶段应处理；P2：中长期增强。  
> “证据”中的行号以 2026-07-13 当前分支 `dev` 为准。

## P0：生产前必须处理

### P0-1 修复缓存键不完整导致的错误响应复用

**问题**

`ChatCompletionRequest` 允许额外 OpenAI 参数，但缓存哈希只包含 messages、temperature、top_p、
max_tokens、tools、tool_choice、response_format 和 stop。`seed`、`frequency_penalty`、
`presence_penalty`、`logit_bias`、`n`、`parallel_tool_calls` 等参数不同的请求可能命中同一个缓存。
哈希也没有包含最终 Provider/Model 或配置版本，路由切换后可能继续返回旧 Provider 的缓存结果。

**证据**

- `backend/app/schemas/chat.py:13`：请求模型允许 `extra = allow`。
- `backend/app/services/cache_service.py:15`：缓存哈希使用固定字段子集。
- `backend/app/services/chat_service.py:87`：路由允许缓存时直接使用该哈希读取响应。

**更新建议**

- 对去除 `stream` 等非语义字段后的完整请求体做确定性序列化。
- 缓存键加入 route rule、最终 model/provider、API 兼容版本和人工 `cache_version`。
- 明确定义 `cache_scope` 的 client/key/global 行为；不支持的 scope 拒绝保存。
- 增加“任一影响输出的参数变化都会 miss”参数化测试。

**验收**

- 所有影响模型输出的参数不同都不会复用缓存。
- 修改 primary model、fallback 或 Provider 配置后旧缓存不会误命中。
- 原有相同请求缓存命中测试继续通过。

### P0-2 Provider 密钥不应可读回，且必须真正加密

**问题**

字段名为 `encrypted_api_key`，但 Provider Adapter 直接把该值当真实密钥使用，说明数据库保存的是
明文。`ProviderRead` 继承 `ProviderWrite`，List/Read 响应会包含完整密钥，前端类型和编辑表单也接收
并显示该值。任何管理员 access token 泄露都可能进一步泄露全部上游供应商凭据。

**证据**

- `backend/app/db/sql/001_initial_schema.sql:33`：密钥存储为普通 TEXT。
- `backend/app/schemas/admin.py:108`、`:162`：读模型继承包含密钥的写模型。
- `backend/app/providers/openai_compatible.py:17`、`gemini_native.py:43`：字段直接作为 API Key。
- `frontend/src/types/gateway.ts:79`：Provider 响应类型包含 `encrypted_api_key`。

**更新建议**

- 拆分 Provider Create/Patch/Read schema，Read 只返回 `has_api_key`、`key_hint`、`key_updated_at`。
- Patch 中 `encrypted_api_key` 缺省表示保留，显式 rotate/clear 使用独立动作。
- 使用 KMS、Vault，或由环境主密钥派生的 AEAD 进行应用层加密；密钥不得和数据库同库保存。
- 新增编号 SQL 脚本保存密钥版本/提示信息，不增加外键。
- 日志、审计、异常与 Provider Test 结果继续做密钥脱敏。

**验收**

- 管理 API、浏览器、日志、审计中均无法取得完整 Provider 密钥。
- 数据库 dump 中无法直接使用密钥调用上游 API。
- 存量明文可一次性迁移并可回滚；密钥可轮换。

### P0-3 建立 Usage 内容隐私与数据保留策略

**问题**

统一 Chat 每次都会写入完整 messages 和 completion；Native Proxy 会保存请求/响应正文，流式响应最多
保存约 20,000 字符。当前没有字段级开关、脱敏规则、租户策略、保留天数或清理任务。数据库将持续
积累用户输入、模型输出和潜在个人/业务敏感数据。

**证据**

- `backend/app/services/chat_service.py:180`、`:352`：保存 prompt/completion。
- `backend/app/services/native_proxy_service.py:235`、`:398`：保存原生请求/响应。
- `backend/app/core/config.py:7`：没有 Usage 内容保存和 retention 配置。

**更新建议**

- 增加 `STORE_USAGE_CONTENT`、各字段独立开关、最大字符/字节数和 `USAGE_RETENTION_DAYS`。
- 默认生产仅保存 usage、路由、状态和成本，不保存正文。
- 对 authorization、token、password、base64、tool 参数等递归脱敏。
- 增加分批清理命令/定时任务，并记录删除数量和耗时。
- 管理台详情页明确标识内容是否被省略、截断或脱敏。

**验收**

- 关闭内容保存后新 Usage Log 不包含 prompt/completion/raw body。
- 超长内容有确定上限，敏感字段测试通过。
- 可按保留天数批量清理且不会长时间锁表。

### P0-4 生产配置 fail-fast 与管理员注册策略生效

**问题**

JWT 和 bootstrap token 有可运行的弱默认值，`environment` 没有用于生产启动校验。
`admin_registration_mode` 虽在配置和 `.env.example` 中声明，但注册接口完全不读取它。首次注册采用
“先查是否存在用户”，并发请求可能都通过无 token 分支。

**证据**

- `backend/app/core/config.py:9`、`:14`、`:22`、`:26`：默认 secret 和未使用的注册模式。
- `backend/app/api/v1/auth.py:41`：注册只根据 `has_users()` 决定是否校验 bootstrap token。

**更新建议**

- `ENVIRONMENT=production` 时拒绝默认/过短 secret、宽泛 CORS 和不安全配置。
- 实现 `disabled`、`bootstrap`、`token_required` 注册模式并加测试。
- 首次管理员创建改为数据库原子保护或仅保留 CLI bootstrap。
- 登录、注册、刷新增加 Redis/IP/account 限流和失败告警。

**验收**

- 生产环境弱配置无法启动，并给出明确错误。
- 注册模式与文档一致；并发首次注册只能成功一个授权流程。
- 暴力登录/刷新受到限制，正常登录不受影响。

## P1：下一阶段应处理

### P1-1 清理“配置已展示但运行时未实现”的漂移

**问题**

- `forward_headers_allowlist` 已在 Provider Schema 和前端配置中出现，但 Gemini Native Adapter 只应用
  blocked headers，未读取 allowlist。
- `cache_scope` 被保存和展示，但缓存键始终只使用 client ID。
- `default_timeout_seconds` 当前没有运行时引用。

这种漂移会让管理员误以为安全/行为策略已经生效。

**更新建议**

- Native Header 默认采用最小 allowlist；blocked headers 作为不可覆盖的 denylist。
- 明确实现或移除 `cache_scope` 和 `default_timeout_seconds`。
- 建立配置字段到运行时代码的契约测试。

**验收**

- 不在 allowlist 的 Header 不会发给上游，敏感 Header 永远无法放行。
- 所有公开配置字段都有运行时消费者或被删除。

### P1-2 健康恢复改为受控半开探测

**问题**

cooldown 到期后 `is_available()` 会让所有普通请求同时认为 Provider 可用，没有 half-open 锁或单次探测。
高并发下可能形成恢复风暴；任意一个成功请求又会立刻清零失败状态。

**更新建议**

- Redis/数据库实现 half-open lease，冷却后仅允许一个探测请求。
- 成功达到恢复阈值后再 healthy，失败则指数退避并加入 jitter。
- 增加 provider health 状态变化事件和指标。

**验收**

- cooldown 到期瞬间最多一个探测请求进入不健康 Provider。
- 恢复和再次失败的状态转换可测试、可观测。

### P1-3 Redis 故障和限流原子性

**问题**

Redis 启动连接失败时限流和缓存静默失效；运行过程中 Redis 错误可能直接变成 500。限流采用分离的
`INCR`/`EXPIRE`，不是单个原子脚本，也没有标准限流响应头。

**更新建议**

- 使用 Lua 或 Redis 原子限流算法，返回 remaining/reset/retry-after。
- 分业务配置 Redis fail-open/fail-closed，并记录降级指标/告警。
- 缓存读取遇到损坏 JSON 时删除坏值并回源。

**验收**

- 并发限流窗口准确，无永久 key。
- Redis 中断行为符合配置且不会产生无解释 500。

### P1-4 Refresh Token 轮换与浏览器会话加固

**问题**

Refresh 流程是“查询 active -> revoke -> 创建新 session”，没有条件更新或行锁，并发刷新可能生成
多组新 token。前端把 access/refresh token 都放在 `localStorage`，XSS 后可直接窃取长期会话。

**更新建议**

- Refresh Token 使用原子消费、token family 和 reuse detection。
- 优先将 refresh token 放在 `HttpOnly; Secure; SameSite` cookie，access token 仅保存在内存。
- 增加 CSP、安全响应头和会话管理页面。

**验收**

- 同一 refresh token 并发使用最多一次成功；复用触发 token family 撤销。
- 浏览器脚本无法读取 refresh token。

### P1-5 CI、Lint 和真实 PostgreSQL/Redis 集成测试

**现状**

- 后端 57 个 pytest 通过，但主要使用 SQLite/mocks。
- Ruff 手工检查发现 6 个可自动修复的未使用 import；Ruff 不在 dev dependencies。
- 前端 build/typecheck 通过，但 `npm run build` 未显式执行 `tsc`，无 ESLint 和组件/E2E 测试。
- 没有 `.github/workflows`、Dockerfile/Compose 或自动 SQL 初始化校验。

**更新建议**

- CI jobs：`ruff check`、`ruff format --check`、pytest、`tsc --noEmit`、Vite build、前端测试。
- PostgreSQL job 从空库顺序执行全部 SQL，再跑关键 API 集成测试。
- Redis job 覆盖限流、缓存、冷却和故障降级。
- 增加 SQL 重复执行测试和从上一个版本升级测试。

**验收**

- PR 无法在 lint、测试、构建或 SQL 初始化失败时合并。
- SQLite 与 PostgreSQL 差异由 CI 捕获。

### P1-6 API 输入约束、全局请求限制与错误协议

**问题**

Native Proxy 有 2 MiB body 限制，Chat JSON 没有统一 ASGI 层请求体限制。大量 Admin schema 的
status、provider type、URL、数值范围仍是宽泛 string/int。流式错误在 HTTP 200 建立后以 SSE 数据返回，
但缺统一终止事件和错误契约。

**更新建议**

- 在反向代理和 ASGI 层统一限制 body、header、并发和超时。
- 用 Enum/Literal/URL/range 校验 Provider、Route、Client、Pricing 写入。
- 标准化同步和流式错误 envelope、错误码、request ID 和 retryability。

**验收**

- 超限 Chat/Native/Admin 请求都返回一致的 413。
- 无效状态/URL/负数阈值不能入库。

### P1-7 运维观测与健康端点分层

**问题**

`/health` 永远返回 ok，没有区分 liveness/readiness，也不验证数据库/Redis。当前主要观测依赖数据库
Usage Log 和应用日志，缺 Prometheus/OpenTelemetry 指标及告警规则。

**更新建议**

- 增加 `/health/live`、`/health/ready`，readiness 验证 DB，并按策略验证 Redis。
- 输出请求量、延迟、首 token 延迟、Provider 错误、failover、cache、限流、usage parse、missing price。
- 使用 OpenTelemetry trace 串联 gateway request、attempt、provider 和 usage log。

**验收**

- 编排系统不会把 DB 不可用实例加入流量。
- 能基于 Provider 错误率、unknown usage 和 missing price 建立告警。

## P2：功能增强与长期演进

### P2-1 Usage 导出、预算和对账

- 增加按当前筛选条件导出 CSV；大范围导出使用异步任务和过期下载链接。
- 增加 Client/API Key 日/月预算、软告警和硬限额。
- 增加价格配置版本回算策略与对账快照，避免历史成本随当前价格变化。

### P2-2 Workbench Native Proxy 与策略模拟器

- Workbench 支持 Native GET/POST/stream、Header/Query/Body 编辑和脱敏展示。
- 输入 Client/API Key、Alias/Provider/Path，预览访问策略、限流层级和预计路由。
- 一键生成可复现且已脱敏的 curl。

### P2-3 Provider/模型能力扩展

- 按真实需求增加 OpenAI Responses API、Anthropic Native Messages、Embeddings、Images、Audio。
- Provider Adapter 声明 capabilities，路由校验请求能力与模型能力是否匹配。
- 避免在现有 Chat 抽象中强行塞入所有协议。

### P2-4 路由策略演进

- 支持 weighted round-robin、最低延迟、最低成本、区域/数据驻留和 sticky routing。
- 调度指标采用滑动窗口，设置最小样本和抖动保护。
- 先建立 SLO 和指标，再引入自适应路由。

### P2-5 管理与数据生命周期

- 将默认硬删除改为禁用/归档，保留审计和历史 Usage 可解释性。
- 增加审计日志时间筛选、CSV 导出、变更前后 diff 和 request ID。
- 增加 Usage/审计/Session/Cache metadata 的清理和容量看板。

## 暂不建议优先做

- 在 P0 完成前继续增加更多 Dashboard 卡片。
- 在没有 PostgreSQL/Redis 集成测试前实现复杂自适应路由。
- 用更多 JSON 配置字段代替清晰的 schema 和运行时契约。
- 把现有单管理员权限直接扩展成复杂 RBAC；先完成会话、密钥和审计安全基线。

