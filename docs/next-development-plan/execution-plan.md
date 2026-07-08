# 落地执行方案

> 角色视角：AI Gateway 产品技术负责人（Platform Product Tech Lead）  
> 目标：将当前 V3 MVP 推进到可生产运营、可观测、可治理、可持续迭代的版本。

## 1. 执行原则

- 先稳定运行时，再优化管理体验。
- 先保证 usage 和计费数据可信，再扩展报表和分析。
- 数据库继续使用编号 SQL 脚本，不使用 Alembic，不增加数据库外键。
- 每个阶段都必须包含后端测试；涉及前端可见变更时必须跑 `npm run build`。
- 所有新增运行时策略必须能被 usage log、provider health 或 audit log 追踪。

## 2. 阶段一：运行时可靠性治理

建议周期：1 周  
目标：让 provider 健康状态和故障信息真正影响路由，而不只是展示字段。

### 后端任务

1. 新增 Provider Health Service。
   - 统一处理连通性测试、失败记录、成功恢复、冷却过期。
   - 支持不同 provider 的 health path：
     - `openai_compatible`：优先 `/v1/models` 或 `config.health_path`。
     - `gemini`：优先 `v1beta/models` 或 `config.health_path`。
     - `claude`：优先轻量接口或配置化 health path；没有合适接口时记录为 `probe_unsupported`。

2. 让 `failure_threshold` 和 `cooldown_seconds` 参与运行时。
   - provider 调用失败时累计连续失败次数。
   - 达到阈值后将 provider 标记为 `unhealthy` 或 `degraded`。
   - 冷却期内 `RoutingService` 不选择该 provider，fallback 中也跳过。
   - 冷却过期后允许一次探测调用，成功则恢复 `healthy`。

3. 增加 provider 健康状态存储。
   - 推荐新增 SQL：`008_provider_health.sql`。
   - 可选字段：`failure_count`、`last_success_at`、`last_failure_at`、`cooldown_until`、`last_health_error`、`last_health_status_code`。
   - 也可以先复用 `providers.config` 存元数据，但长期建议字段化，便于查询。

4. 扩展 provider test API。
   - 当前 `/admin/providers/{id}/test` 只请求 base URL 根路径，生产价值不足。
   - 返回：`status`、`status_code`、`latency_ms`、`probe_url`、`error_summary`、`checked_at`。

### 前端任务

1. Provider 列表展示健康细节。
   - health 状态、最近检查时间、连续失败次数、冷却剩余时间。
2. Test 按钮结果从简单 notice 改为行内状态或 modal。
3. Provider 编辑表单增加 `health_path`、`failure_threshold`、`cooldown_seconds`。

### 测试任务

- provider test 对 OpenAI/Gemini health path 的单元测试。
- provider 连续失败达到阈值后 route 跳过的集成测试。
- cooldown 过期后恢复探测的测试。
- fallback 中 primary unhealthy 时命中 fallback 的测试。

### 验收标准

- 主 provider 失败达到阈值后，同一 alias 自动走 fallback。
- 冷却期内不会继续把普通业务请求打到 unhealthy provider。
- 管理台可以看到健康检查结果和错误摘要。
- `uv run pytest` 通过。

## 3. 阶段二：Usage 与计费可信度提升

建议周期：1 周  
目标：让用量、成本、缓存、failover 数据可用于运营分析和客户对账。

### 后端任务

1. 完善 Usage 查询。
   - 增加 `created_from`、`created_to`、`model_id`、`api_key_id` 筛选。
   - 当前 usage log 没有 `api_key_id`，建议新增字段，便于 key 级治理和对账。
   - 增加聚合接口：按 client、provider、model_alias、day 汇总请求数、失败率、token、成本。

2. 完善流式 usage。
   - OpenAI-compatible 已具备解析 usage chunk 的基础，需补测试覆盖。
   - 对不返回 usage 的供应商标记 `unknown`，同时记录供应商和模型维度的 unknown 比例。
   - 为 native proxy 建立可配置 parser 路由，避免只依赖 Gemini。

3. 成本计算增强。
   - 支持 cached input、reasoning output、request unit 的汇总展示。
   - 对 pricing_status 为 `not_calculated` 或 `missing_price` 的日志增加后台筛选和修复入口。

4. Usage 数据保留策略。
   - 增加配置项：日志保留天数、是否保存 prompt/completion/raw body。
   - 对敏感内容保存增加开关和最大长度限制。

### 前端任务

1. Usage 页面增加时间范围、client、provider、model、api key 筛选。
2. Dashboard 增加 24h/7d 成本、失败率、cache hit rate、failover rate、usage parsed rate。
3. Pricing 页面展示缺失定价模型列表，并提供快速创建价格配置入口。
4. Usage 支持 CSV 导出。

### 测试任务

- usage list 时间范围和多字段筛选测试。
- 聚合接口测试。
- stream usage final chunk 解析测试。
- missing price / parsed price 的成本计算测试。

### 验收标准

- 管理台能回答：哪个 client 最贵、哪个 provider 失败率最高、哪些模型没有价格。
- 流式请求在供应商返回 usage 时能落库 token 和成本。
- usage 聚合接口和明细接口分页、筛选稳定。

## 4. 阶段三：API Key 与安全治理

建议周期：1 周  
目标：让网关具备生产环境下的 key 生命周期管理和基础安全审计。

### 后端任务

