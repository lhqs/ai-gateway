# AI 模型请求价格配置与计费系统 — 实现方案 v2

> 维护日期：2026-07-05
> 适用范围：LHQS AI Gateway 后端计费配置、usage 解析、请求费用计算、管理台展示
> 数据库约束：继续使用 `backend/app/db/sql/` 顺序 SQL 脚本；不使用 Alembic；不新增数据库外键
> 与 v1（`ai-model-pricing-design.md`）的关系：v2 基于 Plan agent 对真实代码库的踩点输出，强化了接入点路径、迁移约束、历史价格快照、currency 二级分组聚合等可落地细节。

---

## 1. 现有代码库摸底（决定方案形态的关键事实）

### 1.1 技术栈

- **后端**:FastAPI(Python 3.12) + SQLAlchemy 2.0 async + Pydantic v2 + asyncpg(PostgreSQL) + Redis(限流 / 缓存)。测试用 aiosqlite + pytest-asyncio + respx。包管理用 `uv`。
- **前端**:Vite + React + TypeScript + Tailwind。无 UI 库,自有组件(`components/ui.tsx`)。路由基于 `window.history` 的简易 tab 切换,无 React Router。
- **数据库迁移**:**不使用 Alembic**,禁止外键。变更通过 `backend/app/db/sql/00X_*.sql` 顺序 SQL 脚本追加(已有 001~004)。所有 DDL 必须幂等(`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`)。
- **多租户 / 认证**:`Client` + `ApiKey`(`access_config` JSON 字段做权限策略),admin 端用 `ADMIN_TOKEN` Bearer(`require_admin` 依赖)。无用户体系,"用户侧"实际上 = client / api key。

### 1.2 后端目录组织

```
backend/app/
├── api/v1/
│   ├── chat.py                # /v1/chat/completions 入口
│   ├── proxy.py               # /proxy/{provider}/{native_path} 入口
│   └── admin/
│       ├── resources.py       # 管理资源 CRUD(clients/providers/models/aliases/routes/api-keys/usage-logs/dashboard)
│       └── workbench.py       # /admin/workbench/chat-test
├── core/                      # config / errors / security
├── db/
│   ├── models.py              # SQLAlchemy ORM 模型
│   ├── session.py             # async engine / session
│   └── sql/                   # 顺序 SQL 脚本
├── policies/                  # rate_limit
├── providers/                 # openai_compatible / gemini_chat / gemini_native / registry
├── repositories/              # Repository[T] 基类 + 各实体 repo
├── schemas/                   # Pydantic: admin / chat / proxy / usage / workbench
├── services/                  # chat_service / native_proxy_service / usage_service / routing / cache / failover
└── usage/parsers/             # openai / gemini / base / registry
```

### 1.3 关键现有数据结构

**`models` 表(已存在价格字段,但未启用 cache 维度)**:

```sql
-- 001_initial_schema.sql 第 53-67 行
CREATE TABLE models (
  id BIGSERIAL PRIMARY KEY,
  provider_id BIGINT NOT NULL,
  name VARCHAR(128),
  display_name VARCHAR(128),
  capabilities JSONB,
  context_window INTEGER,
  input_price NUMERIC(18,8),         -- 已存在,但未使用
  output_price NUMERIC(18,8),        -- 已存在,但未使用
  currency VARCHAR(16) DEFAULT 'USD',-- 已存在,但未使用
  status VARCHAR(32),
  ...
);
```

ORM 同步:`backend/app/db/models.py:78-90` 已经声明了 `input_price` / `output_price` / `currency`。
Schema:`backend/app/schemas/admin.py:129-138` `ModelWrite` 已经接受 `input_price` / `output_price` / `currency`。

→ **价格字段已经"半成品"地挂在 model 上**,但 chat/native_proxy/usage_service 链路里**完全没有任何计费/`estimated_cost` 写入逻辑**。

**`usage_logs` 表**:

```sql
-- 已有字段(与计费相关)
prompt_tokens INTEGER
completion_tokens INTEGER
total_tokens INTEGER
estimated_cost NUMERIC(18,8)         -- 已存在但恒为 NULL
raw_usage JSONB                      -- 已存在,保留原始 usage(关键!)
cache_hit BOOLEAN                     -- 仅指网关自己的 Redis 缓存命中
```

