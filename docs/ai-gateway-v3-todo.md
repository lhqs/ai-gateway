# AI Gateway V3 TODO

> 维护日期：2026-07-04  
> 来源：对 `docs/ai-gateway-plan-v3.md` 与当前代码实现的重新差距审查  
> 状态：P0 验收缺口已关闭；仍有 P1/P2 生产化增强待做  
> 数据库约束：后续所有数据库变更继续使用 SQL 脚本；禁止使用外键；禁止引入 Alembic。

## 1. 当前已完成的部分

- 已建立 monorepo：
  - `backend/`：FastAPI 后端
  - `frontend/`：Vite + React + Tailwind 管理台
- 已提供 SQL 初始化脚本：
  - `backend/app/db/sql/001_initial_schema.sql`
  - `backend/app/db/sql/002_seed_dev.sql`
  - 当前 SQL 未使用外键。
- 已实现基础业务接口：
  - `POST /v1/chat/completions`
  - `GET /proxy/{provider}/{native_path:path}`
  - `POST /proxy/{provider}/{native_path:path}`
- 已实现基础 adapter：
  - OpenAI-compatible chat adapter
  - Gemini native proxy adapter
- 已实现部分治理能力：
  - 内部 API Key 鉴权
  - Redis 限流基础类
  - 统一协议非流式 Redis 缓存
  - 统一协议非流式 failover 核心逻辑
  - usage log 基础落库
- 已实现部分管理 API：
  - clients
  - api keys 创建/更新
  - providers
  - models
  - model aliases
  - route rules
  - usage logs
  - dashboard
- 已有基础测试：
  - Gemini usage metadata 解析
  - path 白名单和 header 过滤
  - cache key 稳定性
  - failover 判断
  - chat failover + cache 命中路径

## 2. P0：阻塞 V3 验收的缺口

当前 P0 已关闭。以下条目保留为验收记录。

### P0-1 Provider 访问权限控制未完成

状态：已完成。

实现：

- `clients.access_config` 与 `api_keys.access_config` 支持 JSON 授权配置。
- 统一协议校验 `model_aliases`、`provider_ids`、`provider_names`、`model_ids`。
- 原生代理校验 `provider_ids`、`provider_names`、`native_paths`/`native_path_patterns`。
- 被拒绝请求会记录 usage log。

V3 要求“判断调用方是否有权限访问该 provider 或 native API”。

需要完成：

- 设计 provider/model/native path 授权方式。
- 建议第一阶段使用 JSON 字段或独立 SQL 表，但不能使用外键。
- 统一协议调用需要校验 client 是否允许访问目标 model alias 或 model。
- 原生代理调用需要校验 client 是否允许访问 provider 和 native path。
- 补充拒绝访问测试。

验收标准：

- 未授权 client 调用 provider/native path 返回 `403`。
- 已授权 client 可正常调用。
- usage log 能记录被拒绝请求的 request id、client、provider/path 和错误原因。

### P0-2 Admin API 缺少 `GET /admin/api-keys`

状态：已完成。

实现：

- 已新增 `GET /admin/api-keys`。
- 返回完整 key、key prefix、client、状态、访问策略、过期时间、最后使用时间。
- 不返回 key hash。

需要完成：

- 增加 `GET /admin/api-keys`。
- 返回完整 key、key prefix、client_id、状态、过期时间、最后使用时间。
- 不返回 key hash。

验收标准：

- 前端 API Keys 页面可以加载列表。
- 响应中包含完整 `key`，不包含 `key_hash`。

### P0-3 原生流式最大持续时间未实现

状态：已完成。

实现：

- `NativeProxyService.stream()` 使用 `native_stream_max_seconds` 强制限制总持续时间。
- 超时记录 `stream_timeout` usage log。

V3 要求“对流式连接设置最大持续时间”。

需要完成：

- 对 native stream 加最大持续时间控制。
- 超时后关闭流并记录 usage log。
- 错误类型建议记录为 `stream_timeout`。

验收标准：

- 超过配置时间后连接主动结束。
- usage log 中记录失败状态、耗时和错误原因。

### P0-4 原生流式 usage 解析不足

状态：已完成基础能力。

实现：

