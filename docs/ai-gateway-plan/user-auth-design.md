# 管理后台用户注册登录设计

> 维护日期：2026-07-05
> 适用范围：LHQS AI Gateway 管理后台登录、管理 API 鉴权、用户与角色模型
> 现状问题：当前所有 `/admin/*` 接口只依赖单一共享 `ADMIN_TOKEN` Bearer 鉴权，无法区分操作者、无法撤销单个账号、无法做权限分级与审计。
> 数据库约束：继续使用 `backend/app/db/sql/` 顺序 SQL 脚本；不使用 Alembic；不新增数据库外键，关系由应用层与 repository 校验。

---

## 1. 设计目标

### 1.1 本期目标

1. 落地管理后台用户体系，支持注册、登录、退出、查看当前用户。
2. 替换 `/admin/*` 的共享 `ADMIN_TOKEN` 鉴权，改为用户会话 token 鉴权。
3. 保留 `ADMIN_TOKEN` 作为迁移期 bootstrap 能力，用于创建首个管理员或受保护的初始化注册。
4. 管理用户与网关调用方分层：管理后台用户负责配置和运营；`Client + ApiKey` 继续负责 `/v1/chat/completions` 与 `/proxy/*` 的调用鉴权。
5. 为 RBAC、用户管理、操作审计预留字段和接口边界。

### 1.2 非目标

1. 本期不把管理用户直接作为模型调用方身份，不替换现有 `Client + ApiKey` 访问策略。
2. 本期不做 OAuth、SSO、LDAP、飞书登录等企业 IdP 集成。
3. 本期不做细粒度到字段级的权限控制，先使用角色级权限。
4. 本期不引入数据库外键，不引入 Alembic。

---

## 2. 现状摸底

### 2.1 后端

当前鉴权路径：

- `backend/app/api/deps.py`
  - `require_admin()` 从 `Authorization` header 读取 Bearer token。
  - 调用 `verify_admin_token(get_settings().admin_token, authorization)`。
- `backend/app/core/security.py`
  - `verify_admin_token()` 使用 `hmac.compare_digest()` 比较请求 token 与环境变量 `ADMIN_TOKEN`。
- `backend/app/api/v1/admin/resources.py`
  - `router = APIRouter(dependencies=[Depends(require_admin)])`，所有资源管理接口共用同一个 token。
- `backend/app/api/v1/admin/workbench.py`
  - 同样依赖 `require_admin`。

当前普通网关调用鉴权：

- `/v1/chat/completions` 和 `/proxy/{provider}/{native_path}` 使用 `get_auth_context()`。
- `get_auth_context()` 基于 API Key 查出 `ApiKey + Client`。
- `clients.access_config` 与 `api_keys.access_config` 做调用权限策略。

结论：管理后台身份与网关调用身份已经在代码上分离，新用户体系应替换管理面 `require_admin`，不应影响调用面 API Key。

### 2.2 前端

当前登录页：

- `frontend/src/pages/LoginPage.tsx` 要求输入 Backend URL 和 Admin Token。
- `frontend/src/App.tsx` 登录时调用 `/admin/dashboard` 校验 token。
- token 存在 `localStorage.adminToken`。
- 所有管理 API 请求都附带 `Authorization: Bearer <adminToken>`。

结论：前端需要从“输入共享 token”改为“邮箱/用户名 + 密码登录”，并保存后端签发的访问 token。

---

## 3. 总体方案

### 3.1 身份面拆分

系统保留两套身份：

| 身份类型 | 用途 | 鉴权方式 | 主要接口 |
| --- | --- | --- | --- |
| 管理用户 `AdminUser` | 登录管理台、管理 provider/model/client/api key、查看 usage | 用户登录签发 access token | `/auth/*`, `/admin/*` |
| 调用方 `Client + ApiKey` | 调用统一 chat 或原生 proxy | API Key Bearer | `/v1/chat/completions`, `/proxy/*` |

管理用户可以创建和管理 `Client + ApiKey`，但请求模型时仍应使用对应 API Key，以继续复用现有访问策略、限流、计费、usage 归属逻辑。

### 3.2 推荐认证模型

采用短期 access token + 长期 refresh token：

