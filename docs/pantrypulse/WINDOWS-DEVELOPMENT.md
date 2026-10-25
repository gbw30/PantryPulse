# Windows development

For first-time setup, use the complete [installation guide](../../INSTALLATION.md), including manual tool installation and optional dependency decisions. This document is a command reference.

Run from the OUTER Git root, not PantryPulse/. PowerShell 5.1/7 supported.

Pinned tools: Node 24.16.0, npm 11.13.0, uv 0.11.15, uv-managed CPython 3.12.13, PostgreSQL 16 in Docker Desktop (Linux containers). System Python 3.15 is unused. .node-version documents Node; it does not install it. Install the pinned Node release and uv through their official distributions or your chosen manager.

Root package-lock.json owns npm workspaces. apps/api/uv.lock owns Python, including optional Chronos resolution. No nested frontend lock.

```powershell
.\scripts\setup-windows.ps1
# Optional database/browser installation:
.\scripts\setup-windows.ps1 -WithDatabase -WithBrowser
# Recommended complete backend option on this host:
.\scripts\setup-windows.ps1 -WithContainerApi
.\scripts\doctor-windows.ps1
.\scripts\doctor-windows.ps1 -RequireDatabase
```

If script policy blocks local scripts, use your organization's approved process or run the individual setup commands in INSTALLATION.md. The setup script does not change execution policy.

Run in separate terminals:
```powershell
npm run dev:api:docker
npm run dev:web
```
Web http://127.0.0.1:3000; API health http://127.0.0.1:8000/api/v1/health; OpenAPI http://127.0.0.1:8000/docs. Health is process liveness, not database/solver readiness.

On this host Windows Application Control rejected a pandas DLL imported by OR-Tools. Use the Docker API runtime above. Native `npm run dev:api` works for the current health scaffold and is an option on hosts whose native libraries are allowed. Do not change security policy as an environment repair. Docker sources are copied at build time; rerun `npm run dev:api:docker` after Python edits. Do not start native and container API simultaneously on port 8000.

```powershell
npm run test:api:docker
npm run check:runtime:docker
docker compose stop api
```

The container runtime smoke runs a trivial CP-SAT model and a read-only database query; it is not allocation validation. The API health itself remains process-only. Container DATABASE_URL uses postgres:5432; native example uses 127.0.0.1:55432. Neither changes production data.

```powershell
npm run check
npm run build
npm exec --workspace @pantrypulse/web -- playwright install chromium
npm run test:e2e
node --test scripts/quality/tests/*.test.cjs
```

These validate the scaffold, offline helpers and configured tests, not the complete product. Full quality gates still expect future public contracts and domain integration. Worker PostgreSQL tests need `PP_TEST_DATABASE_URL`; Linux containment tests skip on native Windows. See the [worker runbook](../setup/WORKER-QUEUE.md). Consult the checked-in quality configuration for hook enforcement rather than assuming every gate is enabled or complete.

Tracked API example: `apps/api/.env.example`. Copy it to `apps/api/.env` only when local API configuration is needed; do not overwrite an existing private file. No web environment example is tracked. The current health/static shell and simulated Vercel preview need no environment file. API settings loading and the selected same-origin Next.js proxy are not implemented yet. No secrets belong in `NEXT_PUBLIC_` variables.

## Database

```powershell
docker compose up -d --wait postgres
docker compose exec -T postgres pg_isready -U pantrypulse -d pantrypulse_dev
docker compose exec -T postgres psql -U pantrypulse -d pantrypulse_test -c "SELECT current_database();"
docker compose stop postgres
```

Local URL: postgresql+psycopg://pantrypulse:local_dev_only@127.0.0.1:55432/pantrypulse_dev. Tests use pantrypulse_test. These isolated local credentials come from existing Compose config and must never be reused for hosting. Init SQL runs only on a fresh named volume. Investigate existing volumes without deleting them.

PR #52 supplies a jobs-only Alembic revision; no domain revisions exist. Neon follows later using server-only credentials and TLS; do not use SQLite as migration validation.

## Optional forecasting dependencies

```powershell
uv sync --frozen --project apps/api --extra forecast
```

This installs large ML libraries; it does not download a checkpoint or implement inference. Normal setup excludes this extra. Chronos hardware/revision/timeout/fallback require validation.

## Updates and troubleshooting

Intentional updates: npm install at root and uv lock --project apps/api; review locks and rerun frozen checks. Normal setup uses npm ci and uv sync --frozen.

Missing Docker named pipe: start Docker Desktop and await Linux engine readiness. Sandbox registry DNS/cache permission errors: use authorized network access or approved writable cache. Never copy nested node_modules as environment setup. Keep caches/.venv/.next/reports ignored.