**缺口(决定本方案形态)**:

1. 没有 `cached_input_tokens` / `cache_read_tokens` / `cache_creation_tokens` / `reasoning_tokens` 字段 —— 即便 provider 返回了 `raw_usage`,结构化字段没拆出来,无法精确计费。
2. `cache_hit` 字段语义混淆:它表示的是**网关 Redis 命中**,不是 provider 的 prompt cache(Anthropic / OpenAI 都有这个区分)。
3. `estimated_cost` 字段无 currency,无法区分 CNY/USD。
4. 价格只支持时间点快照,无 `effective_from/effective_to`,调价后历史账单会被错算。
5. `OpenAIUsageParser` 只取 `prompt_tokens`/`completion_tokens`/`total_tokens`,丢弃了 `prompt_tokens_details.cached_tokens`(OpenAI)和 `cache_creation_input_tokens` / `cache_read_input_tokens`(Anthropic)。

### 1.4 usage 写入接入点(计费 hook 的天然位置)

- `backend/app/services/chat_service.py`:3 处 `await self.usage.record(...)`(cache 命中 / 成功 / 失败)+ 流式 3 处。
- `backend/app/services/native_proxy_service.py`:`forward` 2 处 + `stream` 内 `iterator` 3 处。
- 唯一入口:`UsageService.record(**data)` → `UsageLogRepository.create_log(data)`。

→ **最佳 hook 点**:在 `UsageService.record` 内部统一计算 cost,所有调用点不用改。把计费从"散落在 chat_service / native_proxy_service"收口到 `usage_service`。

### 1.5 前端

- `frontend/src/pages/ModelsPage.tsx` —— model 的 CRUD 表单**完全没暴露** `input_price` / `output_price` / `currency`(虽然后端 schema 已支持)。
- `frontend/src/pages/UsagePage.tsx` —— 列表无 cost 列。
- `frontend/src/pages/DashboardPage.tsx` —— 4 个 Metric,无成本维度。
- `frontend/src/types/gateway.ts:62-69` `Model` 类型**没有** price 字段。

### 1.6 已有的 TODO / 半成品

`docs/ai-gateway-v3-todo.md` 第 274-283 行 P1-4 "Usage Logs 查询能力不足",与计费查询紧密相关。

---

## 2. 系统设计

### 2.1 关键决策

#### 决策 1:价格表挂在哪里?

**选项 A**:扩展现有 `models.input_price` / `output_price`(已半成品),加 `cached_input_price`。
**选项 B**:新建独立的 `model_pricings` 表,按时间区间生效(`effective_from/effective_to`)。

**采用 B(独立表 + 时间区间)**,理由:
- 一期虽然供应商调价不频繁,但 OpenAI / Anthropic 在 2024-2025 已多次调价,**历史账单必须可重算**。如果价格就挂在 `models` 主表上,调价后老 `usage_logs.estimated_cost` 会被覆盖丢失。
- `usage_logs` 在写入时**冻结当时价格快照**(在 `cost` 之外另存 `cost_snapshot` JSON),这样无论未来价格怎么变,历史账单不变;而独立 `model_pricings` 表的存在是为了"按当前价格表新增/调整 + 偶尔重算历史"。
- `models.input_price/output_price/currency` 字段**保留**,作为"当前默认价格"的便捷字段,与 `model_pricings` 中当前生效行保持冗余同步(写入时由 service 维护),降低 list 视图的 join 成本。

#### 决策 2:token 维度

一期纳入:`input_tokens` / `cached_input_tokens` / `output_tokens`。
后置(M3+ 或不做):`cache_creation_tokens`(Anthropic 写入侧)、`reasoning_tokens`(o1/o3)、`audio_tokens`、image。

理由:
- Anthropic prompt cache 和 OpenAI cached input 都是**实际折扣到 input 单价 10%~50% 的强需求**,是本期的核心目标。
- `cache_creation_tokens` 在 Anthropic 计费中**比普通 input 还贵 25%**,但需要先支持 cache write 才能合理定价。**保留 schema 扩展位但一期默认不暴露**。
- reasoning / audio / image 涉及供应商差异大、暂时非必需。

