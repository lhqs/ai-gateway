# Repository Guidelines

## Project Structure & Module Organization

This repository is a monorepo for the LHQS AI Gateway. Backend code lives in `backend/app/`, with FastAPI entrypoint `app/main.py`, API routes under `app/api/v1/`, service logic in `app/services/`, repositories in `app/repositories/`, provider adapters in `app/providers/`, and database SQL scripts in `app/db/sql/`. Backend tests are in `backend/tests/`.

Frontend code lives in `frontend/src/`. Pages are in `src/pages/`, shared UI/layout components in `src/components/`, API helpers in `src/lib/`, types in `src/types/`, and global styles in `src/styles.css`. Project planning notes are in `docs/`.

## Build, Test, and Development Commands

Backend:

```bash
cd backend
uv sync --dev
uv run pytest
uv run uvicorn app.main:app --reload
```

`uv sync --dev` installs runtime and test dependencies. `uv run pytest` runs the backend test suite. `uvicorn` starts the FastAPI app locally.

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

`npm run dev` starts Vite, `npm run build` creates a production build, and `npm run preview` serves the built app.

## Coding Style & Naming Conventions

Backend targets Python 3.12 and uses Pydantic v2, SQLAlchemy, FastAPI, and async service/repository patterns. Keep modules snake_case, classes PascalCase, and tests named `test_*.py`. Ruff configuration sets a 100-character line length.

Frontend uses TypeScript, React, Vite, and Tailwind. Use PascalCase for React components and page files, for example `DashboardPage.tsx`; use camelCase for functions, variables, and hooks.

## Testing Guidelines

Backend tests use `pytest` with `pytest-asyncio`; async tests are supported automatically. Add focused tests in `backend/tests/` when changing routing, access policy, usage tracking, provider behavior, caching, or proxy handling. There is currently no frontend test script, so validate UI changes with `npm run build` and manual local checks.

## Database Change Guidelines

For schema or seed data changes, add numbered SQL scripts under `backend/app/db/sql/`. Do not use Alembic migrations in this project. Do not add database foreign keys; enforce relationships in application logic and repositories instead.

## Commit & Pull Request Guidelines

The current git history uses Conventional Commit-style messages such as `feat: init commit` and `feat: new version`. Continue with concise prefixes like `feat:`, `fix:`, `docs:`, `test:`, or `chore:`.

Pull requests should include a clear summary, test results (`uv run pytest`, `npm run build` as applicable), linked issues or context, and screenshots for visible frontend changes.

## Security & Configuration Tips

Do not commit `.env` files or secrets. Backend configuration includes `DATABASE_URL`, `POSTGRES_DSN`, `REDIS_URL`, `ADMIN_TOKEN`, `CORS_ORIGINS`, and proxy/cache limits.
