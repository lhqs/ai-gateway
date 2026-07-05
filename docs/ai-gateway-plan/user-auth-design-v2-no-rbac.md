# 管理后台用户注册登录设计 v2（无 RBAC）

> 维护日期：2026-07-05
> 适用范围：LHQS AI Gateway 管理后台注册、登录、退出、管理 API 鉴权
> 与上一版关系：本文件是新版独立文档，不覆盖 `user-auth-design.md`。本版按新要求移除 RBAC 权限管理，不再设计角色、scope、权限矩阵。
> 数据库约束：继续使用 `backend/app/db/sql/` 顺序 SQL 脚本；不使用 Alembic；不新增数据库外键，关系由应用层与 repository 校验。

---

## 1. 背景与目标

当前管理后台使用单一共享 `ADMIN_TOKEN`：

- 所有 `/admin/*` 接口只校验同一个 Bearer token。
- 无法区分具体操作者。
- token 泄露后只能整体替换。
- 前端登录页要求用户直接输入 backend admin token，不适合长期使用。

本期目标：

1. 落地管理后台用户注册、登录、退出。
2. 管理接口从共享 `ADMIN_TOKEN` 改为登录态 access token。
3. 支持首个管理员初始化。
4. 支持单个用户禁用、改密、退出当前会话、退出全部会话。
5. 保留现有 `Client + ApiKey` 作为模型调用方鉴权，不影响 `/v1/chat/completions` 和 `/proxy/*`。
6. 不做 RBAC。只要是启用状态的已登录管理用户，就可以访问管理后台功能。

非目标：

1. 不做角色、scope、菜单权限、接口权限矩阵。
2. 不接入 OAuth、SSO、LDAP、飞书登录。
3. 不把管理用户作为模型调用方身份。
4. 不改造现有 Client/API Key 的访问策略、限流、计费与 usage 归属。

---

## 2. 当前代码现状

### 2.1 后端管理鉴权

当前路径：

- `backend/app/api/deps.py`
  - `require_admin()` 读取 `Authorization` header。
  - 调用 `verify_admin_token(get_settings().admin_token, authorization)`。
- `backend/app/core/security.py`
  - `verify_admin_token()` 比较请求 Bearer token 和环境变量 `ADMIN_TOKEN`。
- `backend/app/api/v1/admin/resources.py`
  - `router = APIRouter(dependencies=[Depends(require_admin)])`。
- `backend/app/api/v1/admin/workbench.py`
  - 同样依赖 `require_admin`。

### 2.2 后端调用方鉴权

当前路径：

- `/v1/chat/completions` 与 `/proxy/{provider}/{native_path}` 使用 `get_auth_context()`。
- `get_auth_context()` 基于 Bearer API Key 找到 `ApiKey + Client`。
- `clients.access_config` 与 `api_keys.access_config` 合并后控制模型、provider、native path 等访问策略。

结论：管理后台用户体系只替换 `/admin/*` 鉴权，不替换调用方 API Key。

### 2.3 前端

当前路径：

- `frontend/src/pages/LoginPage.tsx`
  - 输入 Backend URL 和 Admin Token。
- `frontend/src/App.tsx`
  - 登录时调用 `/admin/dashboard` 校验 token。
  - token 保存在 `localStorage.adminToken`。
  - 后续管理 API 请求使用 `Authorization: Bearer <adminToken>`。

目标：改为账号密码登录，保存后端签发的 access token 和 refresh token。

---

## 3. 总体方案

系统保留两类身份：

| 身份类型 | 用途 | 鉴权方式 | 接口范围 |
| --- | --- | --- | --- |
| 管理用户 `AdminUser` | 登录管理台，管理 provider/model/client/api key，查看 usage | 登录后签发 token | `/auth/*`, `/admin/*` |
| 调用方 `Client + ApiKey` | 调用模型网关 | API Key Bearer | `/v1/chat/completions`, `/proxy/*` |

管理用户登录后即可访问所有管理后台能力。本期不区分 owner/admin/viewer，也不限制某个用户能否访问某个管理接口。

