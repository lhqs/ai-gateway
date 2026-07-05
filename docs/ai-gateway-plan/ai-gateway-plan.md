# AI 网关服务方案确认文档

> 状态：第一轮讨论稿  
> 目标：在正式开发前，通过多轮确认沉淀 AI 网关的目标、边界、架构、功能清单和实施计划。

## 1. 背景与目标

AI 网关服务用于统一承接业务系统对大模型能力的调用，屏蔽不同模型供应商、模型协议、鉴权方式、限流策略、审计要求和成本统计差异。业务系统只需要接入一套稳定的内部 API，由网关负责路由、治理、观测和安全控制。

第一阶段建议目标：

- 提供统一的模型调用入口，支持聊天补全、流式输出和非流式输出。
- 支持多供应商、多模型配置，例如 OpenAI、Azure OpenAI、Anthropic、Google、阿里云、火山、智谱、DeepSeek、本地模型等。
- 支持租户、应用或调用方维度的 API Key 鉴权。
- 支持基础限流、并发控制、超时控制和失败重试。
- 记录调用日志、token 用量、耗时、状态码、错误原因和费用估算。
- 提供可扩展的模型路由策略，包括指定模型、默认模型、按权重路由、失败降级。
- 为后续增加审计、内容安全、缓存、成本预算、管理后台等能力预留扩展点。

## 2. 核心问题定义

AI 网关优先解决以下问题：

1. 接入复杂度：业务方不直接对接多个模型厂商。
2. 稳定性：统一处理超时、重试、降级、熔断和错误映射。
3. 成本治理：统计 token、调用次数、模型成本，并可按调用方分摊。
4. 安全合规：统一鉴权、密钥管理、敏感信息脱敏和调用审计。
5. 可观测性：统一日志、指标、链路追踪和告警。
6. 可演进性：后续可以扩展 RAG、Agent、工具调用、模型评测和策略编排。

## 3. 功能范围

### 3.1 第一阶段必须能力

- 统一 API
  - `POST /v1/chat/completions`
  - 兼容 OpenAI 风格请求和响应，降低业务接入成本。
  - 支持 `stream=true` 的 SSE 流式响应。
- 调用方鉴权
  - 内部 API Key。
  - 绑定调用方、租户、应用、可用模型和额度策略。
- 模型供应商适配
  - 至少先适配 1 到 2 个供应商。
  - 每个供应商封装为独立 adapter。
  - 网关内部使用统一请求和响应结构。
- 路由策略
  - 支持通过请求参数指定模型。
  - 支持模型别名，例如 `gpt-4o-mini`、`default-chat`、`reasoning`。
  - 支持 fallback，例如主模型失败后切换备用模型。
- 治理能力
  - 请求超时。
  - 基础重试。
  - 调用方维度限流。
  - 最大输入 token 或字符数限制。
- 观测与审计
  - 请求 ID。
  - 结构化日志。
  - 调用记录入库。
  - token 用量、延迟、供应商、模型、调用方、错误码。

### 3.2 第二阶段增强能力

- 管理后台或管理 API
  - 管理供应商、模型、API Key、租户、额度、路由策略。
- 成本与预算
  - 按供应商模型配置单价。
  - 按调用方统计成本。
  - 支持日、周、月预算和超额阻断。
- 内容安全
  - 请求和响应敏感词检测。
  - PII 脱敏。
  - 安全策略按租户配置。
- 缓存
  - 对可缓存的非流式请求做语义或精确缓存。
  - 缓存命中计入单独指标。
- 高级路由
  - 权重路由。
  - 按延迟、成本、成功率动态选择模型。
  - 灰度发布。
- 可观测性增强
  - Prometheus 指标。
  - OpenTelemetry 链路追踪。
  - 告警规则。

### 3.3 暂不建议第一阶段实现

- 完整 Agent 平台。
- 复杂工作流编排。
- 多模态全能力统一，例如音频、视频、图像生成全部纳入。
- 大规模模型评测平台。
- 复杂计费结算系统。