1. API key 生命周期。
   - 支持 rotate：生成新 key，旧 key 可立即禁用或设置宽限期。
   - 支持 revoke：状态置为 disabled，并记录 audit log。
   - 支持 last_used_at 按请求更新；当前 schema 已有字段，需确认所有路径均更新。

2. Key 级限流和访问策略。
   - 在 `api_keys.access_config` 中支持 `rate_limit_per_minute`。
   - 当前 native provider 有 provider 级限流，建议统一为 client/key/provider 三层取最严格值。
   - 访问策略增加后台校验预览：输入 model/native path，返回允许或拒绝原因。

3. 完整 key 存储策略。
   - 当前 `api_keys.key_value` 保存完整 key，便于后台展示，但生产上风险较高。
   - 建议改为默认只在创建时返回完整 key。
   - 若必须保留，增加环境变量 `STORE_API_KEY_VALUE=false`，默认生产关闭。

4. 管理审计日志。
   - 已有 `admin_audit_logs` 和认证相关审计，下一步覆盖管理写操作：
     - clients、api keys、providers、models、aliases、routes、pricing。
   - 审计 detail 中避免保存完整密钥。

### 前端任务

1. API key 页面增加 rotate/revoke 操作。
2. 显示 last used、expires、状态、访问策略摘要。
3. 增加访问策略测试小工具。
4. 增加 Audit Logs 页面。

### 测试任务

- disabled key 不可调用。
- expired key 不可调用。
- rotated key 新旧状态符合预期。
- key 级限流优先级测试。
- 管理写操作产生 audit log。

### 验收标准

- 生产环境可关闭完整 key 持久化。
- 每次关键配置变更可追踪到管理员、动作、资源和时间。
- API key 可安全轮换和撤销。

## 5. 阶段四：管理台配置体验优化

建议周期：1 周  
目标：减少误配置，让管理员能用 UI 完成常见配置闭环。

### 前端任务

1. Routes 页面优化 fallback 编辑。
   - 将 `Fallback Model IDs` 从文本框升级为多选列表。
   - 支持排序，顺序即 fallback 优先级。
   - 显示 provider、模型状态、health 状态，避免选到不可用模型。

2. Provider 表单继续结构化。
   - allowed paths 使用 tag input。
   - blocked headers 使用 tag input。
   - config 保留 JSON 高级模式，但常用字段用表单。

3. Workbench 增强。
   - 支持 stream 测试。
   - 支持 native proxy 测试。
   - 展示最终路由、failover、cache、usage、cost。

4. Pricing 页面增强。
   - 批量导入价格。
   - 按 provider/model 搜索。
   - 对已过期价格和未来生效价格做清晰状态展示。

### 后端任务

1. 增加 route validate API。
   - 输入 alias/rule，返回 primary/fallback 是否可用、是否跨 provider、是否存在重复。
2. 增加 provider config schema API。
   - 前端可按 provider_type 渲染常用字段。

### 测试任务

- 前端 `npm run build`。
- route validate API 单元测试。
- Workbench stream/native 测试接口后端覆盖。

### 验收标准

- 常规 provider/model/route/client/key/pricing 配置不需要手写 JSON。
- Workbench 能复现绝大多数线上调用问题。
- 前端 build 通过。

## 6. 阶段五：工程化与部署闭环

建议周期：3 到 5 天  
目标：降低本地启动、部署、升级和回归验证成本。

### 后端与脚本

1. SQL 初始化校验。
   - 新增脚本：顺序执行 `backend/app/db/sql/*.sql`。
   - 在空 PostgreSQL 库执行后，校验关键表和列存在。

2. PostgreSQL 集成测试。
   - 保留 SQLite ASGI 测试。
   - 增加可选 PostgreSQL 测试 profile，覆盖 SQL 脚本真实初始化。

3. 本地与部署脚本。
   - `scripts/apply-sql.sh`
   - `scripts/dev-backend.sh`
   - `scripts/dev-frontend.sh`
   - 可选 `docker-compose.yml`：PostgreSQL + Redis，仅用于本地依赖。

4. 质量工具。
   - 后端：Ruff lint/format。
   - 前端：ESLint。
   - CI：pytest + frontend build + SQL dry run。

### 文档

1. README 增加完整初始化流程。
2. 增加生产环境变量样例。
3. 增加常见 provider 配置样例。
4. 增加排障手册：
   - provider unhealthy。
   - failover 未触发。
   - usage unknown。
   - pricing missing。
   - CORS/login 问题。

### 验收标准

- 新开发者可以按 README 在本地启动完整环境。
- CI 能阻断破坏测试、构建或 SQL 初始化的变更。
- 生产升级有明确 SQL 执行顺序和回滚说明。

## 7. 推荐迭代顺序

1. 第 1 周：阶段一，Provider health + 熔断 + route 跳过。
2. 第 2 周：阶段二，Usage/计费聚合 + stream usage 测试补齐。
3. 第 3 周：阶段三，API key 生命周期 + audit log 覆盖。
4. 第 4 周：阶段四，管理台配置体验和 Workbench 增强。
5. 第 5 周：阶段五，CI、SQL 校验、部署文档和排障手册。

## 8. 风险和取舍

- Provider health 不应一次性做复杂调度系统；先实现连续失败、冷却、恢复探测即可。
- Usage raw body 保存有隐私风险，必须配置化，默认生产环境建议关闭或截断。
- API key 完整值长期保存有安全风险，建议尽快改为只在创建时展示。
- 前端体验优化不要先于运行时可靠性，否则会掩盖核心生产问题。
- PostgreSQL 集成测试可能增加 CI 成本，可以作为可选 profile 先接入。