推荐认证模型：

- `access_token`
  - JWT。
  - 默认 30 分钟有效。
  - 前端调用 `/admin/*` 时放入 `Authorization: Bearer <access_token>`。
  - 后端校验签名、过期时间、用户状态、token version。
- `refresh_token`
  - 高熵随机字符串。
  - 服务端只保存 hash。
  - 默认 14 天有效。
  - 用于刷新 access token。
  - 支持撤销单个会话。

`ADMIN_TOKEN` 降级为 bootstrap token，只用于首个用户初始化或迁移期创建用户，不再作为长期管理后台通行凭据。

---

## 4. 数据库设计

新增 SQL 脚本建议：

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
| `password_hash` | 密码 hash，禁止明文或可逆加密 |
| `display_name` | 展示名 |
| `status` | `active`、`disabled` |
| `token_version` | 改密、退出全部会话、禁用账号后使旧 access token 失效 |
| `last_login_at` | 最近成功登录时间 |
| `password_changed_at` | 最近改密时间 |

说明：本版不需要 `role` 字段。如果后续确实要补权限管理，可以通过新增脚本再加字段，不在本期预埋。

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

说明：

- 不使用数据库外键。
- 创建 session 前由 repository 校验 `admin_users.id` 存在。
- 刷新 token 时校验 session 为 `active` 且未过期。

### 4.3 admin_audit_logs（可选但建议同批建表）

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

即使不做权限管理，也建议记录操作审计，至少覆盖：

- 登录成功 / 失败
- 退出登录
- 改密
- 创建 / 删除 API Key
- 创建 / 更新 / 删除 Provider
- 创建 / 更新 / 删除 Model
- 创建 / 更新 / 删除 RouteRule

---

## 5. 密码与登录安全

### 5.1 密码 hash

推荐使用：

1. `pwdlib[argon2]`：优先，适合新项目。
2. `passlib[bcrypt]`：可接受，生态常见。

要求：

- 禁止自写 SHA256 密码 hash。
- 禁止保存明文密码。
- 登录校验使用库函数 verify。

### 5.2 密码规则

建议规则：

- 最少 10 位。
- 至少包含字母和数字。
- trim 后不能为空。

### 5.3 登录失败防护

建议用 Redis 记录失败次数：

```text
admin-login-fail:account:{account}
admin-login-fail:ip:{ip}
```

策略：

- 连续失败 5 次后冷却 10 分钟。
- 错误响应统一为 `Invalid credentials`，避免泄露账号是否存在。
- 登录成功后清空失败计数。
- Redis 不可用时不阻塞本地开发，只记录 audit log。

---

## 6. 后端接口设计

新增文件：

```text
backend/app/api/v1/auth.py
backend/app/schemas/auth.py
backend/app/services/admin_auth_service.py
backend/app/repositories/admin_users.py
backend/app/repositories/admin_sessions.py
```

接口挂载：

```text
/auth/*
```

不要放在 `/admin/auth/*` 下，避免被管理接口依赖拦截。

### 6.1 POST /auth/register

用途：创建管理用户。

注册策略：

- 如果系统内没有任何 `admin_users`，允许创建首个用户。
- 如果系统内已有用户，则必须携带有效 bootstrap `ADMIN_TOKEN`。
- 本期不做“已登录用户创建其他用户”的权限区分；是否开放多用户创建由注册策略统一控制。

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
    "status": "active"
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

行为：

- 校验 refresh token hash 是否存在。
- 校验 session 是否 active、未过期。
- 校验用户是否 active。
- 签发新的 access token。
- 推荐 refresh token rotation：每次刷新都撤销旧 refresh token 并签发新 refresh token。

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
- 写入 `revoked_at`。
- 前端清理本地 token。

### 6.6 POST /auth/logout-all

需要登录。

行为：

- `admin_users.token_version += 1`。
- 撤销该用户全部 active sessions。
- 旧 access token 因 token version 不匹配失效。

### 6.7 POST /auth/change-password