#### 决策 3:币种

**不引入汇率表,币种记录在 `model_pricings.currency`**。`usage_logs` 在写入 cost 时同时记录 `cost_currency`,**不进行跨币种换算**。聚合查询时按 currency 分桶返回。

#### 决策 4:计价单位

**统一为"每 1M tokens"**,类型 `NUMERIC(18,6)`。

理由:
- 当前主流厂商(OpenAI、Anthropic、Gemini)官方定价页都是 $X per 1M tokens。
- 项目现有 `NUMERIC(18,8)` 是历史包袱,8 位小数对 USD 单价(如 0.000001)够用,但语义不直观。
- 改为 per 1M 后,常见价格如 `$3.00` 直接落库,前端展示时除以 1M 计算 cost 即可,不用看小数位找零。

> **注意**:`models.input_price/output_price` 已经按 per-token 写过 schema,但因为没人用,可以直接语义重定义为 per 1M,不破坏兼容。

#### 决策 5:精度

数据库 `NUMERIC(18,6)`(Decimal)。Python 用 `decimal.Decimal`,**禁止 float**。已有的 `Decimal` 导入(`db/models.py:2`)正合适。

### 2.2 数据模型设计

#### 2.2.1 新表 `model_pricings`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `model_id` | BIGINT | NOT NULL, INDEX | 关联 `models.id`,**不用外键**(项目约束)|
| `currency` | VARCHAR(8) | NOT NULL | `USD` / `CNY` |
| `input_price` | NUMERIC(18,6) | NOT NULL | 每 1M tokens |
| `cached_input_price` | NUMERIC(18,6) | NOT NULL DEFAULT 0 | 每 1M tokens,缓存命中部分 |
| `output_price` | NUMERIC(18,6) | NOT NULL | 每 1M tokens |
| `effective_from` | TIMESTAMPTZ | NOT NULL | 生效起始 |
| `effective_to` | TIMESTAMPTZ | NULL | NULL 表示当前生效 |
| `status` | VARCHAR(16) | NOT NULL DEFAULT 'active' | active / archived |
| `note` | TEXT | NULL | 调价备注 |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**约束(应用层 + DB 唯一索引)**:同一 `(model_id, currency)` 同时只能有一行 `effective_to IS NULL`("当前价"唯一)。

```sql
-- backend/app/db/sql/005_model_pricings.sql
CREATE TABLE IF NOT EXISTS model_pricings (
  id BIGSERIAL PRIMARY KEY,
  model_id BIGINT NOT NULL,
  currency VARCHAR(8) NOT NULL,
  input_price NUMERIC(18,6) NOT NULL,
  cached_input_price NUMERIC(18,6) NOT NULL DEFAULT 0,
  output_price NUMERIC(18,6) NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_to TIMESTAMPTZ,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_pricings_model_id ON model_pricings(model_id);
CREATE INDEX IF NOT EXISTS idx_model_pricings_model_currency_effective
  ON model_pricings(model_id, currency, effective_to);
-- 单值"当前价"约束:通过 partial unique index 强制
CREATE UNIQUE INDEX IF NOT EXISTS uq_model_pricings_current
  ON model_pricings(model_id, currency) WHERE effective_to IS NULL;
```

#### 2.2.2 `usage_logs` 扩展

新增列(保留原表,向后兼容):

```sql
-- backend/app/db/sql/006_usage_logs_cost.sql
ALTER TABLE usage_logs
  ADD COLUMN IF NOT EXISTS cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER NOT NULL DEFAULT 0,        -- provider 侧 prompt cache 命中
  ADD COLUMN IF NOT EXISTS cost NUMERIC(18,8) NOT NULL DEFAULT 0,               -- 替代/并存于 estimated_cost
  ADD COLUMN IF NOT EXISTS cost_currency VARCHAR(8),                            -- 跟随 model_pricings.currency
  ADD COLUMN IF NOT EXISTS cost_snapshot JSONB,                                  -- 冻结的计价快照(输入/缓存/输出单价、币种、模型、生效区间 id)
  ADD COLUMN IF NOT EXISTS pricing_id BIGINT;                                    -- 关联 model_pricings.id(无 FK)
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at_cost
  ON usage_logs(created_at) WHERE cost > 0;
```

