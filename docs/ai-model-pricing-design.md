# AI 模型请求价格配置与费用计算设计

> 维护日期：2026-07-05  
> 适用范围：LHQS AI Gateway 后端计费配置、usage 解析、请求费用计算与管理台展示  
> 数据库约束：继续使用 `backend/app/db/sql/` 下的编号 SQL 脚本；不使用 Alembic；不新增数据库外键。

## 1. 角色选择

本需求最适合由 **AI 网关计费与用量架构师** 负责设计。

原因：

- 该需求不是单纯的“价格字段展示”，核心是把供应商返回的 usage、网关缓存、模型路由、币种单位和后续成本统计统一起来。
- 价格经常变化，且不同供应商会有 input、cached input、output、reasoning tokens、request 级费用等不同计量项，必须先设计可演进的计量模型。
- 当前项目已经有 usage log、模型路由、provider adapter、原生代理和管理后台，方案需要落到现有代码结构和 SQL 脚本，而不是另起一套账务系统。

## 2. 现状判断

当前代码已经具备基础用量记录能力：

- `models` 表已有 `input_price`、`output_price`、`currency` 字段。
- `usage_logs` 表已有 `prompt_tokens`、`completion_tokens`、`total_tokens`、`estimated_cost` 字段。
- OpenAI/Gemini usage parser 目前只归一化到 `prompt_tokens`、`completion_tokens`、`total_tokens`。
- 网关响应缓存命中时，`ChatService` 当前记录 token 为 0，`cache_hit=true`。

主要缺口：

- `models` 上的单价字段只能表达 input/output 两类价格，无法表达 cached input、reasoning output、cache write/read 等常见计费项。
- `estimated_cost` 没有币种单位，无法区分 USD/CNY。
- 人民币和美元应该作为两套独立配置，不应在请求计算时自动汇率换算。
- 缓存概念需要拆开：
  - **供应商 cached input**：请求仍打到供应商，只是供应商对部分输入 token 使用缓存价。
  - **网关 response cache hit**：请求没有打到供应商，默认供应商成本为 0。
- usage parser 没有提取 provider-specific token 明细，例如 OpenAI `prompt_tokens_details.cached_tokens` 一类字段。

## 3. 设计目标

第一阶段目标：

- 支持按模型配置价格，覆盖 input、cached input、output 三类核心计费项。
- 支持人民币和美元作为独立价格配置，计算时只按指定币种配置计算，不做汇率换算。
- 在 usage log 中记录费用金额、币种、计价单位、价格配置版本和计算明细。
- 对统一 chat 和 native proxy 两条调用路径都可复用同一套费用计算服务。
- 保持旧字段兼容，避免一次性破坏现有管理台和测试。

非目标：

- 不做钱包、充值、扣费、发票、汇率转换。
- 不从供应商官网自动抓取价格。
- 不要求第一阶段支持所有模态计费，但数据结构需要允许后续扩展。

## 4. 核心口径

### 4.1 费用口径

请求费用按“计量项 × 单价”求和：

```text
cost = sum(quantity / unit_quantity * unit_price)
```

示例：

- `input_tokens = 1000`
- `cached_input_tokens = 500`
- `output_tokens = 300`
- 单位为 `per_1m_tokens`
- `input_unit_price = 2.00`
- `cached_input_unit_price = 0.50`
- `output_unit_price = 8.00`

则：

```text
input_cost = 1000 / 1000000 * 2.00
cached_input_cost = 500 / 1000000 * 0.50
output_cost = 300 / 1000000 * 8.00
total_cost = input_cost + cached_input_cost + output_cost
```

金额计算必须使用 `Decimal`，不要使用 float。

### 4.2 token 口径

保留现有字段，同时新增更清晰的归一化字段：

- `prompt_tokens`：保留 provider 原始 input/prompt 总量，兼容现有统计。
- `completion_tokens`：保留 provider output/completion 总量。
- `total_tokens`：保留 provider total token。
- `cached_input_tokens`：供应商返回的 cached input token 数。
- `billable_input_tokens`：按普通 input 单价计费的 input token 数。
- `billable_output_tokens`：按 output 单价计费的 output token 数。

计算规则：

```text
cached_input_tokens = parser 提取值，缺省 0
billable_input_tokens = max(prompt_tokens - cached_input_tokens, 0)
billable_output_tokens = completion_tokens
```

如果某个供应商的 usage 语义不是“prompt_tokens 包含 cached tokens”，则由该供应商 parser 明确覆盖归一化结果，不能在计费服务里猜。

### 4.3 缓存口径

必须区分两种缓存：

