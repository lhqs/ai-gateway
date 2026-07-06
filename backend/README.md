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
psql "$POSTGRES_DSN" -f app/db/sql/007_admin_users.sql
uv run uvicorn app.main:app --reload
```

Important environment variables:

- `DATABASE_URL`: PostgreSQL async SQLAlchemy URL used by the backend.
- `POSTGRES_DSN`: PostgreSQL sync URL used by `psql` when applying SQL scripts.
- `REDIS_URL`: Redis URL for rate limiting and response cache.
- `ADMIN_TOKEN`: bootstrap bearer token for creating admin users after the first user exists.
- `JWT_SECRET_KEY`: secret used to sign admin access tokens.
- `JWT_ALGORITHM`: JWT signing algorithm, defaults to `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: admin access token lifetime.
- `REFRESH_TOKEN_EXPIRE_DAYS`: admin refresh token lifetime.
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

## OpenAI-compatible provider request body config

`providers.config` can force top-level request body changes before forwarding unified
`/v1/chat/completions` calls to OpenAI-compatible providers.

Example for disabling DeepSeek thinking while removing the client-supplied reasoning effort:

```json
{
  "request_body_remove_fields": ["reasoning_effort"],
  "request_body_overrides": {
    "thinking": {"type": "disabled"}
  }
}
```

## Claude provider config

Claude uses Anthropic's native Messages API behind the gateway's unified
`/v1/chat/completions` endpoint. Configure the provider with `provider_type="claude"`,
Anthropic's default API key header, and model names from the Anthropic API.

```json
{
  "name": "anthropic",
  "provider_type": "claude",
  "base_url": "https://api.anthropic.com",
  "auth_type": "api_key_header",
  "auth_config": {"header": "x-api-key"},
  "usage_parser_type": "anthropic",
  "config": {
    "default_max_tokens": 4096
  }
}
```

## Verify

```bash
uv sync --dev
uv run pytest
```