这些能力可以作为后续模块，但不应阻塞网关 MVP。

## 4. 非功能要求

- 可用性：核心调用链不能依赖管理后台，配置加载失败时应有明确降级策略。
- 性能：网关本身应保持低额外延迟，非流式请求额外开销目标小于 50ms，流式首包尽量不做重处理。
- 安全：供应商密钥不能暴露给业务方，日志默认不记录完整 prompt 和 completion，或提供脱敏策略。
- 可扩展：新增供应商时不应改动核心路由逻辑。
- 可维护：错误码、日志字段、配置结构和适配器接口需要稳定。
- 可部署：支持容器化部署，配置通过环境变量和数据库配置组合管理。

## 5. 建议架构

### 5.1 模块划分

- API 层
  - 提供 OpenAI 兼容接口。
  - 处理鉴权、参数校验、请求 ID、响应格式。
- Auth 模块
  - 校验内部 API Key。
  - 解析调用方身份、租户、权限和额度。
- Router 模块
  - 将业务模型名解析为实际供应商模型。
  - 执行默认路由、指定路由、fallback、灰度等策略。
- Provider Adapter 模块
  - 每个供应商一个适配器。
  - 负责协议转换、签名、流式响应解析、错误映射。
- Policy 模块
  - 限流、并发、预算、内容安全、最大 token 限制。
- Observability 模块
  - 日志、指标、追踪、调用记录。
- Config 模块
  - 加载供应商、模型、路由、密钥、调用方配置。
- Storage 模块
  - 存储调用记录、用量统计、配置和审计数据。

### 5.2 请求流程

1. 业务系统调用网关 API。
2. API 层生成 request id，完成参数校验。
3. Auth 模块校验调用方身份和权限。
4. Policy 模块执行限流、额度和输入限制。
5. Router 模块选择目标供应商和模型。
6. Provider Adapter 转换请求并调用外部模型服务。
7. 流式或非流式响应返回给业务系统。
8. Observability 模块记录日志、指标、token、耗时和错误。
9. 失败时根据策略执行重试或 fallback。

## 6. 数据模型草案

第一阶段建议至少包含以下实体：

- `clients`
  - 调用方应用。
  - 字段：id、name、tenant_id、status、created_at。
- `api_keys`
  - 内部鉴权 key。
  - 字段：id、client_id、key_hash、status、expires_at、created_at。
- `providers`
  - 模型供应商。
  - 字段：id、name、type、base_url、status、config。
- `models`
  - 可用模型。
  - 字段：id、provider_id、model_name、alias、capabilities、price_config、status。
- `route_rules`
  - 路由规则。
  - 字段：id、client_id、model_alias、primary_model_id、fallback_model_ids、weight_config、status。
- `usage_logs`
  - 调用记录。
  - 字段：id、request_id、client_id、provider_id、model_id、status、prompt_tokens、completion_tokens、total_tokens、latency_ms、estimated_cost、error_code、created_at。

## 7. 技术选型待确认

当前还不建议直接写死技术栈，需要结合团队熟悉度和部署环境确认。候选方向：

### 7.1 服务端语言

- Node.js / TypeScript
  - 优点：生态适合 API 网关、SSE、前后端统一语言。
  - 适合：团队偏前端或全栈，快速 MVP。
- Go
  - 优点：并发、性能、部署简单，适合网关类服务。
  - 适合：高并发、基础设施团队。
- Python
  - 优点：AI 生态丰富，原型快。
  - 适合：与 AI 工具链深度集成，但作为高并发网关需更谨慎。
- Java / Kotlin
  - 优点：企业系统成熟，治理能力强。
  - 适合：已有 Java 微服务体系。

### 7.2 存储与基础设施