- `access_token`
  - JWT，默认 30 分钟有效。
  - 前端在调用 `/admin/*` 时放入 `Authorization: Bearer <access_token>`。
  - 后端无状态校验签名、过期时间、用户状态、token 版本。
- `refresh_token`
  - 高熵随机字符串，只在服务端保存 hash。
  - 默认 14 天有效。
  - 用于换取新的 access token。
  - 支持单会话退出、全部设备退出、账号禁用时整体失效。

迁移期可先只实现 access token，但建议一次性建好 `admin_sessions` 表，否则退出、续期、撤销很快会补债。

### 3.3 Token 存储选择

第一期建议：

- access token 存在前端内存或 `localStorage.authAccessToken`。
- refresh token 存在 `localStorage.authRefreshToken`。
- 后端接口统一从 `Authorization` header 读取 access token。

后续增强：

- refresh token 改为 `HttpOnly + Secure + SameSite=Lax` Cookie。
- 增加 CSRF 保护。

当前前端已经使用 `localStorage.adminToken`，为了降低改造成本，第一期可沿用 localStorage，但必须缩短 access token 生命周期并支持 refresh token 撤销。

---

## 4. 数据库设计

新增脚本建议命名：

```text
backend/app/db/sql/007_admin_users.sql
```

### 4.1 admin_users

```sql
CREATE TABLE IF NOT EXISTS admin_users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name VARCHAR(128),
  role VARCHAR(32) NOT NULL DEFAULT 'admin',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  token_version INTEGER NOT NULL DEFAULT 1,
  last_login_at TIMESTAMPTZ,
  password_changed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_status ON admin_users(status);
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `email` | 登录账号之一，唯一 |
| `username` | 登录账号之一，唯一 |
| `password_hash` | 使用 Argon2id 或 bcrypt hash，禁止明文或可逆加密 |
| `role` | 初期支持 `owner`、`admin`、`viewer` |
| `status` | `active`、`disabled`、`pending` |
| `token_version` | 全部设备退出、改密、禁用后使旧 access token 失效 |
| `last_login_at` | 最近成功登录时间 |
| `password_changed_at` | 最近改密时间 |

### 4.2 admin_sessions

```sql
CREATE TABLE IF NOT EXISTS admin_sessions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  refresh_token_hash VARCHAR(128) NOT NULL UNIQUE,
  user_agent TEXT,
  ip_address VARCHAR(64),
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires_at ON admin_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_status ON admin_sessions(status);
```

不使用数据库外键；创建 session 前由 repository 确认 `admin_users.id` 存在且状态允许登录。

### 4.3 admin_audit_logs（建议同批建表，可延后接入）

```sql
CREATE TABLE IF NOT EXISTS admin_audit_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT,
  action VARCHAR(128) NOT NULL,
  resource_type VARCHAR(64),
  resource_id VARCHAR(64),
  request_id VARCHAR(64),
  ip_address VARCHAR(64),
  user_agent TEXT,
  detail JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_user_id ON admin_audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_action ON admin_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_resource ON admin_audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at ON admin_audit_logs(created_at);
