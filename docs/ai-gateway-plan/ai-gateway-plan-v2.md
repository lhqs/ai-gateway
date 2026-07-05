# AI 网关服务方案确认文档 V2

> 状态：第二轮讨论稿  
> 基于：`docs/ai-gateway-plan.md` 第一轮文档  
> 说明：第一轮文档保留不变，后续每轮较大调整均新建版本文档，便于追踪决策演进。

## 1. 本轮确认结论

本轮已确认以下方向：

- 系统设计必须优先考虑扩展性。
- 第一阶段只实现最核心闭环，但代码结构和数据模型要为后续扩展留足空间。
- 后端技术栈确定为 `uv + Python + FastAPI + PostgreSQL + Redis`。
- 管理后台技术栈确定为 `Vite + React + Tailwind CSS + shadcn/ui`。
- 文档版本需要保留历史记录，不直接覆盖旧方案文档。

## 2. 设计原则

### 2.1 核心闭环优先

第一阶段不追求大而全，而是优先把 AI 网关的最小生产闭环跑通：

- 调用方能通过统一 API 调用模型。
- 网关能完成鉴权、路由、供应商适配、响应转发。
- 网关能记录调用结果、耗时、token 用量和错误信息。
- 管理端能维护基础资源，例如供应商、模型、调用方、API Key 和路由规则。

### 2.2 扩展点前置

即使第一阶段不完整实现高级能力，也需要在模块边界上提前预留扩展点：

- 供应商扩展：新增模型厂商不改 API 层和路由核心逻辑。
- 能力扩展：后续可增加 embeddings、rerank、图像、多模态、工具调用等接口。
- 策略扩展：后续可增加权重路由、成本优先、延迟优先、灰度、熔断和动态降级。
- 治理扩展：后续可增加预算、内容安全、PII 脱敏、审计留存。
- 观测扩展：后续可增加 Prometheus、OpenTelemetry、告警和管理看板。

### 2.3 接口兼容与内部抽象分离

对外 API 可以优先兼容 OpenAI 风格，降低业务方接入成本；但内部不要直接绑定某个供应商协议。建议建立内部统一的请求、响应、错误和 usage 模型，由各供应商 adapter 负责协议转换。

### 2.4 管理后台服务于配置治理

管理后台第一阶段不做复杂 BI 或运营平台，重点用于降低配置维护成本：

- 管理调用方和 API Key。
- 管理供应商和模型。
- 配置模型别名和路由规则。
- 查看调用日志和基础用量统计。

## 3. 技术栈决策

### 3.1 后端

- 包与环境管理：`uv`
- 语言：`Python`
- Web 框架：`FastAPI`
- 数据库：`PostgreSQL`
- 缓存与限流：`Redis`
- 数据校验：`Pydantic`
- 异步 HTTP 客户端：建议 `httpx`
- 数据库 ORM：建议 `SQLAlchemy 2.x` 或 `SQLModel`
- 数据库迁移：建议 `Alembic`
- 测试：建议 `pytest`

后端建议采用异步优先设计。模型调用、流式转发、Redis 操作和数据库访问都可能成为高频路径，FastAPI 与 async HTTP 客户端更适合第一阶段的调用链。

### 3.2 管理后台

- 构建工具：`Vite`
- 前端框架：`React`
- 样式：`Tailwind CSS`
- 组件：`shadcn/ui`
- 表格：建议 `TanStack Table`
- 表单：建议 `react-hook-form + zod`
- 请求：建议 `fetch` 封装或 `TanStack Query`
- 路由：建议 `React Router`

后台 UI 第一阶段以实用、清晰、密度适中的管理界面为主，不做营销式页面。

### 3.3 基础设施

- PostgreSQL 存储长期数据：配置、调用方、模型、路由规则、调用日志、用量统计。
- Redis 存储短期状态：限流计数、并发控制、热点配置缓存、幂等或短期 request 状态。
- Docker Compose 可作为本地开发和早期部署方案。
- 后续生产环境可迁移到 Kubernetes 或已有微服务平台。

## 4. 第一阶段目标

第一阶段建议定义为“可配置、可观测、可扩展的 AI 调用网关 MVP”。

必须完成：

- OpenAI 兼容聊天接口。
- 流式和非流式响应。
- 内部 API Key 鉴权。
- 调用方、供应商、模型、模型别名、路由规则基础管理。
- 至少 1 个供应商 adapter。
- 基础 fallback 机制。
- Redis 限流。
- PostgreSQL 调用日志。
- 管理后台基础页面。

暂缓实现：

- 完整成本预算阻断。
- 高级动态路由。
- 内容安全审核。
- 复杂多租户权限体系。
- Agent 平台。
- RAG 平台。
- 多模态全接口。

## 5. 后端架构建议

### 5.1 目录结构草案

