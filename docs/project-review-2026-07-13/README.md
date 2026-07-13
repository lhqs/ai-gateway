# LHQS AI Gateway 项目审查与增强建议

> 审查日期：2026-07-13  
> 审查范围：`backend/`、`frontend/`、SQL 脚本、测试、依赖、运维文档与现有规划  
> 审查方式：静态代码核查 + 后端测试 + 前端构建/类型检查 + 依赖与安全扫描

## 1. 结论

项目已经超出早期 MVP 阶段，核心网关能力较完整：统一 Chat API、Gemini Native Proxy、
多 Provider 路由和故障转移、健康状态、缓存、限流、Usage/计费、管理员认证、审计日志和管理台
均已落地。当前后端 57 个测试全部通过，前端构建和 TypeScript 类型检查通过，前端依赖扫描未发现
已知漏洞。

下一阶段不应继续照搬 `docs/next-development-plan/backlog.md`。该 backlog 中 Provider 健康检查、
熔断冷却、API Key 轮换/撤销、Usage 聚合、管理写操作审计、Routes 结构化 fallback、Workbench
流式测试、Provider Config Schema 等项目已经全部或大部分实现。

当前最需要处理的是生产安全和行为正确性，而不是继续扩展页面数量：

1. **Provider 密钥会通过管理 API 返回，且实际以明文存储。**
2. **缓存哈希没有覆盖所有影响模型输出的参数，存在错误复用响应的风险。**
3. **Usage 中的 prompt、completion 和原生请求/响应默认落库，缺少保留、截断和清理策略。**
4. **声明了配置但运行时未生效，包括 Native Header Allowlist、`cache_scope` 和
   `admin_registration_mode`。**
5. **没有 CI、PostgreSQL SQL 初始化测试、正式 lint 门禁和前端自动化测试。**

建议先完成 P0 修复，再进入报表、更多 Provider 和高级路由策略等功能增强。

## 2. 当前能力基线

| 领域 | 当前状态 | 判断 |
| --- | --- | --- |
| OpenAI-compatible Chat | 非流式、流式、额外参数透传 | 已实现 |
| Provider 适配 | OpenAI-compatible、Claude Chat、Gemini Chat/Native | 已实现 |
| 路由与故障转移 | Alias、primary/fallback、流式首 token 前切换 | 已实现 |
| Provider 健康治理 | 探测、失败累计、冷却、请求跳过 | 已实现，恢复策略可增强 |
| API Key | hash、过期、禁用、轮换、撤销、last used | 已实现 |
| 访问策略和限流 | Client/Key/Provider 多层策略 | 已实现，Redis 故障策略待完善 |
| Usage 与计费 | 明细、多维筛选、聚合、流式 usage、定价状态 | 已实现 |
| 管理审计 | 认证事件和核心资源写操作 | 已实现 |
| 管理台 | Dashboard、Usage、Pricing、Routes、Workbench、Audit | 已实现 |
| 工程质量 | pytest、前端 build/typecheck 可通过 | 部分实现，缺 CI/lint/frontend tests |
| 生产数据治理 | 内容保存开关、清理、脱敏、密钥加密 | 明显不足 |

## 3. 与旧规划的差异

以下旧待办已经落地，不应继续作为新任务重复排期：

- Provider 健康探测结果和 health path。
- failure threshold、cooldown 和不健康 Provider 跳过。
- API Key rotate/revoke、过期检查和 last used 更新。
- Usage 时间范围/API Key/Provider/Model 等筛选和聚合接口。
- Dashboard 成本、错误率、缓存、failover、usage parsed rate 指标。
- 核心管理写操作审计和 Audit Logs 页面。
- Route fallback 下拉选择、排序和保存前校验。
- Provider Config Schema 和常用字段结构化编辑。
- Workbench 真流式测试和诊断元数据。
- Pricing CSV 模板/导入和生效状态筛选。

仍是“部分实现”的旧待办：

- `forward_headers_allowlist` 只有 Schema 和前端表单，Native Adapter 未使用它过滤 Header。
- Usage CSV 导出尚未落地。
- Workbench 尚未覆盖 Native Proxy 调试。
- SQL 初始化只有手工命令，没有自动校验或 PostgreSQL 集成测试。
- Ruff 仅有配置，没有依赖和门禁；前端没有 ESLint/测试脚本。
- Usage 数据保留与隐私策略尚未实现。

## 4. 推荐执行顺序

### 迭代 1：正确性与密钥安全（P0）

- 修正缓存哈希，加入完整规范化请求体、路由/Provider/Model 和缓存版本。
- Provider 密钥写入后不可通过 Read/List API 读回。
- 使用 KMS/应用层 AEAD 加密 Provider 密钥，并提供旧数据迁移脚本。
- 生产启动时拒绝默认 `JWT_SECRET_KEY` 和 `ADMIN_TOKEN`。

### 迭代 2：隐私、配置一致性与鉴权加固（P0/P1）

- 增加 Usage 内容保存开关、字段级脱敏、长度上限、保留天数和清理任务。
- 让 Header Allowlist、`cache_scope`、`admin_registration_mode` 真正生效，或删除无效配置。
- 增加登录/刷新限流、Refresh Token 原子轮换和首次管理员注册并发保护。

### 迭代 3：交付门禁与真实环境测试（P1）

- 建立 CI：Ruff、pytest、TypeScript、Vite build、前端测试、PostgreSQL SQL 初始化。
- 用 PostgreSQL + Redis 覆盖故障转移、限流、缓存和 SQL 升级路径。
- 修复当前 6 个 Ruff F401，并将 lint 纳入 `uv` dev dependencies。

### 迭代 4：产品增强（P1/P2）

- Usage CSV/异步导出、Native Workbench、访问策略模拟器。
- Provider 密钥轮换状态、缓存清理/统计、用量预算与告警。
- OpenTelemetry/Prometheus 指标、就绪/存活探针和告警闭环。

完整任务、证据和验收条件见 [backlog.md](backlog.md)，执行过的检查见
[verification.md](verification.md)。