- `provider_cached_input`：供应商侧缓存输入，仍有供应商成本，按 `cached_input_unit_price` 计算。
- `gateway_response_cache_hit`：网关响应缓存命中，没有调用供应商，默认供应商成本为 0。

建议 usage log 中保留：

- `cache_hit`：现有字段，继续表示网关 response cache hit。
- `cached_input_tokens`：新增字段，表示供应商 cached input tokens。
- `cost_breakdown`：记录两个缓存口径的费用明细，避免排查时混淆。

网关 response cache hit 默认策略：

- `prompt_tokens/completion_tokens/total_tokens` 继续记录 0，表示本次没有供应商用量。
- `estimated_cost=0`，`cost_currency` 记录请求选择的价格币种或 `NULL`。
- 如果后续要对客户收取“网关缓存服务费”，应新增独立计量项 `gateway_cache_read`，不要混入供应商成本。

## 5. 数据库设计

### 5.1 新增价格配置表

新增 `backend/app/db/sql/005_model_pricing.sql`。

建议表名：`model_price_configs`。

字段设计：

```sql
CREATE TABLE IF NOT EXISTS model_price_configs (
  id BIGSERIAL PRIMARY KEY,
  provider_id BIGINT NOT NULL,
  model_id BIGINT NOT NULL,
  model_name VARCHAR(128) NOT NULL,
  currency_code VARCHAR(16) NOT NULL,
  unit_type VARCHAR(32) NOT NULL DEFAULT 'tokens',
  unit_quantity INTEGER NOT NULL DEFAULT 1000000,
  input_unit_price NUMERIC(24,12),
  cached_input_unit_price NUMERIC(24,12),
  output_unit_price NUMERIC(24,12),
  reasoning_output_unit_price NUMERIC(24,12),
  request_unit_price NUMERIC(24,12),
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_price_configs_model_currency
  ON model_price_configs(model_id, currency_code, status);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_effective
  ON model_price_configs(model_id, currency_code, effective_from, effective_to);
```

说明：

- 不加外键，符合项目约束；通过 application logic 校验 `provider_id/model_id`。
- `currency_code` 使用 `USD`、`CNY` 等 ISO 风格代码。人民币不要写 `RMB`，展示层可显示“人民币”。
- `unit_type + unit_quantity` 记录计价单位，例如：
  - `tokens + 1000000` 表示每 1M tokens。
  - `tokens + 1000` 表示每 1K tokens。
  - 未来可支持 `request + 1`。
- USD 和 CNY 是两条独立配置，不存在换算关系。
- `config` 用于未来扩展，例如 image/audio/token tier、供应商价格来源备注、阶梯价等。

### 5.2 扩展 usage_logs

同一个 SQL 脚本中扩展 `usage_logs`：

```sql
ALTER TABLE usage_logs
  ADD COLUMN IF NOT EXISTS cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS billable_input_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS billable_output_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_currency VARCHAR(16),
  ADD COLUMN IF NOT EXISTS cost_unit_type VARCHAR(32),
  ADD COLUMN IF NOT EXISTS cost_unit_quantity INTEGER,
  ADD COLUMN IF NOT EXISTS input_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS cached_input_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS output_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS total_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS pricing_config_id BIGINT,
  ADD COLUMN IF NOT EXISTS pricing_status VARCHAR(32) NOT NULL DEFAULT 'not_calculated',
  ADD COLUMN IF NOT EXISTS cost_breakdown JSONB;

CREATE INDEX IF NOT EXISTS idx_usage_logs_cost_currency_created_at
  ON usage_logs(cost_currency, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_pricing_status
  ON usage_logs(pricing_status);
```

兼容策略：

- 继续保留 `estimated_cost`，第一阶段可同步写入 `total_cost` 相同值，避免旧页面和旧统计失效。
- 新页面和新接口优先读 `total_cost/cost_currency/cost_breakdown`。
- 后续稳定后再决定是否废弃 `estimated_cost`。

## 6. 后端模块设计

### 6.1 新增模型与仓储

新增或修改：

- `backend/app/db/models.py`
  - 新增 `ModelPriceConfig`
  - 扩展 `UsageLog` 新字段
- `backend/app/repositories/model_price_configs.py`
  - `get_active_for_model(model_id, currency_code, at_time)`
  - `list_by_model(model_id)`
  - 常规 CRUD

价格选择规则：

```text
where model_id = ?
  and currency_code = ?
  and status = 'active'
  and effective_from <= request_time
  and (effective_to is null or effective_to > request_time)
order by effective_from desc, id desc
limit 1
```

如果未找到配置：

- 不阻断模型调用。
- usage log 写 `pricing_status='missing_price_config'`。
- `total_cost=NULL`，`estimated_cost=NULL`。

### 6.2 扩展 usage 归一化