```text
backend/
  app/
    main.py
    api/
      v1/
        chat.py
        admin/
          clients.py
          api_keys.py
          providers.py
          models.py
          routes.py
          usage.py
    core/
      config.py
      security.py
      errors.py
      logging.py
    db/
      session.py
      models.py
      migrations/
    schemas/
      chat.py
      admin.py
      usage.py
    services/
      auth_service.py
      routing_service.py
      policy_service.py
      usage_service.py
      provider_service.py
    providers/
      base.py
      registry.py
      openai_compatible.py
    policies/
      rate_limit.py
      retry.py
      timeout.py
    observability/
      request_context.py
      metrics.py
      audit.py
    repositories/
      clients.py
      providers.py
      models.py
      route_rules.py
      usage_logs.py
  tests/
  pyproject.toml
  alembic.ini
```

### 5.2 核心调用链

1. `chat.py` 接收请求，生成 request id。
2. `auth_service` 校验 API Key，解析调用方。
3. `policy_service` 执行限流、输入长度、权限校验。
4. `routing_service` 根据请求模型名和路由规则选择实际模型。
5. `provider_service` 获取 provider adapter 并发起调用。
6. adapter 将内部请求转换为供应商请求。
7. 响应以普通 JSON 或 SSE 流式返回。
8. `usage_service` 记录调用日志、token、耗时、错误。

## 6. 扩展性设计

### 6.1 Provider Adapter 接口

建议定义统一 adapter 接口：

```python
class ProviderAdapter:
    provider_type: str

    async def chat_completion(self, request: GatewayChatRequest) -> GatewayChatResponse:
        ...

    async def stream_chat_completion(self, request: GatewayChatRequest) -> AsyncIterator[GatewayChatChunk]:
        ...
```

第一阶段可先实现 `openai_compatible` adapter。很多供应商提供 OpenAI 兼容接口，可以先通过配置差异支持多个供应商：

- `base_url`
- `api_key`
- `model_name`
- `headers`
- `timeout`

后续如果供应商协议差异较大，再新增专用 adapter。

### 6.2 能力类型扩展

模型表建议包含 `capabilities` 字段，例如：

```json
["chat", "stream", "tools", "vision", "embedding", "rerank"]
```

第一阶段只实现 `chat` 和 `stream`，但数据结构允许后续按能力筛选模型。

### 6.3 策略扩展

路由规则第一阶段只需要：

- 模型别名。
- 主模型。
- 备用模型列表。
- 启用状态。

但字段设计可以预留：

- `strategy_type`：`primary_fallback`、`weighted`、`latency_first`、`cost_first`。
- `strategy_config`：JSON 配置。
- `priority`：规则优先级。

这样第二阶段可以不重构表结构。

### 6.4 Policy Pipeline

建议将治理能力设计为 pipeline：

```text
before_request:
  auth -> permission -> rate_limit -> quota -> safety_input

after_response:
  usage_record -> cost_calc -> safety_output -> metrics
```

第一阶段只实现其中一部分，但接口可以保持一致。

## 7. 数据模型 V2 草案

### 7.1 `clients`

调用方应用。

- `id`
- `name`
- `description`
- `status`
- `created_at`
- `updated_at`

### 7.2 `api_keys`

内部 API Key，不存明文。

- `id`
- `client_id`
- `name`
- `key_prefix`
- `key_hash`
- `status`
- `last_used_at`
- `expires_at`
- `created_at`
- `updated_at`

### 7.3 `providers`

模型供应商配置。

- `id`
- `name`
- `provider_type`
- `base_url`
- `encrypted_api_key`
- `config`
- `status`
- `created_at`
- `updated_at`

### 7.4 `models`

供应商下的实际模型。

- `id`
- `provider_id`
- `name`
- `display_name`
- `capabilities`
- `context_window`
- `input_price`
- `output_price`
- `currency`
- `status`
- `created_at`
- `updated_at`

### 7.5 `model_aliases`

业务侧使用的模型名。

- `id`
- `alias`
- `description`
- `status`
- `created_at`
- `updated_at`

### 7.6 `route_rules`

别名到实际模型的路由规则。

- `id`
- `model_alias_id`
- `primary_model_id`
- `fallback_model_ids`
- `strategy_type`
- `strategy_config`
- `priority`
- `status`
- `created_at`
- `updated_at`

### 7.7 `usage_logs`

调用明细。

- `id`
- `request_id`
- `client_id`
- `model_alias`
- `provider_id`
- `model_id`
- `stream`
- `status`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `latency_ms`
- `first_token_latency_ms`
- `estimated_cost`
- `error_code`
- `error_message`
- `created_at`

关于 prompt 和 completion：第一阶段建议默认不保存完整内容，只保存长度、token 和必要的调试摘要。是否保存原文需要后续明确合规边界。

