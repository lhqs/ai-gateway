# AI Gateway V3 Implementation Summary

> Date: 2026-07-04  
> Purpose: Summarize the current V3 implementation so later changes can continue from the actual system state instead of re-reading the full discussion.

## 1. Current Status

The project has moved from planning documents to a working V3 MVP implementation.

The current implementation includes:

- FastAPI backend.
- React + Vite frontend management console.
- PostgreSQL schema SQL scripts.
- Redis-based rate limit and cache hooks.
- OpenAI-compatible unified chat API.
- Gemini-style native proxy API.
- Admin APIs for base configuration.
- Admin frontend with login, resource management, and usage log inspection.

The implementation still has P1/P2 production-hardening work recorded in `docs/ai-gateway-v3-todo.md`.

## 2. Important Constraints

Database constraints from the user:

- Do not use foreign keys.
- Do not use Alembic.
- Use SQL scripts for database changes.

Current SQL scripts:

- `backend/app/db/sql/001_initial_schema.sql`
- `backend/app/db/sql/002_seed_dev.sql`
- `backend/app/db/sql/003_access_config.sql`

The SQL scripts intentionally use integer id reference fields without database-level foreign key constraints.

## 3. Backend Summary

Backend stack:

- Python
- FastAPI
- SQLAlchemy async
- PostgreSQL
- Redis
- Pydantic settings
- httpx
- pytest

Key backend entry points:

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/api/v1/chat.py`
- `backend/app/api/v1/proxy.py`
- `backend/app/api/v1/admin/resources.py`

Implemented business APIs:

- `POST /v1/chat/completions`
- `GET /proxy/{provider}/{native_path:path}`
- `POST /proxy/{provider}/{native_path:path}`

Implemented admin APIs:

- clients
- api keys
- providers
- provider connectivity test
- models
- model aliases
- route rules
- usage logs
- dashboard

## 4. Backend Design Decisions

Provider adapter split:

- Unified chat adapters live under `backend/app/providers/`.
- Native proxy adapters also live under `backend/app/providers/`.
- `openai_compatible.py` handles OpenAI-compatible chat calls.
- `gemini_native.py` handles Gemini native proxy forwarding.

Access control:

- `clients.access_config` and `api_keys.access_config` are merged at request time.
- Access policy is implemented in `backend/app/services/access_policy_service.py`.
- Supported policy dimensions:
  - `model_aliases`
  - `provider_ids`
  - `provider_names`
  - `model_ids`
  - `native_paths`
  - `native_path_patterns`

Cache:

- Implemented for non-streaming unified chat.
- Redis key is built from client, model alias, messages, temperature, top_p, max_tokens, tools, tool_choice, response_format, and stop.
- Cache hit logs usage with `cache_hit=true`.

Failover:

- Non-streaming unified chat supports fallback models.
- Streaming unified chat supports failover only before first token is emitted.
- Once streaming output starts, it does not switch providers/models to avoid mixed responses.

Native proxy:

- Supports GET and POST.
- Uses provider base URL only; no arbitrary URL forwarding.
- Enforces provider allowed path whitelist.
- Filters sensitive headers.
- Injects provider auth by configured auth type.
- Supports request body size limit.
- Supports native stream max duration.
- Allows native provider error response passthrough when provider returned structured body/status.

Usage logging:

- Logs unified and native call modes.
- Stores prompt/completion for unified chat.
- Stores native request/response body for native proxy.
- Stores cache and failover fields.
- Records access denied native proxy calls.
- Usage logs are not auto-deleted.

## 5. Frontend Summary

Frontend stack:

- Vite
- React
- Tailwind CSS
- lucide-react

Frontend source is now split for maintainability:

- `frontend/src/main.tsx`: app entry only.
- `frontend/src/App.tsx`: app-level state and page routing.
- `frontend/src/types/gateway.ts`: domain types.
- `frontend/src/lib/api.ts`: API base, request helper, parsing utilities.
- `frontend/src/components/layout.tsx`: app shell and navigation.
- `frontend/src/components/ui.tsx`: shared UI primitives.
- `frontend/src/pages/`: feature pages.

Feature pages:

- `DashboardPage.tsx`
- `ClientsPage.tsx`
- `ProvidersPage.tsx`
- `ModelsPage.tsx`
- `RoutesPage.tsx`
- `UsagePage.tsx`
- `LoginPage.tsx`

The frontend now has a login page:

- User enters backend URL.
- User enters admin token.
- Login verifies the token through `/admin/dashboard`.
- Backend URL is saved in `localStorage.apiBase`.
- Admin token is saved in `localStorage.adminToken`.
- Logout clears the admin token.

## 6. Configuration Summary

Backend env files:

- `backend/.env.example`: committed template.
- `backend/.env`: local file, ignored by git.

Important backend env vars:

- `DATABASE_URL`
- `POSTGRES_DSN`
- `REDIS_URL`
- `ADMIN_TOKEN`
- `REQUEST_BODY_LIMIT_BYTES`
- `NATIVE_STREAM_MAX_SECONDS`
- `DEFAULT_RATE_LIMIT_PER_MINUTE`
- `CACHE_NAMESPACE`
- `CORS_ORIGINS`

Frontend env files:

- `frontend/.env.example`: committed template.
- `frontend/.env`: local file, ignored by git.

If backend runs on port `8004`, frontend should use:

```env
VITE_API_BASE=http://localhost:8004
```

The frontend login page can also override the backend URL at runtime.

## 7. CORS Notes

A CORS issue was reported from:

- frontend origin: `http://localhost:5174`
- backend URL: `http://localhost:8004`

The backend now uses explicit CORS origins from `CORS_ORIGINS`.

Default local origins include:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174
```

If the frontend port changes, add the new origin to `CORS_ORIGINS` and restart the backend.

## 8. Local Run Commands

Backend:

```bash
cd backend
uv sync
cp .env.example .env
psql "$POSTGRES_DSN" -f app/db/sql/001_initial_schema.sql
psql "$POSTGRES_DSN" -f app/db/sql/002_seed_dev.sql
psql "$POSTGRES_DSN" -f app/db/sql/003_access_config.sql
uv run uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

Frontend:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## 9. Verification Commands

Backend tests:

```bash
cd backend
uv sync --dev
uv run pytest
```

Frontend build:

```bash
cd frontend
npm install
npm run build
```

Recent verification performed during implementation:

- Backend pytest passed with 13 tests.
- Frontend production build passed.
- CORS preflight for `http://localhost:5174` to `/admin/dashboard` returned the expected `access-control-allow-origin`.

## 10. Known Remaining Work

See `docs/ai-gateway-v3-todo.md` for the detailed backlog.

Important remaining themes:

- Provider health checks are still simple.
- `failure_threshold` and `cooldown_seconds` are not yet full runtime circuit-breaker logic.
- Cache metadata persistence is not fully used.
- Usage log filtering can be expanded.
- Frontend forms can be further refined with edit/delete flows.
- PostgreSQL real database initialization should be verified in a dedicated environment.

## 11. Guidance For Future Changes

When continuing development:

- Keep database changes in new SQL scripts.
- Do not add foreign key constraints.
- Do not introduce Alembic.
- Keep frontend pages split under `frontend/src/pages/`.
- Keep shared frontend UI under `frontend/src/components/`.
- Keep request helpers in `frontend/src/lib/api.ts`.
- Keep domain types in `frontend/src/types/gateway.ts`.
- Add tests for service behavior and at least one ASGI integration path when changing backend request flow.
- Re-run both backend tests and frontend build before claiming completion.