```

本期最少记录：

- 登录成功 / 失败
- 退出登录
- 创建 / 删除 API Key
- 创建 / 更新 / 删除 Provider
- 创建 / 更新 / 删除 Model、RouteRule
- 禁用 / 启用用户

---

## 5. 密码与安全策略

### 5.1 密码 hash

推荐使用 `pwdlib[argon2]` 或 `passlib[bcrypt]`。

优先级：

1. Argon2id：更适合密码 hash，新项目优先。
2. bcrypt：依赖更常见，落地简单。

安全要求：

- 禁止自写 SHA256 密码 hash。
- 注册、改密、重置密码只保存 hash。
- 登录校验使用库函数 verify。

### 5.2 密码规则

第一期建议：

- 最少 10 位。
- 至少包含字母和数字。
- 禁止全空白。
- 前后 trim 后入库。

不要在后端强制过复杂规则，避免用户用弱规律密码；后续可以接入泄露密码库检查。

### 5.3 登录防护

第一期建议：

- 连续失败 5 次后，对账号或 IP 做 10 分钟冷却。
- 返回统一错误：`Invalid credentials`，避免枚举邮箱/用户名。
- 登录成功后清空失败计数。

计数可以先放 Redis：

```text
admin-login-fail:account:{email_or_username}
admin-login-fail:ip:{ip}
```

没有 Redis 时，退化为仅记录 audit log，不阻塞本地开发。

---

## 6. 后端接口设计

新增路由文件：

```text
backend/app/api/v1/auth.py
```

挂载路径建议：

```text
/auth/*
```

不要放在 `/admin/auth/*` 下，避免被全局 admin dependency 拦截。

### 6.1 POST /auth/register

用途：注册管理用户。

迁移期策略：

- 如果系统内不存在任何 `admin_users`，允许创建首个 `owner`。
- 如果已经存在用户，则必须满足其中一种条件：
  - 请求携带有效 bootstrap `ADMIN_TOKEN`；
  - 当前登录用户为 `owner` 或具备 `users:write` 权限。

请求：

```json
{
  "email": "admin@example.com",
  "username": "admin",
  "password": "strong-password-123",
  "display_name": "Admin"
}
```

响应：

```json
{
  "id": 1,
  "email": "admin@example.com",
  "username": "admin",
  "display_name": "Admin",
  "role": "owner",
  "status": "active"
}
```

### 6.2 POST /auth/login

请求：

```json
{
  "account": "admin@example.com",
  "password": "strong-password-123"
}
```

响应：

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh-token>",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "email": "admin@example.com",
    "username": "admin",
    "display_name": "Admin",
    "role": "owner"
  }
}
```

### 6.3 POST /auth/refresh

请求：

```json
{
  "refresh_token": "<refresh-token>"
}
```

响应同 `/auth/login`，可选择 refresh token rotation：

- 推荐每次 refresh 都签发新的 refresh token。
- 旧 refresh token 立即标记为 revoked。

### 6.4 GET /auth/me

Header：

```http
Authorization: Bearer <access_token>
```

响应：

```json
{
  "id": 1,
  "email": "admin@example.com",
  "username": "admin",
  "display_name": "Admin",
  "role": "owner",
  "status": "active"
}
```

### 6.5 POST /auth/logout

请求：

```json
{
  "refresh_token": "<refresh-token>"
}
```

行为：

- 将对应 `admin_sessions.status` 设为 `revoked`。
- 前端清理本地 access/refresh token。

### 6.6 POST /auth/logout-all

需要登录。

行为：

- `admin_users.token_version += 1`。
- 撤销该用户所有 active sessions。

### 6.7 用户管理接口（第二阶段）

建议放在 `/admin/users`，受 RBAC 控制：

- `GET /admin/users`
- `POST /admin/users`
- `PATCH /admin/users/{id}`
- `POST /admin/users/{id}/disable`
- `POST /admin/users/{id}/reset-password`

---

## 7. 鉴权依赖改造

### 7.1 新增 AdminAuthContext

建议在 `backend/app/core/security.py` 或新文件 `backend/app/core/admin_auth.py` 中定义：

```python
@dataclass(slots=True)
class AdminAuthContext:
    user: AdminUser
    scopes: set[str]
```

### 7.2 替换 require_admin

当前：

```python
async def require_admin(authorization: str | None = Header(default=None)) -> None:
    verify_admin_token(get_settings().admin_token, authorization)
```

目标：

```python
async def get_admin_context(
    session: AsyncSession = Depends(session_dep),
    authorization: str | None = Header(default=None),
) -> AdminAuthContext:
    ...

async def require_admin(
    auth: AdminAuthContext = Depends(get_admin_context),
) -> AdminAuthContext:
    return auth
```

这样现有 `router = APIRouter(dependencies=[Depends(require_admin)])` 可以平滑替换；后续需要操作者信息的接口可显式注入：

```python
async def create_provider(
    payload: ProviderWrite,
    admin: AdminAuthContext = Depends(require_admin),
    session: AsyncSession = Depends(session_dep),
):
    ...
```

### 7.3 Bootstrap token 兼容

建议新增单独依赖，不要让旧 `ADMIN_TOKEN` 永久等同管理员：

```python
async def require_bootstrap_admin(...)
```

只允许用于：

- 首个用户初始化。
- 迁移期创建用户。

不允许继续访问 provider/model/client 等日常管理接口。

---

## 8. RBAC 设计

### 8.1 角色

第一期使用 `admin_users.role` 单字段：

| 角色 | 权限 |
| --- | --- |
| `owner` | 全部权限，含用户管理、全部设备退出、危险配置 |
| `admin` | 管理 provider/model/client/api key/route，查看 usage |
| `viewer` | 只读 dashboard、usage、配置列表 |

### 8.2 Scope 映射

代码中维护固定映射，不需要建表：

```python
ROLE_SCOPES = {
    "owner": {"*"},
    "admin": {
        "dashboard:read",
        "clients:write",
        "api_keys:write",
        "providers:write",
        "models:write",
        "routes:write",
        "usage:read",
        "workbench:write",
    },
    "viewer": {
        "dashboard:read",
        "clients:read",
        "providers:read",
        "models:read",
        "routes:read",
        "usage:read",
    },
}
```

### 8.3 接口权限建议

| 接口 | Scope |
| --- | --- |
| `GET /admin/dashboard` | `dashboard:read` |
| `GET /admin/clients` | `clients:read` |
| `POST/PATCH/DELETE /admin/clients` | `clients:write` |
| `GET /admin/api-keys` | `api_keys:read` |
| `POST/PATCH/DELETE /admin/api-keys` | `api_keys:write` |
| `GET /admin/providers` | `providers:read` |
| `POST/PATCH/DELETE /admin/providers` | `providers:write` |
| `GET /admin/models` | `models:read` |
| `POST/PATCH/DELETE /admin/models` | `models:write` |
| `GET /admin/route-rules` | `routes:read` |
| `POST/PATCH/DELETE /admin/route-rules` | `routes:write` |
| `GET /admin/usage-logs` | `usage:read` |
| `POST /admin/workbench/chat-test` | `workbench:write` |
| `/admin/users/*` | `users:write` |

第一期可以先只校验 `role in {"owner", "admin"}` 访问所有管理接口，`viewer` 只读；scope 依赖后续逐步细化。

---

## 9. 后端文件改造清单

### 9.1 新增文件

```text
backend/app/db/sql/007_admin_users.sql
backend/app/repositories/admin_users.py
backend/app/repositories/admin_sessions.py
backend/app/repositories/admin_audit_logs.py
backend/app/schemas/auth.py
backend/app/api/v1/auth.py
backend/app/services/admin_auth_service.py
```

### 9.2 修改文件

```text
backend/app/db/models.py
backend/app/core/config.py
backend/app/core/security.py
backend/app/api/deps.py
backend/app/main.py
backend/app/api/v1/admin/resources.py
backend/app/api/v1/admin/workbench.py
backend/README.md
```

### 9.3 配置项

新增环境变量：

```env
JWT_SECRET_KEY=<required-in-prod>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
ADMIN_REGISTRATION_MODE=bootstrap
```

`ADMIN_TOKEN` 迁移期保留，但语义调整为 bootstrap token：

```env
ADMIN_TOKEN=<bootstrap-token-only>
```

生产环境要求：

- `JWT_SECRET_KEY` 必须显式配置，不能使用默认值。
- `ADMIN_TOKEN` 必须显式配置，且只用于初始化用户。

---

## 10. 前端改造设计

### 10.1 登录页

`LoginPage.tsx` 从 Admin Token 改为：

- Backend URL
- Account（email 或 username）
- Password
- 登录按钮

登录流程：

1. 调用 `POST /auth/login`。
2. 保存 `access_token`、`refresh_token`、`user`、`apiBase`。
3. 调用 `/auth/me` 或直接进入 dashboard。

### 10.2 App 状态

`App.tsx` 当前状态：

```ts
const [adminToken, setAdminToken] = useState(localStorage.getItem("adminToken") || "");
```

目标状态：

```ts
const [accessToken, setAccessToken] = useState(localStorage.getItem("accessToken") || "");
const [refreshToken, setRefreshToken] = useState(localStorage.getItem("refreshToken") || "");
const [currentUser, setCurrentUser] = useState<AuthUser | null>(...);
```

所有管理 API headers：

```ts
{ Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }
```

### 10.3 API helper

`frontend/src/lib/api.ts` 增强：

- 遇到 401 时尝试调用 `/auth/refresh`。
- refresh 成功后重试原请求一次。
- refresh 失败则清理 token 并回到登录页。

### 10.4 退出登录

前端 logout：

1. 调用 `POST /auth/logout`，传 refresh token。
2. 清理 `localStorage.accessToken`、`localStorage.refreshToken`、旧的 `localStorage.adminToken`。
3. 清理用户状态并回到登录页。

### 10.5 首个管理员注册页

可选方案：

- 简化版：不做单独页面，提供后端 curl 初始化说明。
- 完整版：登录页增加“初始化管理员”入口，输入 bootstrap token 后调用 `/auth/register`。

建议第一期用简化版，先把核心登录链路做稳。

---

## 11. 迁移策略

### 11.1 阶段一：兼容上线

1. 新增 `admin_users`、`admin_sessions`、`admin_audit_logs` 表。
2. 新增 `/auth/register`、`/auth/login`、`/auth/me`、`/auth/refresh`、`/auth/logout`。
3. `/admin/*` 仍临时支持两种 token：
   - 新 access token。
   - 旧 `ADMIN_TOKEN`。
4. 前端切换到用户名密码登录。

### 11.2 阶段二：收紧旧 token

1. `/admin/*` 不再接受 `ADMIN_TOKEN`。
2. `ADMIN_TOKEN` 只允许访问 `/auth/register` 的 bootstrap 分支。
3. README 和 `.env.example` 更新命名说明。

### 11.3 阶段三：权限与审计完善

1. 接入 scope 校验。
2. 管理用户 CRUD。
3. 关键写操作记录 `admin_audit_logs`。
4. usage、provider、api key 等页面展示操作者审计记录。

---

## 12. 测试计划

### 12.1 后端测试

新增或扩展 `backend/tests/test_app_integration.py`：

- 首个用户可注册为 `owner`。
- 已有用户后，未携带 bootstrap token 不能开放注册。
- 登录成功返回 access/refresh token。
- 错误密码返回 401，且错误信息不泄露账号是否存在。
- `/auth/me` 可用 access token 获取当前用户。
- 过期或签名错误 access token 访问 `/admin/dashboard` 返回 401。
- disabled 用户不能登录，已有 token 也不能继续访问。
- refresh token 可换取新 access token。
- logout 后 refresh token 不能再次使用。
- `viewer` 不能调用写接口。
- `/v1/chat/completions` 仍只接受 API Key，不接受 admin access token。

### 12.2 前端验证

当前没有前端测试脚本，至少执行：

```bash
cd frontend
npm run build
```

手动验证：

- 未登录访问任意 tab 时展示登录页。
- 登录成功进入 dashboard。
- 刷新页面后仍可保持登录。
- access token 过期后 refresh 成功并重试请求。
- logout 后不能继续访问 dashboard。
- 旧 `localStorage.adminToken` 不再影响登录状态。

---

## 13. 实施顺序建议

1. 后端先新增 DB 脚本、ORM、schema、repository。
2. 实现 `AdminAuthService`：密码 hash、登录、JWT、refresh token hash。
3. 实现 `/auth/*` 接口和测试。
4. 改造 `require_admin`，临时兼容旧 `ADMIN_TOKEN`。
5. 前端切换登录页和 token 状态。
6. 跑通手动登录和 `uv run pytest`。
7. 移除 `/admin/*` 对旧 `ADMIN_TOKEN` 的兼容，仅保留 bootstrap 注册。
8. 增加 RBAC scope 和审计日志。

---

## 14. 关键决策记录

1. 管理用户不替代 `Client + ApiKey`，避免破坏现有调用策略、计费和 usage 归属。
2. `ADMIN_TOKEN` 降级为 bootstrap token，不再作为长期共享管理员凭据。
3. access token 使用 JWT，refresh token 使用服务端可撤销 session。
4. 第一阶段角色用单字段 `role`，不建复杂 RBAC 表；scope 映射放代码。
5. 数据库继续使用顺序 SQL 脚本，不引入外键和 Alembic。
