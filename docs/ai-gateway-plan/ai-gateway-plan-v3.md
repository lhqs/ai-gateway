# AI 网关服务方案确认文档 V3

> 状态：第三轮讨论稿，已合并第三轮确认反馈  
> 基于：`docs/ai-gateway-plan-v2.md`  
> 说明：V1、V2 文档保留不变。本版本补充“非 OpenAI 兼容供应商的原生协议代理”能力，并按本轮要求直接更新 V3，不新建 V4。

## 1. 本轮新增结论

本轮确认：

- AI 网关不仅支持 OpenAI 兼容协议供应商。
- 对 Gemini 等非 OpenAI 兼容供应商，也需要支持其原生协议代理。
- 原生协议代理不强制转换为 OpenAI 格式，重点做 API 转发、鉴权、限流、调用日志和用量监控。
- MVP 需要包含缓存能力。
- MVP 需要包含自动故障转移核心能力。
- 系统需要同时支持两类调用模式：
  - 统一协议模式：对外暴露 OpenAI 兼容接口，由网关做协议转换和模型路由。
  - 原生代理模式：对外暴露供应商原生协议代理入口，由网关保持请求和响应形态，做治理和观测。

## 2. 调用模式调整

### 2.1 统一协议模式

统一协议模式面向希望低成本接入多个模型的业务方。

典型接口：

```http
POST /v1/chat/completions
Authorization: Bearer <internal-api-key>
Content-Type: application/json
```

适用场景：

- 业务方希望使用一套 OpenAI 风格 API。
- 供应商本身支持 OpenAI 兼容协议。
- 网关需要做模型别名、fallback、统一错误格式、统一 usage 统计。
- 后续需要在不同供应商之间做路由和降级。
- 网关需要在主模型异常时自动故障转移到备用模型。

第一阶段优先支持：

- OpenAI-compatible adapter。
- 非流式和流式聊天接口。
- 模型别名、fallback 与自动故障转移。
- 非流式响应缓存。

### 2.2 原生代理模式

原生代理模式面向供应商协议差异较大、业务方希望直接使用供应商原生能力的场景。

典型接口建议：

```http
POST /proxy/{provider}/{native_path}
Authorization: Bearer <internal-api-key>
Content-Type: application/json
```

示例：

```http
POST /proxy/gemini/v1beta/models/gemini-1.5-pro:generateContent
```

网关在该模式下负责：

- 校验内部 API Key。
- 判断调用方是否有权限访问该 provider 或 native API。
- 将请求转发到供应商原生 endpoint。
- 注入供应商鉴权信息，例如 API Key、Bearer Token 或自定义 header。
- 透传请求 method、query、body 和关键 headers。
- 透传供应商响应 body、status code、content type 和流式数据。
- 记录 request id、调用方、provider、native path、状态码、耗时、错误信息。
- 尽可能解析供应商返回的 usage 信息。
- 无法解析 usage 时记录原始响应状态，并标记 usage 统计为 `unknown` 或 `estimated`。

网关在该模式下不负责：

- 不强制转换为 OpenAI 响应格式。
- 不修改 prompt 或 completion 结构。
- 不保证跨供应商 fallback。
- 不屏蔽供应商原生错误结构，除非出于安全原因需要隐藏敏感信息。

## 3. Provider Adapter 分层调整

V2 中的 Provider Adapter 需要扩展为两类能力接口。

### 3.1 标准模型调用 Adapter

用于统一协议模式：

```python
class ChatProviderAdapter:
    provider_type: str

    async def chat_completion(self, request: GatewayChatRequest) -> GatewayChatResponse:
        ...

    async def stream_chat_completion(self, request: GatewayChatRequest) -> AsyncIterator[GatewayChatChunk]:
        ...
```

职责：

- 协议转换。
- 统一响应结构。
- 统一错误映射。
- 统一 usage 解析。
- 支持模型路由、fallback、标准化治理能力。

### 3.2 原生代理 Adapter

用于非 OpenAI 兼容协议代理：

```python
class NativeProxyAdapter:
    provider_type: str

    async def forward(self, request: NativeProxyRequest) -> NativeProxyResponse:
        ...

    async def stream_forward(self, request: NativeProxyRequest) -> AsyncIterator[bytes]:
        ...

    async def parse_usage(self, response: NativeProxyUsageSource) -> NativeUsageResult:
        ...
```

职责：

- 组装供应商原生 URL。
- 注入供应商鉴权。
- 控制允许转发的 header。
- 处理超时、连接错误和响应透传。
- 尝试从响应 body、headers 或流式结束事件中提取 usage。
- 对无法解析的 usage 做明确标记。

