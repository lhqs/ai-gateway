# 阶段一、阶段二实施总结与手动测试指南

> 日期：2026-07-08  
> 范围：运行时可靠性治理、Usage 与计费可信度提升、Usage 页面搜索区体验优化  
> 角色视角：AI Gateway 平台架构负责人

## 1. 本次实施目标

本次修改把 V3 MVP 往生产可运营版本推进，核心目标有三点：

1. 让 Provider 健康状态真正参与运行时路由决策。
2. 让 Usage 明细和聚合数据能支持运营分析、成本分析和 API Key 级对账。
3. 精简 Usage 页面筛选区，默认只展示核心检索条件，高级条件折叠展示。

## 2. 关键后端改动

### 2.1 Provider 健康治理

新增 `ProviderHealthService`：

- 文件：`backend/app/services/provider_health_service.py`
- 能力：
  - 统一处理 Provider health probe。
  - 支持按 provider 类型生成默认探测路径：
    - `openai_compatible` / `claude`：`v1/models`
    - `gemini`：`v1beta/models`
  - 支持 `provider.config.health_path` 覆盖默认探测路径。
  - 支持探测请求带 provider auth header 或 query key。
  - 记录成功、失败、连续失败次数、冷却截止时间、最近错误、最近状态码。

Chat 调用路径变更：

- 文件：`backend/app/services/chat_service.py`
- 行为：
  - 构建 primary + fallback 候选模型。
  - 跳过处于 `unhealthy` 且还在 `cooldown_until` 之前的 provider。
  - 如果 primary 被跳过且 fallback 可用，直接调用 fallback，并在 usage log 中记录 `failover_triggered=true`。
  - Provider 调用成功会恢复 health 状态。
  - Provider 健康相关失败会增加 failure count，达到阈值后进入 cooldown。

Native Proxy 调用路径变更：

- 文件：`backend/app/services/native_proxy_service.py`
- 行为：
  - 原生代理没有 fallback，因此 provider 不可用时直接返回 503。
  - 不可用请求会记录 usage log，错误码为 `provider_unavailable`。
  - 原生响应状态码会反馈给 health service，用于健康状态恢复或失败计数。

Admin Provider Test 变更：

- 文件：`backend/app/api/v1/admin/resources.py`
- 接口：`POST /admin/providers/{id}/test`
- 返回：
  - `status`
  - `status_code`
  - `latency_ms`
  - `probe_url`
  - `error_summary`
  - `checked_at`

### 2.2 Usage 与计费可信度

Usage Log 新增 `api_key_id`：

- 文件：`backend/app/db/models.py`
- 所有 Chat 和 Native Proxy usage 记录都会写入当前 API Key ID。
- 用途：
  - API Key 级用量查询。
  - API Key 级成本对账。
  - 后续支持 key 级限流、禁用影响分析。

Usage 明细查询增强：

- 文件：`backend/app/repositories/usage_logs.py`
- 接口：`GET /admin/usage-logs`
- 新增筛选：
  - `client_id`
  - `api_key_id`
  - `model_alias`
  - `provider_id`
  - `model_id`
  - `created_from`
  - `created_to`
  - 已有筛选继续保留：`call_mode`、`status`、`native_path`、`usage_status`、`pricing_status`、`cache_hit`、`failover_triggered`

新增 Usage 聚合接口：

- 接口：`GET /admin/usage-summary`
- 支持 `group_by`：
  - `total`
  - `day`
  - `client`
  - `api_key`
  - `provider`
  - `model`
  - `model_alias`
  - `status`
  - `call_mode`
- 聚合指标：
  - request count
  - success count
  - error count
  - prompt/completion/total tokens
  - cached input tokens
  - total cost
  - avg latency
  - cache hit count
  - failover count
  - stream count
  - parsed usage count
  - missing price count

Dashboard 增强：

- 接口：`GET /admin/dashboard`
- 新增返回：
  - `error_rate`
  - `total_cost_24h`
  - `total_cost_7d`
  - `failover_rate`
  - `usage_parsed_rate`
  - `missing_price_count`

### 2.3 数据库变更

新增 SQL：

- 文件：`backend/app/db/sql/008_provider_health_usage_filters.sql`

新增 Provider 字段：

- `failure_count`
- `last_success_at`
- `last_failure_at`
- `cooldown_until`
- `last_health_error`
- `last_health_status_code`

新增 Usage 字段：

- `api_key_id`

新增索引：

- provider health / cooldown 查询索引
- usage 按 api key、client、provider、model 与 created_at 组合查询索引