新增内部对象，例如 `NormalizedUsage`：

```python
class NormalizedUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    billable_input_tokens: int = 0
    billable_output_tokens: int = 0
    raw_usage: dict[str, Any] | None = None
    usage_status: Literal["parsed", "estimated", "unknown", "failed"] = "unknown"
```

OpenAI parser 第一阶段应提取：

- `usage.prompt_tokens`
- `usage.completion_tokens`
- `usage.total_tokens`
- `usage.prompt_tokens_details.cached_tokens`

Gemini parser 第一阶段应提取：

- `usageMetadata.promptTokenCount`
- `usageMetadata.candidatesTokenCount`
- `usageMetadata.totalTokenCount`
- 如果 Gemini 返回 cached content 相关 token 字段，则映射到 `cached_input_tokens`；没有则为 0。

### 6.3 新增 PricingService

新增 `backend/app/services/pricing_service.py`。

职责：

- 根据 `model_id + currency_code + request_time` 查价格配置。
- 根据 normalized usage 计算费用。
- 返回可直接写入 `usage_logs` 的字段。

建议返回结构：

```python
class CostResult(BaseModel):
    pricing_status: str
    pricing_config_id: int | None = None
    cost_currency: str | None = None
    cost_unit_type: str | None = None
    cost_unit_quantity: int | None = None
    input_cost: Decimal | None = None
    cached_input_cost: Decimal | None = None
    output_cost: Decimal | None = None
    total_cost: Decimal | None = None
    cost_breakdown: dict[str, Any] | None = None
```

计算状态：

- `calculated`：找到配置并完成计算。
- `missing_price_config`：没有找到对应币种价格。
- `not_billable`：网关 response cache hit、失败请求、usage unknown 且无可计量 token。
- `usage_unknown`：请求成功但 provider 未返回 usage，无法计算费用。

失败请求费用策略：

- 默认不计算费用，写 `pricing_status='not_billable'`。
- 如果 provider 失败响应里仍返回 usage，可按实际 usage 计算；第一阶段可以暂不做。

### 6.4 币种选择

第一阶段不在调用方请求体中开放币种参数，避免业务方随意选择不同成本口径。

推荐配置入口：

- 全局默认：`settings.DEFAULT_COST_CURRENCY`，默认 `USD`。
- client 级覆盖：`clients.access_config.cost_currency`。
- api key 级覆盖：`api_keys.access_config.cost_currency`，优先级最高。

选择顺序：

```text
api_key.access_config.cost_currency
> client.access_config.cost_currency
> DEFAULT_COST_CURRENCY
```

只记录和使用币种代码，不做 USD/CNY 换算。

### 6.5 调用链集成

统一 chat 非流式：

1. provider 返回 response。
2. parser 生成 normalized usage。
3. `PricingService.calculate(model.id, currency_code, usage)`。
4. `UsageService.record()` 写 token、费用和 breakdown。

统一 chat 流式：

1. 流结束时拿到 usage。
2. 如果 usage parsed，则计算费用。
3. 如果未拿到 usage，写 `pricing_status='usage_unknown'`。

native proxy：

1. adapter 解析 native usage。
2. 如果 native path 解析到了模型 alias 和 `model_id`，正常计算。
3. 如果 native path 无法归属到模型，写 `pricing_status='missing_model_context'` 或 `not_calculated`。

网关 response cache hit：

1. 不调用 provider。
2. usage log 写 `cache_hit=true`。
3. `pricing_status='not_billable'`。
4. `total_cost=0`，`estimated_cost=0`。

## 7. 管理 API 设计

新增 admin endpoints：

- `GET /admin/model-price-configs?model_id=&currency_code=&limit=&offset=`
- `POST /admin/model-price-configs`
- `PATCH /admin/model-price-configs/{id}`
- `DELETE /admin/model-price-configs/{id}` 或软删除为 `status='deleted'`

请求体示例：

```json
{
  "provider_id": 1,
  "model_id": 2,
  "model_name": "gpt-4.1-mini",
  "currency_code": "USD",
  "unit_type": "tokens",
  "unit_quantity": 1000000,
  "input_unit_price": "0.400000000000",
  "cached_input_unit_price": "0.100000000000",
  "output_unit_price": "1.600000000000",
  "status": "active",
  "effective_from": "2026-07-05T00:00:00Z",
  "effective_to": null,
  "config": {
    "source": "manual",
    "note": "供应商官网价格手工录入"
  }
}
```

校验规则：

- `currency_code` 必须是大写，第一阶段允许 `USD`、`CNY`。
- `unit_quantity > 0`。
- 单价允许为 `NULL`，表示该计量项不支持或不计费。
- `model_id/provider_id` 必须存在且匹配，但只在应用层检查，不建数据库外键。

