# LHQS AI Gateway Backend

FastAPI backend for the V3 AI gateway MVP.

## Run locally

```bash
cd backend
uv sync
cp .env.example .env
psql "$POSTGRES_DSN" -f app/db/sql/001_initial_schema.sql
psql "$POSTGRES_DSN" -f app/db/sql/002_seed_dev.sql
psql "$POSTGRES_DSN" -f app/db/sql/003_access_config.sql
uv run uvicorn app.main:app --reload
```

Important environment variables:

- `DATABASE_URL`: PostgreSQL async SQLAlchemy URL used by the backend.
- `POSTGRES_DSN`: PostgreSQL sync URL used by `psql` when applying SQL scripts.
- `REDIS_URL`: Redis URL for rate limiting and response cache.
- `ADMIN_TOKEN`: bearer token for `/admin/*`.
- `REQUEST_BODY_LIMIT_BYTES`: native proxy request body limit.
- `NATIVE_STREAM_MAX_SECONDS`: native streaming connection duration limit.
- `DEFAULT_RATE_LIMIT_PER_MINUTE`: fallback Redis rate limit.
- `CACHE_NAMESPACE`: Redis cache key namespace.
- `CORS_ORIGINS`: comma-separated frontend origins allowed to call the backend.

Database changes are SQL scripts under `app/db/sql/`. Alembic is intentionally not used.

## Access policy

`clients.access_config` and `api_keys.access_config` are merged at request time. Empty or missing lists mean unrestricted for that dimension.

Example:

```json
{
  "model_aliases": ["default-chat"],
  "provider_names": ["openai", "gemini"],
  "model_ids": [1, 2],
  "native_paths": ["v1beta/models/*", "v1beta/models/*:generateContent"]
}
```

## Verify

```bash
uv sync --dev
uv run pytest
```
