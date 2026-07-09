# Production Operations Guide

This guide captures the minimum production setup and troubleshooting loop for LHQS AI Gateway.

## 1. Environment

Start from `backend/.env.example` and set production values explicitly.

Required backend variables:

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/lhqs_ai_gateway
POSTGRES_DSN=postgresql://USER:PASSWORD@HOST:5432/lhqs_ai_gateway
REDIS_URL=redis://HOST:6379/0
ADMIN_TOKEN=<long-random-bootstrap-token>
JWT_SECRET_KEY=<long-random-jwt-secret>
CORS_ORIGINS=https://your-admin-console.example.com
STORE_API_KEY_VALUE=false
DEFAULT_RATE_LIMIT_PER_MINUTE=120
DEFAULT_COST_CURRENCY=USD
```

Production defaults:

- Keep `STORE_API_KEY_VALUE=false`. Full API keys are returned only when created or rotated.
- Use Redis in production. Without Redis, rate limiting and cache degrade gracefully but do not protect upstream providers.
- Keep SQL schema changes in `backend/app/db/sql/` and apply them in numeric order.

Frontend variable:

```bash
VITE_API_BASE=https://your-gateway-api.example.com
```

## 2. Database Initialization

For a new PostgreSQL database, apply every SQL file in order:

```bash
cd backend
for file in app/db/sql/*.sql; do
  psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f "$file"
done
```

After initialization, verify the main tables exist:

```bash
psql "$POSTGRES_DSN" -c "\dt"
psql "$POSTGRES_DSN" -c "select count(*) from providers;"
psql "$POSTGRES_DSN" -c "select count(*) from admin_users;"
```

For upgrades, apply only newly added numbered SQL scripts. Do not use Alembic migrations in this project.

## 3. Provider Configuration Examples

OpenAI-compatible provider:

```json
{
  "name": "openai",
  "provider_type": "openai_compatible",
  "base_url": "https://api.openai.com/v1",
  "encrypted_api_key": "sk-...",
  "protocol_modes": ["openai_compatible"],
  "auth_type": "bearer_token",
  "config": {
    "health_path": "models"
  },
  "failure_threshold": 3,
  "cooldown_seconds": 60
}
```

Gemini native proxy provider:

```json
{
  "name": "gemini",
  "provider_type": "gemini",
  "base_url": "https://generativelanguage.googleapis.com",
  "encrypted_api_key": "AIza...",
  "protocol_modes": ["native_proxy"],
  "auth_type": "api_key_query",
  "auth_config": { "query_name": "key" },
  "allowed_paths": ["v1beta/models/*"],
  "blocked_headers": ["authorization", "cookie"],
  "usage_parser_type": "gemini",
  "native_rate_limit_per_minute": 60,
  "config": {
    "health_path": "v1beta/models"
  }
}
```

Client/API key access policy with key-level rate limit:

```json
{
  "model_aliases": ["default-chat"],
  "provider_names": ["openai", "gemini"],
  "native_paths": ["v1beta/models/*"],
  "rate_limit_per_minute": 30,
  "cost_currency": "USD"
}
```

## 4. Troubleshooting

Provider unhealthy:

- Open `Providers`, run `Test`, and inspect `status_code`, `probe_url`, and `last_health_error`.
- Check `failure_count`, `failure_threshold`, and `cooldown_until`.
- Confirm `base_url`, `auth_type`, `auth_config`, and `config.health_path` match the provider.

Failover not triggered:

- Confirm the route has `failover_enabled=true` and fallback models are ordered.
- Confirm `max_failover_attempts` is at least the number of fallback attempts you expect.
- Check that fallback model/provider status is `active` and provider health is not in cooldown.
- Review `Usage Logs` fields: `failover_triggered`, `failure_reason`, `initial_provider_id`, and `final_provider_id`.

Usage unknown:

- Confirm the provider returns usage metadata for the selected mode.
- For OpenAI-compatible streaming, keep `stream_options.include_usage` enabled.
- For native proxy, set `usage_parser_type` to the matching parser such as `gemini`.

Pricing missing:

- Open `Pricing`, filter by provider/model/status, and create a current active price config.
- Confirm `effective_from` is not in the future and `effective_to` has not expired.
- Check `Usage Logs.pricing_status` for `missing_price_config` or `usage_unknown`.

CORS or login failures:

- Ensure `CORS_ORIGINS` contains the exact frontend origin.
- Ensure `VITE_API_BASE` points to the backend origin reachable from the browser.
- Ensure `JWT_SECRET_KEY` is stable across backend restarts.
- If first admin registration is blocked, use `ADMIN_TOKEN` only for bootstrap registration.

API key failures:

- Disabled or expired keys return 401.
- Rotating a key revokes the old key by default.
- With `STORE_API_KEY_VALUE=false`, full key values are not recoverable after creation or rotation.
- Check `Audit Logs` for `api_key.create`, `api_key.rotate`, and `api_key.revoke` events.