- Gemini native adapter 可从 stream chunk 中提取 `usageMetadata`。
- `NativeProxyService.stream()` 能将解析到的 usage 写入 usage log。

V3 要求 Gemini `streamGenerateContent` 纳入 MVP，并尽可能解析 usage。

需要完成：

- 解析 Gemini stream 结束事件中的 usage metadata。
- 能解析时记录 `parsed`。
- 不能解析时保留 `unknown`，但需要保留原始尾包或聚合摘要。

验收标准：

- 模拟 Gemini stream 返回 usage metadata 时，usage log 记录标准 token 字段和 `raw_usage`。

### P0-5 统一协议流式 failover 未实现

状态：已完成。

实现：

- 首包前失败可以按 route rule fallback。
- 已经输出后不切换，避免混合响应。
- 记录每次尝试和最终命中。

V3 要求支持流式聊天接口，并要求模型别名、fallback 与自动故障转移。

需要完成：

- 明确流式 failover 策略：
  - 首包前失败可以 failover。
  - 已开始输出后失败不切换，避免响应内容混杂。
- 记录每次尝试和最终失败原因。
- 补充测试。

验收标准：

- 主模型首包前失败时可切换 fallback。
- 已输出后失败时不切换，并记录失败。

### P0-6 原生代理错误透传不符合 V3

状态：已完成。

实现：

- provider 返回的原生错误 body/status/content-type 可透传。
- 网关策略错误、连接错误、超时错误仍使用网关错误结构。

V3 明确“允许透传供应商原生错误响应给业务方”。

需要完成：

- 对 provider 已返回的错误 body/status/content-type 做透传。
- 只对网关策略错误、连接错误、超时错误使用网关错误结构。
- 避免泄露敏感 header 或 provider key。

验收标准：

- 模拟 Gemini 400 原生错误，业务方收到原始 JSON 结构和原始状态码。

### P0-7 管理后台不满足 V3 页面要求

状态：已完成 MVP 验收能力。

实现：

- API Keys 列表可用。
- Provider 页面支持测试按钮。
- Usage Logs 支持筛选 query 和详情展开。
- Provider/model/alias/route/client/API key 均可通过后台创建。

保留 P2：后续仍建议从 JSON 表单升级为结构化表单。

- Provider 页面没有可点击的连通性测试。
- Provider 页面没有结构化字段控件。
- Routes 页面没有 fallback 顺序编辑体验。
- Usage Logs 页面没有展示 prompt、completion、raw request、raw response。
- Usage Logs 页面没有筛选 failover/cache/native path。
- API Keys 页面当前后端缺列表接口。

需要完成：

- 优先补齐能支撑验收的管理能力，不追求复杂 UI。
- Usage Logs 至少提供详情展开面板。
- Provider test 按钮调用 `/admin/providers/{id}/test`。

验收标准：

- 可在前端完成 provider、model、alias、route rule、native proxy 基础配置。
- 可在前端触发 provider 连通性测试。
- 可在前端查看 V3 要求的 usage log 字段。

### P0-8 缺少端到端集成验证

状态：已完成基础集成验证。

实现：

- 使用 ASGI app + SQLite async 测试库验证 admin 配置到 chat 调用再到 usage log。
- 验证 native proxy 权限拒绝和 usage log。

当前仍建议后续补充 PostgreSQL 实库初始化测试。

需要完成：

- 使用 SQLite async 或测试 PostgreSQL 建立集成测试。
- 覆盖 admin 创建配置 -> 创建 API key -> chat 调用 -> usage log。
- 覆盖 native proxy 成功、白名单拒绝、body size 拒绝。
- 覆盖 Redis 不可用时的降级行为。

验收标准：

- `uv run pytest` 覆盖端到端链路。
- 测试能证明核心 API 可由数据库配置驱动。

## 3. P1：重要但不阻塞第一轮可用性的缺口

### P1-1 Provider 连通性测试过于粗糙

当前只请求 `provider.base_url` 根路径，对 Gemini/OpenAI-compatible 都不够准确。

需要完成：

- OpenAI-compatible：测试 `/v1/models` 或配置化 health path。
- Gemini：测试可配置 GET path，例如 `v1beta/models`。
- 记录测试耗时、状态码、错误摘要。