需要登录。

请求：

```json
{
  "old_password": "old-password",
  "new_password": "new-password-123"
}
```

行为：

- 校验旧密码。
- 更新 `password_hash`。
- 更新 `password_changed_at`。
- `token_version += 1`。
- 撤销所有 refresh sessions。
- 要求用户重新登录。

---

## 7. 管理接口鉴权改造

### 7.1 新增 AdminAuthContext

```python
@dataclass(slots=True)
class AdminAuthContext:
    user: AdminUser
```

不包含 role、scope。

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

校验逻辑：

1. 必须存在 `Authorization: Bearer <access_token>`。
2. JWT 签名有效。
3. JWT 未过期。
4. JWT 中的 `sub` 对应用户存在。
5. 用户 `status = active`。
6. JWT 中的 `token_version` 等于数据库中的 `admin_users.token_version`。

### 7.3 Bootstrap token

保留单独函数：

```python
async def require_bootstrap_token(...)
```

只允许用于 `/auth/register` 的受保护分支。

不允许继续用于：

- `/admin/dashboard`
- `/admin/providers`
- `/admin/models`
- `/admin/clients`
- `/admin/api-keys`
- `/admin/usage-logs`
- `/admin/workbench/*`

---

## 8. 前端改造

### 8.1 登录页

`LoginPage.tsx` 改为：

- Backend URL
- Account（email 或 username）
- Password
- Sign In

移除 Admin Token 输入。

登录流程：

1. 调用 `POST /auth/login`。
2. 保存 `access_token`、`refresh_token`、`user`、`apiBase`。
3. 进入 dashboard。

### 8.2 App 状态

当前：

```ts
const [adminToken, setAdminToken] = useState(localStorage.getItem("adminToken") || "");
```

目标：

```ts
const [accessToken, setAccessToken] = useState(localStorage.getItem("accessToken") || "");
const [refreshToken, setRefreshToken] = useState(localStorage.getItem("refreshToken") || "");
const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
```

管理 API headers：

```ts
{
  Authorization: `Bearer ${accessToken}`,
  "Content-Type": "application/json"
}
```

### 8.3 API helper

`frontend/src/lib/api.ts` 增强：

- 请求返回 401 时调用 `/auth/refresh`。
- refresh 成功后更新 localStorage，并重试原请求一次。
- refresh 失败则清理 token，回到登录页。

### 8.4 退出登录

流程：

1. 调用 `POST /auth/logout`。
2. 清理：
   - `localStorage.accessToken`
   - `localStorage.refreshToken`
   - `localStorage.authUser`
   - 旧的 `localStorage.adminToken`
3. 回到登录页。

### 8.5 首个用户初始化

建议第一期先用后端接口或 curl 初始化：

```bash
curl -X POST "$API_BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","password":"strong-password-123","display_name":"Admin"}'
```

如果系统已有用户，创建新用户需要携带 bootstrap token：

```bash
curl -X POST "$API_BASE/auth/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","username":"ops","password":"strong-password-123","display_name":"Ops"}'
```

---

## 9. 配置项

新增：

```env
JWT_SECRET_KEY=<required-in-prod>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
ADMIN_REGISTRATION_MODE=bootstrap
```

保留但调整语义：

```env
ADMIN_TOKEN=<bootstrap-token-only>
```

生产环境要求：

- `JWT_SECRET_KEY` 必须显式配置。
- `ADMIN_TOKEN` 必须显式配置且只用于 bootstrap。
- 默认开发值只能用于本地。

---

## 10. 迁移策略

### 10.1 阶段一：新增能力

1. 新增 SQL 脚本、ORM、repository、schema。
2. 实现 `/auth/register`、`/auth/login`、`/auth/me`、`/auth/refresh`、`/auth/logout`、`/auth/change-password`。
3. 保留旧 `ADMIN_TOKEN` 访问 `/admin/*` 的兼容一小段时间，便于前后端分步上线。
4. 前端切换为账号密码登录。

### 10.2 阶段二：收紧兼容