## 8. 前端设计

第一阶段建议新增 “Pricing” 管理入口，或在 Models 页面中增加模型价格配置区域。

更推荐新增独立页面：

- 模型价格列表：model、provider、currency、unit、input、cached input、output、status、生效时间。
- 创建/编辑弹窗：结构化输入单价和币种。
- Usage 页面增加展示：
  - `total_cost`
  - `cost_currency`
  - `pricing_status`
  - `cached_input_tokens`
  - 展开详情中的 `cost_breakdown`

不要只把价格塞进 Models 页面，因为同一模型可能同时维护 USD/CNY 两套配置，也可能有历史生效版本。

## 9. 测试方案

后端测试优先级：

- `PricingService` 单元测试：
  - input/output 基础费用计算。
  - cached input 费用计算。
  - CNY/USD 独立配置，不做换算。
  - 缺少价格配置时返回 `missing_price_config`。
  - gateway cache hit 返回 `not_billable` 和 0 成本。
- usage parser 测试：
  - OpenAI cached tokens 提取。
  - Gemini usageMetadata 兼容旧字段。
- chat service 集成测试：
  - 非流式成功请求写入 `total_cost/cost_currency/cost_breakdown`。
  - 流式 usage parsed 后写入费用。
  - cache hit 不重复计算供应商成本。
- native proxy 集成测试：
  - 能解析到模型时计算费用。
  - 无模型上下文时不阻断请求，并记录未计算状态。

前端验证：

- `npm run build`。
- 手工创建 USD/CNY 两套价格配置。
- 发起一次调用后在 Usage 页面能看到费用和币种。

## 10. 落地执行计划

### 阶段 1：数据结构和纯计算

1. 新增 `005_model_pricing.sql`。
2. 新增 SQLAlchemy `ModelPriceConfig` 与 usage log 扩展字段。
3. 新增 `ModelPriceConfigRepository`。
4. 新增 `PricingService`，只做纯计算和价格选择。
5. 补齐 PricingService 单元测试。

验收：

- 不接入真实 chat 调用，也能通过测试证明 USD/CNY 独立配置和 cached input 费用计算正确。

### 阶段 2：usage parser 与调用链接入

1. 扩展 `NativeUsageResult` 或新增 `NormalizedUsage`。
2. OpenAI/Gemini parser 提取 `cached_input_tokens`。
3. `UsageService.record()` 接收费用字段。
4. `ChatService`、`NativeProxyService` 在写 usage log 前调用 `PricingService`。
5. 补齐集成测试。

验收：

- 成功请求 usage log 里有 token 明细、费用明细、币种和价格配置 ID。
- cache hit 请求费用为 0，且不会误用供应商 cached input 口径。

### 阶段 3：管理 API

1. 在 `schemas/admin.py` 增加价格配置 schema。
2. 在 `api/v1/admin/resources.py` 增加价格配置 CRUD。
3. API 层校验 model/provider 匹配、币种、单位。
4. 补 admin API 测试。

验收：

- 可以通过 admin API 创建同一模型的 USD/CNY 两套价格配置。
- Usage 计算按配置的币种命中正确价格。

### 阶段 4：管理台展示

1. 新增 Pricing 页面或 Models 价格配置区域。
2. Usage 页面展示费用字段和计算状态。
3. Dashboard 后续可增加按币种分组的成本汇总。

验收：

- 管理员可以不改数据库直接维护价格。
- 可以查看每次请求的费用和费用明细。

## 11. 关键实现建议

- 单价和费用都使用 `Decimal` / `NUMERIC(24,12)`，不要用 float。
- `estimated_cost` 只作为兼容字段，新逻辑以 `total_cost + cost_currency` 为准。
- 币种只记录代码，不做汇率换算；USD/CNY 必须分别配置。
- 价格配置按生效时间查询，避免供应商调价后历史 usage 被重新解释。
- usage log 必须记录 `pricing_config_id` 和 `cost_breakdown`，方便追溯当时为何算出该费用。
- 不要把 gateway response cache hit 当作 cached input；前者是网关无供应商成本，后者是供应商折扣成本。
- 如果 provider 没有返回 usage，第一阶段不要估算 token 成本，记录 `usage_unknown`；估算可以作为后续独立功能。

## 12. 后续扩展

后续可以在不破坏第一阶段结构的前提下增加：

- image/audio/video 按量计费项。
- reasoning tokens 单独计价。
- request 级固定费用。
- 客户侧加价策略，例如成本价、固定倍率、按 client 配价。
- 按币种分组的日/月成本汇总表。
- 价格配置导入导出。
- 供应商价格来源、审核状态、变更记录。