### P1-2 `failure_threshold` 和 `cooldown_seconds` 未参与运行时治理

数据库已有字段，但没有健康状态熔断或冷却逻辑。

需要完成：

- 统计 provider 连续失败次数。
- 达到阈值后标记 degraded/unhealthy。
- 冷却期内避免选中该 provider，或只允许探测请求。

### P1-3 Redis 缓存缺少元数据持久化

V3 允许第一阶段仅 Redis，但当前建了 `cache_entries` 表却没有写入，容易造成设计不一致。

需要决策：

- 要么删除可选表。
- 要么在缓存写入时同步记录 cache metadata。

建议：

- 第一阶段保留 Redis 内容缓存，同时写入 `cache_entries` 元数据，便于后台观测。

### P1-4 Usage Logs 查询能力不足

当前只支持 recent list，不支持 V3 提到的筛选。

需要完成：

- 按 `call_mode`、`client_id`、`model_alias`、`provider_id`、`native_path`、`status`、`cache_hit`、`failover_triggered`、时间范围筛选。
- 分页返回总数。

### P1-5 内部 API Key 权限和安全策略不足

当前只保存 hash，但缺少：

- key 禁用后的缓存失效策略。
- key 级限流配置。
- key 级可访问模型/provider 限制。
- 管理后台不展示 key last used。

### P1-6 OpenAI-compatible 流式 usage 统计不足

当前流式 usage 默认为 `unknown`，没有解析最终 usage chunk。

需要完成：

- 支持供应商返回 `stream_options.include_usage` 时解析 final usage chunk。
- 记录 `completion_content` 的聚合摘要或可配置保存。

### P1-7 原生代理 header 透传策略需要配置化

当前只有 blocked headers，缺少 allowlist/forward rules。V3 只要求默认不转发敏感 header，但生产上建议更明确。

需要完成：

- provider.config 支持 `forward_headers_allowlist`。
- 默认只转发 content-type、accept、user-agent 等低风险 header。

## 4. P2：质量、维护性和体验优化

### P2-1 前端表单需要从 JSON 表单升级为结构化表单

当前 JSON 表单便于快速配置，但易错。

建议：

- Provider 使用字段表单和 tag input。
- Routes 使用 model select 和 fallback reorder 控件。
- Usage detail 使用抽屉或展开行。

### P2-2 缺少代码质量工具配置

建议补充：

- Ruff lint/format 配置和命令。
- Pyright 或 mypy。
- 前端 ESLint。
- CI 脚本。

### P2-3 缺少本地启动脚本

虽然不需要 Docker Compose，但仍建议提供：

- `scripts/dev-backend.sh`
- `scripts/dev-frontend.sh`
- `scripts/apply-sql.sh`

### P2-4 缺少生产配置样例

建议补充：

- `.env.example`
- provider 配置样例
- route rule 配置样例
- Gemini native proxy 示例请求

## 5. 下一步推荐执行顺序

1. 修复后端明显缺口：
   - `GET /admin/api-keys`
   - provider/client 权限模型
   - native stream 最大持续时间
   - 原生错误响应透传
2. 补端到端集成测试：
   - admin 配置闭环
   - chat 非流式 + cache + failover
   - native proxy GET/POST/stream
3. 补管理后台验收能力：
   - API Keys 列表
   - Provider test 按钮
   - Usage detail 展开
4. 完善流式治理：
   - unified stream failover
   - OpenAI stream usage
   - Gemini stream usage
5. 补使用文档和本地运行脚本。

## 6. 当前验证命令

当前已跑通过：

```bash
cd backend
uv sync --dev
uv run pytest
```

```bash
cd frontend
npm install
npm run build
```

当前验证已包含 P0-8 的基础端到端集成测试。

## 7. 完成判定标准

只有同时满足以下条件，才可以重新声明 V3 MVP 完成：

- P0 全部关闭。
- 后端单元测试和集成测试通过。
- 前端 build 通过，并可完成 provider/model/route/native proxy 基础配置。
- SQL 脚本能在空 PostgreSQL 库成功初始化。
- 实现中无外键约束、无 Alembic。
- README 包含可复现的本地启动、SQL 初始化和示例调用流程。
