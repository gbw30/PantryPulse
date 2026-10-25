# PantryPulse deployment and recovery

Provider-by-provider account/configuration instructions are in [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md). GitHub and Neon support the demo, with Fly.io and Vercel as hosting options. The guide includes the current scaffold's fixed-port, CORS/settings and migration limitations; this runbook describes the later full release workflow.

An isolated [frontend-only Vercel preview](../setup/VERCEL.md) now serves simulated `/design-lab` content from `codex/vercel-prototype-preview`. It has no API, database, proxy, model or presenter controls. Its successful build and browser smoke do not satisfy this runbook's integrated Preview or Judge demo gates.

For the demo-only presentation, the preferred compute is now the presenter's laptop; follow [LOCAL-DEMO.md](../setup/LOCAL-DEMO.md) and the separate compose.demo.yaml configuration. Fly.io below is the optional hosted alternative. The scaffold health/runtime checks do not establish readiness of the unimplemented domain workflow.

This runbook prepares a deployable candidate. It does not create accounts, buy services, expose a real operational database or deploy without the user's target authorization. Provider menus and limits change; confirm current settings in the named account at setup.

## Environment matrix

| Environment | Frontend/API | Database | Forecast mode | Reset |
|---|---|---|---|---|
| Local dev | 127.0.0.1:3000 / :8000 | dedicated dev DB | baseline first, optional Chronos | demo org only |
| Worker | unique ports per lane | worker DB/schema/Neon branch | fixtures/baseline | worker demo only |
| CI | ephemeral servers | PostgreSQL service | baseline/provider doubles; no model downloads | isolated test seed |
| UI prototype | Vercel `/design-lab` only; no API | none | simulated values | branch deployment |
| Preview | Vercel preview + separate API target or explicitly shared demo API | isolated preview/demo DB | cached verified forecast + fallback | presenter protected |
| Judge demo | frozen web/API release pair | dedicated demo DB | prewarmed verified provider/cache, fallback available | presenter protected |

A Vercel preview does not automatically create a matching Python API or database. The current UI prototype intentionally has neither. For a future integrated Preview, implement the selected same-origin Next.js proxy and record the actual web/API/database mapping in the release manifest. Do not broaden CORS to bypass the selected architecture.

## Database and backend

1. Provision a dedicated Neon/PostgreSQL demo database or branch on an authorized account. Use the correct driver URL and TLS mode; store secrets only in server configuration. The template uses postgresql+psycopg with SQLAlchemy; raw tooling may need a plain PostgreSQL URL. Keep migration and runtime URL formats intentional.
2. Apply Alembic migrations as one controlled release step before serving the new API. Test migration on a fresh isolated DB first. Do not run migrations independently from every app worker or frontend preview.
3. Seed the fixed demo organization and verify non-demo organizations are untouched by reset. A reset endpoint scoped only by a user-provided organization ID is insufficient; enforce server-side demo flag and presenter authorization.
4. For the chosen laptop demo, run the supplied Dockerfile through compose.demo.yaml, which explicitly loads the private apps/api/.env.demo Neon connection and publishes only 127.0.0.1:8000. Follow LOCAL-DEMO.md for startup and verification; no Fly service is required. If switching later to Fly.io, use its separate optional guide and match internal_port to 8000. Confirm uv.lock and the installed Python/runtime pair work. The current /api/v1/health is process liveness only; future readiness should check DB connectivity/migration compatibility without forcing a model download.
5. Configure DATABASE_URL, APP_ENV, DEMO_MODE, CORS_ALLOWED_ORIGINS, FORECAST_MODEL_ID, FORECAST_DEVICE and SOLVER_TIME_LIMIT_SECONDS. FORECAST_PROVIDER and DEMO_FIXED_DATE are proposed app extensions; implement their parsing deliberately. DEMO_ADMIN_TOKEN stays on the server. Never put it in the frontend public environment.
6. Prefer synchronous bounded baseline inference for six tiny series. If using 202 background jobs, choose a durable or explicitly recoverable execution path: an in-process FastAPI background task can be lost on restart. Persist queued/running/failed status; add restart reconciliation or label the limitation. Do not leave jobs running forever after a host restarts.
7. Measure Chronos model download/load/inference, memory and startup separately. Load lazily or prewarm an authorized persistent cache. Do not assume GPU availability. If hosting cannot support it within the event, keep verified precomputed outputs with metadata and use the baseline live; disclose that mode.

## Frontend and integration

The prototype project's root is `apps/web`; it builds with the root lockfile and needs no API variable. For a later connected frontend, implement V5's thin same-origin Next.js proxy and configure its server-side API target for each environment after the open proxy/auth design decisions are settled. Do not put API credentials, database URLs or presenter secrets in browser-visible variables. Confirm framework output settings rather than forcing an unrelated output directory.

Use exact HTTPS URLs for demo origins and API targets. Confirm error envelopes, proxy authorization, background forecast polling and plan POSTs through the deployed frontend. The proxy is not authorization by itself: protect reset and any consequential mutations in FastAPI. The public demo should contain synthetic data, conservative request limits and an admin/presenter boundary around reset/adjustment. If there is no time to build a safe presenter reset flow, disable public reset and use a private server-side seed command on the dedicated demo database; document that tradeoff.

Capture a release manifest containing web commit/build URL, API commit/image/revision/URL, schema revision, demo dataset version/hash, forecast run/provider/checkpoint/cutoff, solver version/settings, allowed origins, feature flags and rollback target. Never put secret values in it. A deployment is verified only after actual URL readback and main workflow smoke test.

## Release and rollback

Run full and E2E gates on one stable combined tree, review screenshots, then deploy the authorized preview. Test cold start, known provider failure, scenario replan and protected reset. Preserve the last working web/API pair. Freeze after five clean reset-to-finish rehearsals.

On failure: classify web/API/config/DB/model, restore the known-good frontend/API pair and compatibility flags, then recheck health and the main path. Prefer forward-compatible additive migrations during the event. Rolling back application code does not roll back data/schema automatically. Never run an untested destructive downgrade against the demo database. Restore/reseed only the dedicated demo dataset after verifying scope.

Keep a local runnable release with dependencies and model/cache already present, a short backup recording and screenshots. Rehearse loss of network. State clearly when demonstrating a recording or cached result. Do not rely on a paid feature, cloud review plugin, dynamic workflow or particular GPU being available on demo day.

Provider references: [Vercel environments](https://vercel.com/docs/deployments/environments), [Fly Dockerfile deployment](https://fly.io/docs/languages-and-frameworks/dockerfile/), [Neon branches](https://neon.com/docs/manage/branches). The environment separation, release manifest and rollback policy above are project recommendations.
