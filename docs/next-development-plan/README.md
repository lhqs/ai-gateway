# LHQS AI Gateway 下一阶段增强方案

> 生成日期：2026-07-07  
> 适用范围：当前仓库 `backend/`、`frontend/`、`docs/` 的下一阶段功能增强与优化  
> 推荐角色：AI Gateway 产品技术负责人（Platform Product Tech Lead）

## 1. 推荐角色

最适合牵头解决当前问题的角色是：**AI Gateway 产品技术负责人（Platform Product Tech Lead）**。

原因：

- 当前项目已经不是单点功能开发阶段，而是从 V3 MVP 进入生产可运营阶段。
- 后续工作同时涉及后端可靠性、计费准确性、安全治理、前端管理体验、测试和部署流程。
- 需要有人持续做优先级取舍：哪些能力先保证线上稳定，哪些体验后续迭代，哪些旧 TODO 已被实现或需要降级。

该角色的主要职责：

- 定义生产化路线图和验收标准。
- 将后端、前端、数据库、测试和文档任务拆成可执行迭代。
- 确保不破坏现有约束：数据库变更继续使用 SQL 脚本，不使用 Alembic，不增加外键。
- 对关键能力建立可度量指标：可用性、失败率、故障转移成功率、usage 解析率、计费覆盖率、管理操作可审计率。

## 2. 当前项目判断

当前项目已经具备一个可演示、可初步使用的 AI Gateway MVP：

- 后端：FastAPI、SQLAlchemy async、PostgreSQL、Redis、OpenAI-compatible chat、Claude chat、Gemini native proxy。
- 管理 API：clients、api keys、providers、models、model aliases、route rules、usage logs、dashboard、workbench。
- 前端：React + Vite + Tailwind 管理台，已有 Dashboard、Usage、Models、Providers、Routes、Clients、Pricing、Workbench。
- 治理能力：API key 鉴权、访问策略、限流、非流式缓存、failover、usage log、定价计算。
- 管理员认证：注册、登录、刷新 token、登出、改密、session 失效、基础审计日志。
- 测试：已有后端单元测试和 SQLite ASGI 集成测试。

当前真正值得继续投入的方向不是继续补 MVP，而是进入 **生产可运营版本**：

1. 让路由和 provider 健康状态真正参与运行时决策。
2. 提高 usage/计费准确率，尤其是流式和原生代理。
3. 完善安全治理：API key 生命周期、敏感数据存储、管理操作审计。
4. 提升管理台配置效率，减少 JSON 手填和误配置。
5. 建立部署、初始化、回归测试和运维排障闭环。

## 3. 最高优先级结论

下一阶段建议按以下顺序推进：

1. **可靠性治理**：provider 健康检查、熔断、冷却、路由跳过不健康 provider。
2. **Usage 与计费闭环**：流式 usage、native usage、按时间范围聚合、成本看板和导出。
3. **API Key 与安全治理**：禁用/轮换/过期/限流/访问策略验证，减少完整 key 长期明文存储风险。
4. **管理台生产体验**：结构化 route fallback、provider health 结果、usage 分析页、审计日志页。
5. **工程化交付**：SQL 初始化校验、PostgreSQL 集成测试、CI、lint、部署样例。

## 4. 本目录文件

- [execution-plan.md](execution-plan.md)：分阶段落地执行方案、任务拆解、验收标准。
- [backlog.md](backlog.md)：按 P0/P1/P2 排列的功能 backlog。