说明:
- `cached_input_tokens` 是"网关 Redis 缓存命中场景"的 prompt_tokens(语义沿用现有 `cache_hit`),那部分不计费。
- `cache_read_tokens` 是**provider prompt cache 命中**的 tokens,按 `cached_input_price` 计费。
- `cost` 用 `Decimal`,前端展示时和 `cost_currency` 一起显示。
- `estimated_cost` 字段保留不动(避免破坏旧测试),新逻辑只用 `cost`。

#### 2.2.3 `models` 表

**不动 schema**(已有的 `input_price`/`output_price`/`currency` 保留),但 service 层在 `model_pricings` 写入时同步刷新 `models` 的冗余字段(让 ModelsPage 列表能直接看到当前价)。

### 2.3 计费计算逻辑

#### 2.3.1 接入点:`UsageService.record`

```python
# backend/app/services/usage_service.py (新)
from decimal import Decimal
from datetime import datetime, timezone

class UsageService:
    def __init__(self, session):
        self.session = session
        self.repo = UsageLogRepository(session)
        self.pricings = PricingRepository(session)

    async def record(self, *, model_id: int | None, prompt_tokens: int,
                     completion_tokens: int, cache_read_tokens: int = 0,
                     cache_hit: bool = False, status: str, **data) -> None:
        cost = Decimal("0")
        cost_currency = None
        snapshot = None
        pricing_id = None

        # 网关缓存命中不计费(即使 provider 不会真的返回 0 token)
        if cache_hit or status != "success":
            billable_prompt = 0
            billable_cached = 0
            billable_completion = 0
        else:
            billable_prompt = max(prompt_tokens - cache_read_tokens, 0)
            billable_cached = cache_read_tokens
            billable_completion = completion_tokens

        if model_id and status == "success" and not cache_hit:
            pricing = await self.pricings.get_effective(model_id)
            if pricing:
                cost_currency = pricing.currency
                pricing_id = pricing.id
                snapshot = {
                    "input_price": str(pricing.input_price),
                    "cached_input_price": str(pricing.cached_input_price),
                    "output_price": str(pricing.output_price),
                    "currency": pricing.currency,
                    "unit": "per_1m_tokens",
                }
                million = Decimal("1000000")
                cost = (
                    (pricing.input_price * Decimal(billable_prompt) / million)
                    + (pricing.cached_input_price * Decimal(billable_cached) / million)
                    + (pricing.output_price * Decimal(billable_completion) / million)
                ).quantize(Decimal("0.00000001"))

        await self.repo.create_log({
            **data,
            "model_id": model_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cache_read_tokens": cache_read_tokens,
            "status": status,
            "cost": cost,
            "cost_currency": cost_currency,
            "cost_snapshot": snapshot,
            "pricing_id": pricing_id,
        })
```

注意:
- **chat_service / native_proxy_service 的所有 `self.usage.record(...)` 调用点都需要补传 `cache_read_tokens`**(从解析器拿)。
- **网关 cache_hit 命中**:`prompt_tokens = completion_tokens = 0`,cost 自然 = 0,无需特判。但保留 `cache_read_tokens = 0`,避免和 provider cache 混淆。

#### 2.3.2 解析器扩展(关键)

```python
# backend/app/usage/parsers/openai.py (扩展)
class OpenAIUsageParser:
    def parse(self, payload):
        usage = (payload or {}).get("usage")
        if not isinstance(usage, dict):
            return NativeUsageResult(raw_usage=None, usage_status="unknown")
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        cache_read = 0
        details = usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            cache_read = int(details.get("cached_tokens") or 0)
        result = NativeUsageResult(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            raw_usage=usage,
            usage_status="parsed",
        )
        # 给 NativeUsageResult 加 cache_read_tokens 字段(见 schemas/proxy.py)
        result.cache_read_tokens = cache_read
        return result
```

`NativeUsageResult` / `GatewayChatResponse` / `GatewayChatChunk` 都需要加 `cache_read_tokens: int = 0` 字段(`schemas/proxy.py` + `schemas/chat.py`)。