## 4. Gemini 支持方式

Gemini 第一阶段建议按原生代理模式接入，而不是强行映射为 OpenAI 格式。

第一阶段已确认支持 Gemini 系列原生 API，采用 `/proxy/{provider}/{native_path}` 方式转发。实现边界如下：

- `generateContent`
- `streamGenerateContent`
- Gemini 原生 GET API，例如模型列表和模型详情
- 其他 Gemini 原生 POST API，可通过 path 白名单逐步开放

Gemini 原生代理要解决的问题：

- API Key 注入。
- URL path 与 query 透传。
- JSON request body 透传。
- 普通响应和流式响应透传。
- 从 Gemini 原生 usage metadata 中提取 token 用量。
- 对 Gemini 原生错误结构做日志记录。

如果后续业务希望通过 `/v1/chat/completions` 调用 Gemini，可以再单独实现 Gemini 的标准模型调用 adapter，将 OpenAI 风格 messages 转换为 Gemini contents。

## 5. API 范围 V3

### 5.1 业务统一接口

保留 V2 中的接口：

- `POST /v1/chat/completions`

用途：

- OpenAI 兼容协议。
- 网关统一模型路由。
- 统一响应格式。

### 5.2 供应商原生代理接口

新增：

- `GET /proxy/{provider}/{native_path:path}`
- `POST /proxy/{provider}/{native_path:path}`

第一阶段只支持 `GET` 和 `POST`。`PUT`、`PATCH`、`DELETE` 等方法暂不开放，后续按供应商和业务场景评估。

已确认增加以下保护：

- 每个 provider 配置允许代理的 path 白名单。
- 默认不转发敏感 header。
- 默认不允许请求任意外部 URL，只能转发到已配置 provider 的 base URL。
- 对 request body 大小做限制。
- 对流式连接设置最大持续时间。

## 6. 数据模型补充

### 6.1 `providers` 补充字段

在 V2 基础上增加：

- `protocol_modes`
  - 示例：`["openai_compatible"]`、`["native_proxy"]`、`["openai_compatible", "native_proxy"]`
- `auth_type`
  - 示例：`api_key_header`、`api_key_query`、`bearer_token`、`custom`
- `auth_config`
  - 鉴权注入配置。第一阶段供应商密钥不要求加密存储。
- `allowed_paths`
  - 原生代理 path 白名单。
- `blocked_headers`
  - 不允许转发的 header。
- `usage_parser_type`
  - 示例：`openai`、`gemini`、`anthropic`、`none`、`custom`
- `health_status`
  - 供应商健康状态，例如 `healthy`、`degraded`、`unhealthy`。
- `failure_threshold`
  - 触发故障转移或熔断的失败阈值。
- `cooldown_seconds`
  - 故障后恢复探测前的冷却时间。

### 6.2 `usage_logs` 补充字段

在 V2 基础上增加：

- `call_mode`
  - `unified_chat` 或 `native_proxy`
- `native_method`
- `native_path`
- `native_status_code`
- `usage_status`
  - `parsed`、`estimated`、`unknown`、`failed`
- `raw_usage`
  - JSON，保存供应商返回的 usage metadata，避免丢失细节。
- `prompt_content`
  - 统一协议模式下保存 prompt 或 messages 内容。
- `completion_content`
  - 统一协议模式下保存 completion 内容。
- `raw_request_body`
  - 原生代理模式下保存请求 body。
- `raw_response_body`
  - 原生代理模式下保存响应 body。流式响应可保存聚合后的文本或最终摘要，具体格式在实现时统一。

### 6.3 可选新增 `provider_native_routes`

如果原生代理规则较复杂，可新增独立表：

- `id`
- `provider_id`
- `name`
- `method`
- `path_pattern`
- `enabled`
- `timeout_ms`
- `max_body_bytes`
- `streaming`
- `created_at`
- `updated_at`

第一阶段如果规则简单，可以先放在 `providers.config` 或 `providers.allowed_paths` 中。

### 6.4 `route_rules` 补充字段

在 V2 基础上增加：

- `fallback_model_ids`
  - 备用模型列表，按顺序尝试。
- `failover_enabled`
  - 是否启用自动故障转移。
- `failover_on_status_codes`
  - 触发故障转移的 HTTP 状态码，例如 `429`、`500`、`502`、`503`、`504`。
- `failover_on_error_types`
  - 触发故障转移的错误类型，例如 timeout、connection_error、rate_limit、provider_error。
- `max_failover_attempts`
  - 单次请求最多故障转移次数。
- `cache_enabled`
  - 是否启用缓存。
- `cache_ttl_seconds`
  - 缓存有效期。
