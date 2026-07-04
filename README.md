# LHQS AI Gateway

Monorepo implementation of `docs/ai-gateway-plan-v3.md`.

Included:

- FastAPI backend with `/v1/chat/completions`.
- Native provider proxy at `/proxy/{provider}/{native_path}` for Gemini-style APIs.
- PostgreSQL SQL scripts without foreign keys.
- Redis rate limiting and non-streaming response cache.
- Client/API key access policy for model aliases, providers, models, and native paths.
- Unified chat failover for non-streaming and first-token-before stream failures.
- Native stream duration guard and Gemini stream usage extraction.
- Usage logs with prompt/completion/native request/native response fields.
- Basic admin APIs and React management console.

Backend database changes live in `backend/app/db/sql/`; Alembic is not used.

## Verify

```bash
cd backend
uv sync --dev
uv run pytest
```

```bash
cd frontend
npm install
npm run build
```