Anthropic(如果后续接入 anthropic provider adapter):解析 `usage.cache_read_input_tokens` 和 `usage.cache_creation_input_tokens`,前者填 `cache_read_tokens`,后者一期忽略。

#### 2.3.3 失败 / 重试计费

现状:失败请求 `prompt_tokens=0`,所以**失败请求 cost = 0**。这符合"计费跟着实际 token 走"的语义,**保持不变**。

注意 failover 场景:当前 `chat_service` 每次 attempt 都会写一条 usage_log(status=failed),最后成功的那条也写一条。这是**正确的**:失败 attempt 不计费,成功 attempt 计费。无需改动。

### 2.4 API 设计

#### 管理员侧(`/admin`)

新建 `backend/app/api/v1/admin/pricings.py`:

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/models/{model_id}/pricings` | 列出某 model 的所有历史定价 |
| POST | `/admin/models/{model_id}/pricings` | 新增当前价格(自动把上一条置 `effective_to=now()`|
| PATCH | `/admin/pricings/{id}` | 修改备注 / status,**不允许改价格**(要改请新增)|
| POST | `/admin/pricings/{id}/archive` | 归档(设 `effective_to=now()`)|

Pydantic schema 加在 `schemas/admin.py`:`PricingWrite` / `PricingRead` / `PricingPage`。

#### 用户侧 / 聚合查询(`/admin`,一期不分权限)

扩展现有 `/admin/usage-logs` 不够,新增聚合接口:

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/usage-logs` | **扩展**:响应里加 `cost` / `cost_currency` / `cache_read_tokens` |
| GET | `/admin/usage/summary` | 一期聚合:按 `client_id` / `model_id` / `model_alias` / `provider_id` / `currency` / 时间区间分组,返回总 tokens、总 cost(按 currency 拆分)|
| GET | `/admin/usage/cost-by-model` | 按模型维度(适合 Dashboard 饼图)|
| GET | `/admin/usage/cost-by-day` | 按天时序(适合折线图)|

聚合查询实现:在 `UsageLogRepository` 加 `summary_grouped(group_by: list[str], start, end)` 方法,用 SQL `GROUP BY` + `SUM(cost)`。**因 currency 不同,必须按 currency 二级分组**,避免 CNY + USD 直接相加。

### 2.5 前端

| 改动 | 文件 | 说明 |
|---|---|---|
| Model 表单加价格区块 | `frontend/src/pages/ModelsPage.tsx` | 新增字段:`input_price` / `cached_input_price` / `output_price` / `currency`;提交时调 `POST /admin/models/{id}/pricings`(而不是只 PATCH model)|
| Model 列表加价格列 | 同上 | 显示当前价(从 model 冗余字段读)|
| 新页 `PricingPage`(M2)| `frontend/src/pages/PricingPage.tsx` | 列出 model 历史价格、新增/归档;**或**直接合并到 ModelsPage 的展开行 |
| Usage 表加 cost 列 | `frontend/src/pages/UsagePage.tsx` | 列:`cost (currency)`、`cache_read_tokens` |
| Dashboard 加成本 Metric | `frontend/src/pages/DashboardPage.tsx` | M3 |
| 类型扩展 | `frontend/src/types/gateway.ts` | `Model` 加 `input_price` / `output_price` / `cached_input_price` / `currency`;`UsageLog` 加 `cost` / `cost_currency` / `cache_read_tokens` |

复用 `components/ui.tsx` 现有组件(`Field` / `Input` / `Select` / `Section` / `DataTable` / `Modal` / `Pagination` / `Badge` / `Button`),无需新增组件库。

### 2.6 数据流总结

```
请求进入 → chat_service / native_proxy_service
        ↓
provider adapter → OpenAIUsageParser 提取 cache_read_tokens
        ↓
ChatService 调 self.usage.record(..., cache_read_tokens=X)
        ↓
UsageService.record 查 model_pricings(按 model_id 取当前价)
        ↓
计算 cost(Decimal) + 冻结 snapshot → 写 usage_logs
        ↓
admin 前端查 /admin/usage-logs(含 cost)/ /admin/usage/summary
```

---

## 3. 落地分阶段