- `cache_scope`
  - 缓存维度，例如 client、model_alias、request_hash。

### 6.5 可选新增 `cache_entries`

如果需要持久化缓存元数据，可新增缓存记录表。第一阶段也可以仅使用 Redis 存储缓存内容。

- `id`
- `cache_key`
- `client_id`
- `model_alias`
- `request_hash`
- `response_body`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `expires_at`
- `created_at`

## 7. 后端目录结构补充

在 V2 目录结构基础上建议增加：

```text
backend/
  app/
    api/
      v1/
        proxy.py
    providers/
      base.py
      registry.py
      openai_compatible.py
      native_base.py
      gemini_native.py
    schemas/
      proxy.py
    services/
      native_proxy_service.py
      cache_service.py
      failover_service.py
    usage/
      parsers/
        base.py
        openai.py
        gemini.py
```

模块职责：

- `proxy.py`：接收原生代理请求。
- `native_proxy_service.py`：处理 provider 查找、权限、限流、转发、日志。
- `native_base.py`：定义原生代理 adapter 抽象。
- `gemini_native.py`：实现 Gemini 原生代理规则和 usage 解析。
- `cache_service.py`：处理缓存 key 生成、读取、写入、命中记录。
- `failover_service.py`：处理故障判断、备用模型选择和故障转移记录。
- `usage/parsers`：按供应商解析 usage。

## 8. 缓存与自动故障转移

### 8.1 缓存能力

MVP 需要实现缓存能力，第一阶段建议限定为非流式请求缓存。

缓存策略：

- 默认只缓存 `stream=false` 的统一协议调用。
- 原生代理模式默认不缓存，后续可按 provider path 单独开启。
- cache key 基于 client、model alias、messages、temperature、top_p、max_tokens、tools 等影响输出的参数生成。
- 缓存内容存储在 Redis。
- 缓存 TTL 可按 route rule 或 model alias 配置。
- 缓存命中需要写入 usage log，标记 `cache_hit=true`。
- 缓存命中时不再请求供应商，token 用量可记录为 `0`，同时保留原缓存响应的 token 元数据用于统计分析。

暂不实现：

- 语义缓存。
- 流式响应缓存。
- 跨租户或跨 client 共享缓存。
- 复杂缓存失效策略。

### 8.2 自动故障转移

MVP 需要实现自动故障转移核心能力，第一阶段优先用于统一协议模式。

触发条件：

- 供应商请求超时。
- 网络连接异常。
- 供应商返回 `429`、`500`、`502`、`503`、`504`。
- adapter 标记为可重试的 provider error。

执行策略：

- 按 route rule 中的 `fallback_model_ids` 顺序尝试备用模型。
- 单次请求最多尝试 `max_failover_attempts` 次。
- 故障转移需要保留同一个 request id，并记录每一次 provider/model 尝试。
- 如果全部失败，返回最后一次错误或网关统一错误。
- 原生代理模式第一阶段不做跨供应商自动故障转移。

观测要求：

- usage log 记录是否发生故障转移。
- 记录主模型失败原因。
- 记录最终命中的 provider 和 model。
- 后台日志查询可筛选 failover 请求。

## 9. 观测与用量统计调整

原生代理模式下，用量统计需要接受“不完全统一”的现实。

建议记录三层信息：

- 标准 usage 字段
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
- 原生 usage 字段
  - `raw_usage`
  - 保存供应商原始 usage metadata。
- usage 可信状态
  - `parsed`：成功解析为标准字段。
  - `estimated`：通过规则估算。
  - `unknown`：供应商未返回或暂不支持解析。
  - `failed`：解析失败。

这样即使某些供应商的 usage 格式不一致，也不会阻塞调用记录和后续治理。

缓存与故障转移需要补充记录：

- `cache_hit`
- `cache_key`
- `failover_triggered`
- `failover_attempts`
- `initial_provider_id`
- `initial_model_id`
- `final_provider_id`
- `final_model_id`
- `failure_reason`

已确认的日志策略：

- prompt 和 completion 需要入库。
- 原生代理请求和响应内容需要支持入库。
- usage 日志永久保存，第一阶段不设置自动清理周期。
- 对无法解析 usage 的调用，允许入库为 `unknown`。

## 10. 第一阶段范围调整

第一阶段 MVP 建议调整为：

- OpenAI 兼容聊天接口。
- OpenAI-compatible provider adapter。
- Gemini 原生代理 adapter。
- 内部 API Key 鉴权。
- Provider 访问权限控制。
- 模型别名和基础 fallback，仅用于统一协议模式。
- Redis 限流。
- Redis 响应缓存。
- 自动故障转移核心能力。
- PostgreSQL usage log。
- 原生代理调用日志与 usage 解析。
- 管理后台可配置 provider、model、route rule，以及 native proxy 基础配置。
- Provider 连通性测试。
- 原生代理独立限流策略。
- 前端和后端放在同一个 monorepo。