注意：

- 继续遵守项目约束：只使用编号 SQL 脚本，不使用 Alembic，不新增数据库外键。

## 3. 关键前端改动

### 3.1 Provider 页面

文件：`frontend/src/pages/ProvidersPage.tsx`

新增展示：

- health 状态
- failure count / threshold
- cooldown 截止时间
- last check 时间

新增配置：

- `health_path`
- `health_status`
- `failure_count`
- `cooldown_until`
- `failure_threshold`
- `cooldown_seconds`

用途：

- 可以直接在页面上把 primary provider 设置为 `unhealthy` 并填写未来的 `cooldown_until`，用于验证 fallback 路由。
- 不再必须通过数据库手工更新 provider health 字段。

### 3.2 Routes 页面

文件：`frontend/src/pages/RoutesPage.tsx`

新增体验：

- Route Rule 创建/编辑时，fallback models 改为下拉选择。
- 已选 fallback model 会展示为列表。
- 支持删除 fallback model。
- 支持上移/下移 fallback 顺序，列表顺序就是运行时 fallback 顺序。

### 3.3 Dashboard 页面

文件：`frontend/src/pages/DashboardPage.tsx`

新增指标卡：

- 7d Cost
- Total Cost
- 24h Cost
- Failover Rate
- Usage Parsed
- Missing Prices

### 3.4 Usage 页面

文件：`frontend/src/pages/UsagePage.tsx`

新增：

- 顶部聚合卡片：Requests、Success Rate、Cost、Cache Hits、Missing Prices。
- 更多筛选条件：Client、API Key、Provider、Model、Alias、Usage、Pricing、Native Path、Cache Hit、Failover、时间范围。

最新体验调整：

- 默认搜索区只保留一行核心条件：
  - Mode
  - Status
  - Client
  - Provider
  - Alias
  - Apply
  - More
  - Reset
- 高级筛选放入 `More` 折叠区：
  - API Key
  - Model
  - Usage
  - Pricing
  - Native Path
  - Cache Hit
  - Failover
  - From
  - To
- `More` 按钮显示当前高级筛选启用数量。

## 4. 已补充测试

后端测试新增覆盖：

- Provider health cooldown 判断。
- OpenAI-compatible versioned base URL 的 health probe path。
- Primary provider 处于 cooldown 时跳过并命中 fallback。
- Usage log 写入 `api_key_id`。
- Usage log 按 `api_key_id` 筛选。
- Usage summary 聚合接口。

已执行验证：

```bash
cd backend
uv run pytest
```

结果：

```text
43 passed
```

前端构建验证：

```bash
cd frontend
npm run build
```

结果：构建通过。

说明：

- `ruff` 当前未执行成功，因为后端环境中未安装 `ruff` 可执行文件。

## 5. 手动测试前准备

### 5.1 应用数据库脚本

在已初始化过旧库的情况下，执行新增 SQL：

```bash
cd backend
psql "$POSTGRES_DSN" -f app/db/sql/008_provider_health_usage_filters.sql
```

如果是空库初始化，按编号顺序执行所有 SQL 脚本，确保 `008_provider_health_usage_filters.sql` 在最后执行。

### 5.2 启动后端

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

### 5.3 启动前端

```bash
cd frontend
npm run dev
```

如果 Vite 自动分配到 `5174`，访问：

```text
http://localhost:5174/
```

如果是默认端口，访问：

```text
http://localhost:5173/
```

## 6. 手动测试步骤

### 6.1 Provider Health Test

目标：验证 provider test 使用真实 health path，并能更新健康字段。

步骤：

1. 打开管理台。
2. 进入 `Providers` 页面。
3. 创建或编辑一个 provider。
4. 设置：
   - `provider_type=openai_compatible`
   - `base_url=https://api.openai.com` 或你的 OpenAI-compatible 服务地址
   - `health_path=v1/models`
   - `failure_threshold=2`
   - `cooldown_seconds=60`
5. 点击 provider 行里的 `Test`。
6. 观察页面：
   - health 状态是否更新。
   - failure count 是否变化。
   - last check 是否变化。
   - cooldown 是否在失败达到阈值后出现。

预期：

- 可访问 provider 返回 `healthy`。
- 认证失败、网络失败、5xx 等情况会记录错误摘要，并逐步进入 degraded/unhealthy。

### 6.2 Chat Fallback 跳过 Unhealthy Provider

目标：验证 primary provider unhealthy 且在 cooldown 内时，路由直接走 fallback。