### M1:数据底座 + 计费 hook(小~中)

**目标**:链路上能算出 cost,但还没 UI 配置入口(通过 SQL 手工写 pricing)。

**交付物**:
1. `backend/app/db/sql/005_model_pricings.sql`(新文件)
2. `backend/app/db/sql/006_usage_logs_cost.sql`(新文件)
3. `backend/app/db/models.py`:加 `ModelPricing` 模型,`UsageLog` 加新字段映射
4. `backend/app/repositories/pricings.py`(新文件):`PricingRepository.get_effective(model_id, currency=None)` / `set_current(...)`
5. `backend/app/schemas/proxy.py` + `schemas/chat.py`:`NativeUsageResult` / `GatewayChatResponse` / `GatewayChatChunk` 加 `cache_read_tokens: int = 0`
6. `backend/app/usage/parsers/openai.py`:解析 `prompt_tokens_details.cached_tokens`
7. `backend/app/services/usage_service.py`:注入 `PricingRepository`,实现计费
8. `backend/app/services/chat_service.py` + `native_proxy_service.py`:所有 `self.usage.record(...)` 调用补传 `cache_read_tokens`
9. `backend/tests/test_pricing.py`(新):覆盖 (a) cached_tokens 解析、(b) 网关缓存命中 cost=0、(c) 价格快照冻结、(d) Decimal 精度

**验收标准**:
- `uv run pytest` 通过,新增测试覆盖 ≥ 4 个用例。
- 手工 SQL 插入一条 `model_pricings` 后,发一次 chat 请求,`usage_logs.cost` 非 0 且 currency 正确。
- 模拟 OpenAI 响应带 `prompt_tokens_details.cached_tokens=500`,cost 中按 cached_input_price 折算。

**改动文件清单(真实路径)**:
- 新增:`backend/app/db/sql/005_model_pricings.sql`、`backend/app/db/sql/006_usage_logs_cost.sql`、`backend/app/repositories/pricings.py`、`backend/tests/test_pricing.py`
- 修改:`backend/app/db/models.py`、`backend/app/schemas/proxy.py`、`backend/app/schemas/chat.py`、`backend/app/usage/parsers/openai.py`、`backend/app/services/usage_service.py`、`backend/app/services/chat_service.py`、`backend/app/services/native_proxy_service.py`、`backend/app/repositories/usage_logs.py`

**工作量**:中(约 1.5 人日)。

### M2:价格配置 UI + Schema 完善(中)

**目标**:管理员能在前端配置价格。

**交付物**:
1. `backend/app/schemas/admin.py`:加 `PricingWrite` / `PricingRead` / `PricingPage` / `PricingArchive`
2. `backend/app/api/v1/admin/pricings.py`(新文件)
3. `backend/app/main.py`:注册新 router
4. `backend/app/repositories/models.py`:写 model 时同步刷新冗余字段(或在 pricing 写入时联动)
5. `frontend/src/types/gateway.ts`:扩展 `Model` + 新增 `Pricing` 类型
6. `frontend/src/pages/ModelsPage.tsx`:表单加价格字段、列表加价格列;新建/编辑 model 时同时调 pricing 接口
7. `frontend/src/pages/PricingPage.tsx`(**推荐合并到 ModelsPage** 展开行,避免新增 tab;如要独立 tab,加 `tabPaths.pricing` + layout nav)

**验收标准**:
- 前端能新增 model 并同时填三档价格 + 币种。
- 已有 model 调价后,老价格自动归档(`effective_to`),新价格生效。
- 前端列表显示当前价;展开可看历史价格。
- `npm run build` 通过。

**改动文件清单**:
- 新增:`backend/app/api/v1/admin/pricings.py`、(可选)`frontend/src/pages/PricingPage.tsx`
- 修改:`backend/app/schemas/admin.py`、`backend/app/main.py`、`backend/app/repositories/models.py`、`frontend/src/types/gateway.ts`、`frontend/src/pages/ModelsPage.tsx`、`frontend/src/lib/routes.ts`(如新增 tab)、`frontend/src/components/layout.tsx`(如新增 nav)、`frontend/src/App.tsx`(如新增 tab 路由)

**工作量**:中(约 1.5~2 人日)。

