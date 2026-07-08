# 下一阶段功能 Backlog

> 优先级定义：  
> P0：生产化前必须完成，直接影响稳定性、安全或对账可信度。  
> P1：重要增强，显著提升运维效率和管理体验。  
> P2：质量、体验和长期维护优化。

## P0：生产化必做

### P0-1 Provider 健康检查准确化

现状：

- `/admin/providers/{id}/test` 当前主要请求 provider base URL 根路径。
- 对 OpenAI-compatible、Gemini、Claude 都不够准确。

目标：

- 按 provider_type 或 `provider.config.health_path` 生成真实探测路径。
- 记录 `latency_ms`、`status_code`、`probe_url`、`error_summary`。

验收：

- 管理台 Test 能返回可解释的健康检查结果。
- 测试覆盖 OpenAI-compatible 和 Gemini。

### P0-2 Provider 熔断与冷却

现状：

- `providers.failure_threshold`、`cooldown_seconds` 字段已存在，但运行时治理不足。

目标：

- 连续失败达到阈值后标记 provider unhealthy/degraded。
- cooldown 内普通请求跳过该 provider。
- cooldown 后允许恢复探测。

验收：

- primary unhealthy 时路由命中 fallback。
- fallback 全部不可用时返回可解释错误并记录 usage log。

### P0-3 API Key 生命周期治理

现状：

- key 有 hash、status、expires、last_used_at 字段。
- 仍需要完善 rotate、revoke、禁用后的行为和审计。

目标：

- 支持 key rotate/revoke。
- 所有鉴权路径更新 last_used_at。
- 管理操作写 audit log。
- 支持生产关闭 `key_value` 完整 key 持久化。

验收：

- disabled/expired key 无法调用。
- rotate 后新 key 可用，旧 key 按策略禁用或宽限。
- audit log 不泄露完整 key。

### P0-4 Usage 与计费聚合

现状：

- usage log 明细较完整，但聚合分析能力不足。

目标：

- 增加按时间、client、provider、model_alias 的聚合接口。
- 增加时间范围筛选。
- 增加 usage parsed rate、missing price 统计。

验收：

- Dashboard 可展示成本、失败率、cache hit rate、failover rate、usage parsed rate。
- Usage 页面可按时间范围和关键维度筛选。

### P0-5 SQL 初始化真实校验

现状：

- 有多份编号 SQL 脚本。
- 测试主要依赖 SQLAlchemy metadata + SQLite，无法完全证明 PostgreSQL SQL 脚本可初始化。

目标：

- 增加脚本顺序执行所有 SQL。
- 增加可选 PostgreSQL 集成测试或 CI job。

验收：

- 空 PostgreSQL 库执行 SQL 后，应用可启动，核心接口可跑通。

## P1：重要增强

### P1-1 流式 Usage 测试补齐

目标：

- 对 OpenAI-compatible `stream_options.include_usage` final chunk 增加测试。
- 对未知 usage 的流式请求记录 unknown，并可在后台统计。

验收：

- 供应商返回 usage chunk 时，prompt/completion/total tokens 正确落库。

### P1-2 Native Proxy Header 策略配置化

目标：

- provider.config 支持 `forward_headers_allowlist`。
- 默认只转发低风险 header。
- blocked headers 继续作为兜底。

验收：

- 敏感 header 不会透传到 provider。
- allowlist 生效且有测试。

### P1-3 管理写操作审计覆盖

目标：

- clients、api keys、providers、models、aliases、routes、pricing 的 create/update/delete 写入 audit log。
- 增加 Audit Logs 页面。

验收：

- 任一关键配置变更都能查到管理员、动作、资源、时间。

### P1-4 Routes 结构化 Fallback 编辑

目标：

- 用多选 + 排序替代 `Fallback Model IDs` 文本输入。
- 展示模型所属 provider 和 health 状态。

验收：

- 管理员无需手写 ID 即可配置 fallback 顺序。

### P1-5 Workbench 扩展

目标：

- 支持 stream chat 测试。
- 支持 native proxy 测试。
- 展示最终 provider/model、cache、failover、usage、cost。

验收：

- Workbench 能用于复现统一协议和 native proxy 的主要线上问题。

### P1-6 Usage CSV 导出

目标：

- 按当前筛选条件导出 CSV。
- 控制单次导出上限。

验收：

- 财务或运营可以导出指定时间范围的用量明细。

## P2：质量与长期维护

### P2-1 Provider/Route 配置 Schema 化

目标：

- 后端提供 provider_type 对应的配置 schema。
- 前端按 schema 渲染常用字段。
- JSON 高级模式保留。

验收：

- 新增 provider 类型时，前端无需大量硬编码。

### P2-2 本地开发脚本

目标：

- 增加 `scripts/apply-sql.sh`、`scripts/dev-backend.sh`、`scripts/dev-frontend.sh`。
- 可选增加本地依赖 `docker-compose.yml`。

验收：

- 新开发者可在 15 分钟内启动完整本地环境。

### P2-3 CI 与质量工具

目标：

- 后端接入 Ruff lint/format。
- 前端接入 ESLint。
- CI 执行 pytest、frontend build、SQL 初始化校验。

验收：

- PR 不能在测试或构建失败时合并。

### P2-4 数据保留与隐私策略

目标：

- prompt/completion/raw body 是否保存由配置控制。
- 增加最大保存长度。
- 增加 usage logs 清理脚本。

验收：

- 生产环境可降低敏感内容落库风险。

### P2-5 文档与排障手册

目标：

- 更新 README 初始化流程。
- 增加 provider 配置样例。
- 增加常见问题排障手册。

验收：

- 常见问题能按文档完成自助定位。