暂不要求：

- 将 Gemini 强行纳入 `/v1/chat/completions`。
- 原生代理跨供应商 fallback。
- 原生代理跨供应商自动故障转移。
- 对所有供应商 usage 做完全统一。
- 语义缓存。
- 流式响应缓存。
- 多租户。
- embeddings。
- Docker Compose。
- 供应商密钥加密存储。

## 11. 管理后台补充

Provider 管理页面需要支持配置：

- 协议模式：OpenAI compatible、Native proxy。
- Base URL。
- 鉴权方式。
- 允许代理的 path。
- Usage parser 类型。
- 超时配置。
- 是否允许流式响应。
- 连通性测试。
- 健康状态。
- 故障阈值和冷却时间。

Routes 页面需要支持配置：

- fallback 模型顺序。
- 是否启用自动故障转移。
- 故障转移触发条件。
- 最大故障转移次数。
- 是否启用缓存。
- 缓存 TTL。

Usage Logs 页面需要展示：

- 调用模式。
- 原生 path。
- usage 解析状态。
- 原始供应商状态码。
- request id。
- prompt 和 completion。
- 原生代理请求和响应内容。
- 缓存命中状态。
- 是否发生自动故障转移。
- 故障转移尝试次数和最终命中模型。

## 12. 已确认问题

本轮已确认以下事项：

1. Gemini 第一阶段支持 Gemini 系列原生 API，通过 path 白名单逐步开放。
2. 原生代理入口采用 `/proxy/{provider}/{native_path}`。
3. 允许透传供应商原生错误响应给业务方。
4. 原生代理需要 path 白名单。
5. Gemini 鉴权第一阶段使用 API Key。
6. 原生代理第一阶段只支持 `GET` 和 `POST`。
7. 第一阶段支持原生流式响应，`streamGenerateContent` 纳入 MVP。
8. 对无法解析 usage 的调用，允许入库为 `unknown`。
9. 后台需要支持 provider 连通性测试。
10. 原生代理请求需要配置独立限流策略。
11. 第一阶段不实现多租户。
12. prompt 和 completion 需要入库。
13. usage 日志永久保存。
14. 供应商密钥第一阶段不需要加密存储。
15. 不需要 Docker Compose。
16. 前后端放在同一个 monorepo。
17. 第一阶段不支持 embeddings。
18. MVP 需要实现缓存能力。
19. MVP 需要实现自动故障转移核心能力。

## 13. 决策记录

| 日期 | 决策项 | 结论 | 备注 |
| --- | --- | --- | --- |
| 2026-07-04 | 文档版本策略 | 保留旧文档，默认按版本演进；本轮按要求直接更新 V3 | 不新建 V4 |
| 2026-07-04 | OpenAI 兼容供应商 | 支持统一协议模式 | 延续 V2 |
| 2026-07-04 | 非 OpenAI 兼容供应商 | 支持原生协议代理 | 例如 Gemini |
| 2026-07-04 | 原生代理职责 | API 转发、鉴权、限流、日志、用量监控 | 不强制统一响应格式 |
| 2026-07-04 | Gemini 原生代理范围 | 第一阶段支持 Gemini 系列原生 API | 通过 path 白名单控制 |
| 2026-07-04 | 原生代理入口 | `/proxy/{provider}/{native_path}` | 已确认 |
| 2026-07-04 | 原生代理方法 | 第一阶段只支持 GET、POST | 支持原生流式响应 |
| 2026-07-04 | Gemini 鉴权 | API Key | 第一阶段不使用 OAuth |
| 2026-07-04 | 日志内容 | prompt、completion、原生请求和响应内容入库 | usage 日志永久保存 |
| 2026-07-04 | 多租户 | 第一阶段不实现 | 后续可扩展 |
| 2026-07-04 | 密钥存储 | 供应商密钥第一阶段不加密存储 | 内部 API Key 仍建议只保存 hash |
| 2026-07-04 | 部署与仓库 | 不需要 Docker Compose，前后端同 monorepo | 已确认 |
| 2026-07-04 | Embeddings | 第一阶段不支持 | 后续扩展 |
| 2026-07-04 | 缓存 | MVP 需要实现缓存能力 | 第一阶段优先非流式 Redis 响应缓存 |
| 2026-07-04 | 自动故障转移 | MVP 需要实现核心能力 | 第一阶段用于统一协议模式 |