### M3:成本查询 + Dashboard(中~大)

**目标**:管理员能看到成本聚合。

**交付物**:
1. `backend/app/repositories/usage_logs.py`:加 `summary_grouped(...)` / `cost_by_model(...)` / `cost_by_day(...)`,**按 currency 二级分组**
2. `backend/app/schemas/usage.py`:加 `UsageSummary` / `CostByModelRow` / `CostByDayRow`
3. `backend/app/api/v1/admin/resources.py` 或新建 `analytics.py`:3 个聚合接口
4. `backend/app/api/v1/admin/resources.py`:`list_usage_logs` 响应扩展(实际就是改 `UsageLogRead`)
5. `backend/app/schemas/usage.py`:`UsageLogRead` 加 `cost` / `cost_currency` / `cache_read_tokens`
6. `frontend/src/pages/UsagePage.tsx`:加 cost 列、currency 筛选、时间范围筛选
7. `frontend/src/pages/DashboardPage.tsx`:加 2 个 Metric("今日成本 USD"、"今日成本 CNY",按 currency 拆分显示)

**验收标准**:
- UsagePage 表格能展示 cost + currency,能按时间区间 / model / client 筛选。
- Dashboard 显示双币种成本(不混算)。
- 聚合接口测试覆盖。

**改动文件清单**:
- 修改:`backend/app/repositories/usage_logs.py`、`backend/app/schemas/usage.py`、`backend/app/api/v1/admin/resources.py`、`frontend/src/pages/UsagePage.tsx`、`frontend/src/pages/DashboardPage.tsx`、`frontend/src/types/gateway.ts`
- 新增:(可选)`backend/app/api/v1/admin/analytics.py`、`backend/tests/test_usage_summary.py`

**工作量**:中~大(约 2~3 人日)。

### M4(可选 / 后置):扩展计费维度

- Anthropic provider adapter(含 `cache_creation_input_tokens` 计费维度)。
- `reasoning_tokens`(OpenAI o1/o3)。
- Image / audio tokens。
- 跨币种聚合展示(按"展示币种 + 静态汇率表"做可选换算,不在一期)。

**工作量**:中。

---

## 4. 风险与回避

| 风险 | 回避 |
|---|---|
| `models.input_price` 已有字段被旧代码读取 | 全局 grep 确认只有 ORM / schema 声明,无实际读取计费逻辑(已确认)|
| Partial unique index 在老 PG 版本不支持 | PG 11+ 支持,项目用 asyncpg + 现代 PG,无问题 |
| 网关 cache_hit 与 provider cache 语义混淆 | 用 `cache_read_tokens`(provider 侧)独立字段,`cache_hit` 维持原义(网关侧)|
| Decimal / float 序列化到 JSON 丢精度 | Pydantic v2 默认 `Decimal → str`,前端展示时按字符串处理;`cost_snapshot` 也用 `str(pricing.input_price)` |
| 调价后历史 cost 被覆盖 | `usage_logs.cost_snapshot` 冻结价格,且 `model_pricings` 老行只归档不删除 |
| CNY/USD 误加 | 聚合 SQL 强制 `GROUP BY currency`,service 层返回 dict `{currency: amount}` |

---

## 5. 关键文件清单(实现时第一波要动的)

- `/Users/lhqs/devloper/workspace/projects/lhqs-ai-gateway/backend/app/services/usage_service.py`(计费 hook 收口点,M1 核心)
- `/Users/lhqs/devloper/workspace/projects/lhqs-ai-gateway/backend/app/db/sql/001_initial_schema.sql`(新 SQL 脚本 005/006 的格式与命名参照对象)
- `/Users/lhqs/devloper/workspace/projects/lhqs-ai-gateway/backend/app/db/models.py`(新增 `ModelPricing` ORM 与 `UsageLog` 字段扩展)
- `/Users/lhqs/devloper/workspace/projects/lhqs-ai-gateway/backend/app/usage/parsers/openai.py`(`cached_tokens` 解析接入点)
- `/Users/lhqs/devloper/workspace/projects/lhqs-ai-gateway/frontend/src/pages/ModelsPage.tsx`(价格配置 UI 主战场)