1. `/admin/*` 只接受用户 access token。
2. `ADMIN_TOKEN` 只用于 `/auth/register` 的 bootstrap 分支。
3. README 和 `.env.example` 更新说明。
4. 前端清理旧 `localStorage.adminToken`。

### 10.3 阶段三：审计与运维增强

1. 写入关键管理操作 audit log。
2. 增加用户列表、禁用用户、重置密码等管理能力。
3. 增加会话列表与撤销指定会话能力。

---

## 11. 后端文件改造清单

新增：

```text
backend/app/db/sql/007_admin_users.sql
backend/app/repositories/admin_users.py
backend/app/repositories/admin_sessions.py
backend/app/repositories/admin_audit_logs.py
backend/app/schemas/auth.py
backend/app/api/v1/auth.py
backend/app/services/admin_auth_service.py
```

修改：

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

前端修改：

```text
frontend/src/App.tsx
frontend/src/pages/LoginPage.tsx
frontend/src/lib/api.ts
frontend/src/types/gateway.ts
```

---

## 12. 测试计划

### 12.1 后端测试

建议覆盖：

- 首个用户可以无 bootstrap token 注册。
- 已存在用户后，无 bootstrap token 不能继续注册。
- 已存在用户后，有 bootstrap token 可以注册新用户。
- 登录成功返回 access token 和 refresh token。
- 错误密码返回 401，错误信息统一。
- disabled 用户不能登录。
- `/auth/me` 可通过 access token 获取当前用户。
- 过期 access token 访问 `/admin/dashboard` 返回 401。
- refresh token 可换取新 access token。
- logout 后 refresh token 不能再次使用。
- change-password 后旧 access token 和 refresh token 失效。
- `/admin/*` 不再接受旧 `ADMIN_TOKEN`。
- `/v1/chat/completions` 仍只接受 API Key，不接受管理用户 access token。

### 12.2 前端验证

执行：

```bash
cd frontend
npm run build
```

手动验证：

- 未登录时展示登录页。
- 登录成功进入 dashboard。
- 刷新页面后保持登录。
- access token 过期后 refresh 成功并重试请求。
- logout 后不能继续访问管理页。
- 旧 `localStorage.adminToken` 不再影响登录状态。

---

## 13. 不确认信息，需要确认

以下点当前需求里没有完全确定，建议实现前确认：

1. 是否允许开放注册？
   - 方案默认：首个用户可直接注册；已有用户后必须携带 `ADMIN_TOKEN` bootstrap token。
2. 是否需要多用户？
   - 方案默认：支持多用户，但所有 active 用户权限相同。
3. 是否需要用户管理页面？
   - 方案默认：第一期不强制做页面，可先通过接口创建/禁用用户；后续再补 UI。
4. refresh token 存储方式是否接受 localStorage？
   - 方案默认：为降低改造成本先用 localStorage；更安全方案是 HttpOnly Cookie。
5. access token 和 refresh token 有效期是否合适？
   - 方案默认：access token 30 分钟，refresh token 14 天。
6. 是否需要“忘记密码 / 邮件重置密码”？
   - 方案默认：不做邮件重置，先通过管理接口或数据库运维重置。
7. `ADMIN_TOKEN` 兼容期保留多久？
   - 方案默认：分两阶段上线，前端切换完成后立即禁止 `/admin/*` 使用旧 token。
8. audit log 是否本期必须完整接入？
   - 方案默认：建议先建表；写操作审计可以分批接入。

---

## 14. 推荐实施顺序

1. 新增 DB 脚本和 ORM 模型。
2. 新增 repository、schema、`AdminAuthService`。
3. 实现 `/auth/*` 接口和后端测试。
4. 改造 `require_admin` 支持用户 access token。
5. 短期兼容旧 `ADMIN_TOKEN`，方便前端迁移。
6. 前端改为账号密码登录。
7. 移除 `/admin/*` 对旧 `ADMIN_TOKEN` 的兼容。
8. 增加 change password、logout all、基础审计日志。