步骤：

1. 准备两个 provider：
   - primary provider
   - fallback provider
2. 为两个 provider 各创建一个 model。
3. 创建一个 alias，例如 `default-chat`。
4. 创建 route rule：
   - primary model 选择 primary provider 的 model。
   - 在 `Fallback Models` 下拉框中选择 fallback provider 的 model。
   - 如有多个 fallback，可用上下箭头调整顺序。
   - `max_failover_attempts >= 1`。
5. 打开 `Providers` 页面，编辑 primary provider。
6. 展开 `Advanced`。
7. 将 primary provider 设置为：
   - `health_status=unhealthy`
   - `failure_count` 大于或等于 `failure_threshold`
   - `cooldown_until` 为未来时间
8. 保存 provider。
9. 使用 Workbench 或 API Key 调用：

```bash
curl http://localhost:8004/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default-chat",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

10. 打开 `Usage` 页面查看最新日志。

预期：

- 请求成功。
- `final_provider_id` 对应 fallback provider。
- `failover_triggered=true`。
- primary provider 不应被实际调用。

### 6.3 Native Proxy Provider Unavailable

目标：验证 native proxy 在 provider cooldown 时返回 503，并记录 usage。

步骤：

1. 准备一个支持 `native_proxy` 的 provider，例如 Gemini。
2. 将该 provider 设置为：
   - `health_status=unhealthy`
   - `cooldown_until` 为未来时间
3. 使用 API Key 请求：

```bash
curl http://localhost:8004/proxy/gemini/v1beta/models/gemini-1.5-pro:generateContent \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"hello"}]}]}'
```

预期：

- 返回 503。
- Usage 页面出现一条 `native_proxy` failed 日志。
- `error_code=provider_unavailable`。

### 6.4 Usage 核心筛选

目标：验证 `/usage` 页面默认一行核心筛选。

步骤：

1. 打开：

```text
http://localhost:5174/usage
```

或当前 Vite 实际端口的 `/usage`。

2. 默认搜索区应只显示一行：
   - Mode
   - Status
   - Client
   - Provider
   - Alias
   - Apply
   - More
   - Reset
3. 使用 `Mode`、`Status`、`Client`、`Provider`、`Alias` 任意组合筛选。
4. 点击 `Apply`。

预期：

- Usage 表格刷新。
- 顶部聚合卡片同步刷新。
- 页面不会出现大量默认展开的筛选控件。

### 6.5 Usage 高级筛选

目标：验证高级筛选折叠区。

步骤：

1. 在 `/usage` 页面点击 `More`。
2. 展开后选择高级条件：
   - API Key
   - Model
   - Usage
   - Pricing
   - Native Path
   - Cache Hit
   - Failover
   - From / To
3. 点击 `Apply`。
4. 观察 `More` 按钮上的数字。
5. 点击 `Reset`。

预期：

- 高级筛选生效。
- `More` 后的数字等于当前启用的高级筛选数量。
- `Reset` 后筛选全部清空，数字消失。

### 6.6 Dashboard 指标

目标：验证 Dashboard 新增聚合指标。

步骤：

1. 打开 Dashboard。
2. 观察指标卡：
   - Requests
   - Success Rate
   - Tokens
   - Avg Latency
   - Errors
   - 7d Cost
   - Cache Hit Rate
   - Usage Parsed
   - Total Cost
   - 24h Cost
   - Failover Rate
   - Missing Prices
3. 发起几次成功、失败、fallback、cache hit 请求。
4. 刷新 Dashboard。

预期：

- 指标随 usage log 变化。
- Failover Rate、Usage Parsed、Missing Prices 能反映当前日志状态。

## 7. 后续调整注意点

1. Provider health 当前是请求路径内同步更新，逻辑简单可靠；如果后续流量很大，可以再引入异步健康探测任务。
2. `cooldown_until` 过期后，当前策略允许 provider 重新进入候选；成功调用会恢复 healthy，失败会再次累计。
3. Usage summary 当前直接查 `usage_logs` 聚合；数据量变大后可考虑增加日级汇总表。
4. `api_key_id` 是后续做 key 级限流、客户对账、key rotate 影响分析的基础字段，不建议移除。
5. Usage 页面核心筛选和高级筛选的分层已经形成交互约定，后续新增筛选条件默认应进入高级区，除非是高频检索字段。
6. 生产环境应尽快补充 usage raw body 保存开关，降低 prompt/completion/raw body 长期落库风险。