## 8. 管理后台范围

### 8.1 第一阶段页面

- Dashboard
  - 今日请求数。
  - 成功率。
  - 平均延迟。
  - token 用量。
  - 错误数量。
- Clients
  - 调用方列表。
  - 创建、禁用、编辑调用方。
- API Keys
  - 创建 key。
  - 查看 key 前缀。
  - 禁用和过期 key。
- Providers
  - 维护供应商名称、类型、base URL、密钥、状态。
- Models
  - 维护模型、能力、上下文窗口、价格。
- Routes
  - 维护模型别名、主模型、fallback 模型。
- Usage Logs
  - 查询调用记录。
  - 按调用方、模型、状态、时间筛选。

### 8.2 暂不做的后台能力

- 复杂权限系统。
- 租户级组织架构。
- 成本账单结算。
- 图表大屏。
- Prompt 内容检索。
- 工作流编排。

## 9. API 范围

### 9.1 业务调用 API

- `POST /v1/chat/completions`
  - OpenAI 兼容。
  - 支持 `stream=false` 和 `stream=true`。

### 9.2 管理 API

- `GET /admin/clients`
- `POST /admin/clients`
- `PATCH /admin/clients/{id}`
- `POST /admin/api-keys`
- `PATCH /admin/api-keys/{id}`
- `GET /admin/providers`
- `POST /admin/providers`
- `PATCH /admin/providers/{id}`
- `GET /admin/models`
- `POST /admin/models`
- `PATCH /admin/models/{id}`
- `GET /admin/model-aliases`
- `POST /admin/model-aliases`
- `GET /admin/route-rules`
- `POST /admin/route-rules`
- `PATCH /admin/route-rules/{id}`
- `GET /admin/usage-logs`
- `GET /admin/dashboard`

管理 API 的鉴权方式仍待确认。第一阶段可以先使用单独的 admin token，后续再演进到用户登录和 RBAC。

## 10. 推荐开发顺序

### 10.1 后端优先闭环

1. 初始化 `uv + FastAPI` 项目。
2. 配置 PostgreSQL、Redis、本地 Docker Compose。
3. 建立数据库模型和 Alembic 迁移。
4. 实现 provider adapter 基类和 OpenAI-compatible adapter。
5. 实现 `/v1/chat/completions` 非流式调用。
6. 实现 API Key 鉴权。
7. 实现模型别名和路由规则。
8. 实现流式 SSE 转发。
9. 实现 Redis 限流。
10. 实现 usage log 入库。

### 10.2 管理后台跟进

1. 初始化 `Vite + React + Tailwind CSS + shadcn/ui`。
2. 搭建应用布局、导航和 API client。
3. 实现供应商、模型、别名、路由规则管理。
4. 实现调用方和 API Key 管理。
5. 实现 usage logs 查询。
6. 实现 dashboard 基础指标。

### 10.3 验证与交付

1. 使用 mock provider 或真实 provider 跑通非流式请求。
2. 跑通流式响应。
3. 验证 fallback。
4. 验证限流。
5. 验证调用日志。
6. 使用后台配置一个完整调用链。

## 11. 仍需确认的问题

为了进入开发设计阶段，还需要确认：

1. 首批接入哪个供应商？是否优先选择 OpenAI 兼容协议的供应商？
2. 第一阶段是否必须支持 OpenAI 原生响应格式完全兼容，还是只做主要字段兼容？
3. 管理后台第一阶段是否需要登录？如果需要，使用什么身份体系？
4. 是否需要多租户字段？如果暂不实现，数据模型是否仍预留 `tenant_id`？
5. API Key 是否只绑定 client，还是要绑定可用模型范围和限额？
6. prompt 和 completion 是否允许落库？如果不允许，是否允许保存摘要、hash 或截断内容？
7. usage 日志保留周期是多久？
8. 第一阶段需要支持哪些限流维度？例如 client、api key、model、provider。
9. 供应商密钥是否需要数据库加密存储？密钥加密主密钥从哪里来？
10. 本地开发和部署是否需要 Docker Compose？
11. 后端和前端是否放在同一个 monorepo 内？
12. 是否需要从第一阶段开始支持 embeddings？

## 12. 决策记录

| 日期 | 决策项 | 结论 | 备注 |
| --- | --- | --- | --- |
| 2026-07-04 | 文档版本策略 | 保留旧文档，新反馈新建版本文档 | 当前文档为 V2 |
| 2026-07-04 | 后端技术栈 | uv + Python + FastAPI + PostgreSQL + Redis | 已确认 |
| 2026-07-04 | 管理后台技术栈 | Vite + React + Tailwind CSS + shadcn/ui | 已确认 |
| 2026-07-04 | 第一阶段方向 | 核心功能优先，架构预留扩展空间 | 已确认 |