- PostgreSQL：存储配置、调用记录、统计数据。
- Redis：限流、缓存、并发控制、短期计数。
- Prometheus + Grafana：指标与看板。
- OpenTelemetry：链路追踪。
- Docker / Kubernetes：部署和扩缩容。

## 8. API 设计草案

### 8.1 聊天补全

```http
POST /v1/chat/completions
Authorization: Bearer <internal-api-key>
Content-Type: application/json
```

请求示例：

```json
{
  "model": "default-chat",
  "messages": [
    {
      "role": "user",
      "content": "介绍一下我们的产品"
    }
  ],
  "temperature": 0.7,
  "stream": true
}
```

响应建议兼容 OpenAI 风格，内部可增加响应头：

- `x-request-id`
- `x-provider`
- `x-model`
- `x-latency-ms`

### 8.2 管理 API

管理 API 可以第二阶段实现，第一阶段先通过配置文件或数据库初始化脚本管理。

候选接口：

- `POST /admin/providers`
- `POST /admin/models`
- `POST /admin/clients`
- `POST /admin/api-keys`
- `POST /admin/route-rules`
- `GET /admin/usage`

## 9. 实施阶段建议

### 阶段 0：方案确认

- 明确首批接入供应商和模型。
- 明确调用方数量、QPS、并发和延迟目标。
- 明确是否必须兼容 OpenAI API。
- 明确部署环境和技术栈。
- 明确日志中是否允许保存 prompt 和 completion。

### 阶段 1：MVP

- 搭建服务框架。
- 实现 OpenAI 兼容 chat completions。
- 实现内部 API Key 鉴权。
- 实现 1 到 2 个供应商 adapter。
- 实现模型别名和 fallback。
- 实现基础日志、调用记录和 token 用量统计。
- 实现基础限流和超时。

### 阶段 2：生产化

- 接入 Redis 限流。
- 接入 PostgreSQL 配置和调用记录。
- 增加 Prometheus 指标。
- 增加管理 API。
- 增加错误码体系和告警。
- 增加配置热加载或缓存刷新。

### 阶段 3：治理增强

- 成本预算。
- 内容安全。
- 高级路由。
- 灰度发布。
- 缓存。
- 多模态接口扩展。

## 10. 第一轮待确认问题

请优先确认以下问题，后续方案会根据答案收敛：

1. 首批要接入哪些模型供应商和模型？
2. 是否要求 API 兼容 OpenAI 格式？
3. 网关主要服务内部系统，还是也会开放给外部客户？
4. 是否需要多租户？租户、应用、用户三者是否都要建模？
5. 第一阶段是否需要管理后台，还是只需要配置文件或管理 API？
6. 预计调用规模是多少？例如 QPS、并发、日请求量、流式请求占比。
7. 是否允许记录原始 prompt 和 completion？是否需要脱敏？
8. 是否需要按调用方做成本统计和预算阻断？
9. 部署环境是什么？单机、Docker Compose、Kubernetes、已有微服务平台？
10. 团队倾向的技术栈是什么？
11. 是否需要支持 embeddings、rerank、图像理解、图像生成、语音等接口？
12. 是否存在合规要求，例如数据不能出境、供应商白名单、审计留存周期？

## 11. 初步建议

在需求尚未完全确认前，建议先按“OpenAI 兼容 API + 可插拔供应商 adapter + Redis 限流 + PostgreSQL 记录”的方向设计。这样可以最大化降低业务方接入成本，同时保留未来治理能力。

如果团队没有强技术栈偏好：

- 偏快速落地：Node.js / TypeScript。
- 偏基础设施和高并发：Go。
- 偏 AI 原型和实验：Python。

第一版不要做成大而全平台，应先把“稳定代理、统一鉴权、模型路由、调用记录、基础限流”做好。

## 12. 决策记录

| 日期 | 决策项 | 结论 | 备注 |
| --- | --- | --- | --- |
| 2026-07-04 | 文档初始化 | 第一轮讨论稿 | 待补充业务约束 |

