# Scaffold command contract

Merge scripts into the existing web manifest; install compatible versions and commit its lockfile. Do not execute a fragment as an application. The optional `contracts:check` command needs an implementation before it can pass; create scripts/contracts/check.cjs in the target app.

## Expected application entry points

- apps/api/app/main.py exposes app.
- apps/api/app/export_openapi.py prints canonical, sorted OpenAPI JSON without production DB/model initialization.
- apps/api/app/seed_demo.py accepts --reset, --organization demo and --fixed-date YYYY-MM-DD; refuses non-demo database/organization.
- apps/api/pyproject.toml and uv.lock include FastAPI/Pydantic, SQLAlchemy/Alembic, psycopg, OR-Tools; ruff/pytest/httpx in a dev group. Keep Chronos/torch optional or lazily imported for CI baseline tests.
- apps/api/tests/integration/test_migrations.py applies migrations to the isolated test DB and checks schema constraints; it must not just mock Alembic.
- apps/web package includes compatible Next/React/TypeScript, chosen CSS/primitives, motion, recharts, and dev tools Vitest/Playwright/ESLint/openapi-typescript.
- apps/web/tests/e2e/demo.spec.ts implements the actual judge journey and tests data changes after replan.
- scripts/contracts/check.cjs regenerates backend OpenAPI and TS into a temporary directory, compares them with packages/contracts/openapi.json and packages/contracts/src/schema.d.ts, then exits nonzero on drift. Run the installed generator from the web package; canonicalize OpenAPI key ordering and exclude environment-dependent server URLs. Do not use a git-diff-only check that misses untracked output.

## First local commands after scaffold

Run `npm ci --prefix apps/web` and `uv sync --frozen --project apps/api` after lockfiles exist. In apps/api: `uv run --frozen alembic upgrade head`, then the demo seed/reset command against the dedicated dev DB. Use `uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000` there, and `npm run dev` in apps/web. Two terminals avoid shell-background portability issues.

CI must fail until these entry points and meaningful tests exist. The kit does not fake them to make checks green.
