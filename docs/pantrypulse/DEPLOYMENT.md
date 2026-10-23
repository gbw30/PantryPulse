# PantryPulse deployment and recovery

This runbook prepares a deployable candidate. It does not create accounts, buy services, expose a real operational database or deploy without the user's target authorization. Provider menus and limits change; confirm current settings in the named account at setup.

## Environment matrix

| Environment | Frontend/API | Database | Forecast mode | Reset |
|---|---|---|---|---|
| Local dev | 127.0.0.1:3000 / :8000 | dedicated dev DB | baseline first, optional Chronos | demo org only |
| Worker | unique ports per lane | worker DB/schema/Neon branch | fixtures/baseline | worker demo only |
| CI | ephemeral servers | PostgreSQL service | baseline/provider doubles; no model downloads | isolated test seed |
| Preview | Vercel preview + separate API target or explicitly shared demo API | isolated preview/demo DB | cached verified forecast + fallback | presenter protected |
| Judge demo | frozen web/API release pair | dedicated demo DB | prewarmed verified provider/cache, fallback available | presenter protected |

A Vercel preview does not automatically create a matching Python API or database. Record the actual three-way mapping in the release manifest. Preview URL changes require an explicit allowed CORS origin, or route requests through a tested same-origin server proxy. Do not allow every origin to avoid setup work.

## Database and backend

1. Provision a dedicated Neon/PostgreSQL demo database or branch on an authorized account. Use the correct driver URL and TLS mode; store secrets only in server configuration. The template uses postgresql+psycopg with SQLAlchemy; raw tooling may need a plain PostgreSQL URL. Keep migration and runtime URL formats intentional.
2. Apply Alembic migrations as one controlled release step before serving the new API. Test migration on a fresh isolated DB first. Do not run migrations independently from every app worker or frontend preview.
3. Seed the fixed demo organization and verify non-demo organizations are untouched by reset. A reset endpoint scoped only by a user-provided organization ID is insufficient; enforce server-side demo flag and presenter authorization.
4. Deploy FastAPI separately on Railway or an equivalent long-lived Python service. Set root directory/build context to apps/api if using the supplied Dockerfile. Bind to 0.0.0.0 and the provider's PORT. Confirm uv.lock and the installed Python/runtime pair work. API healthz should be cheap; readiness should check DB connectivity/migration compatibility without forcing a model download.
5. Configure DATABASE_URL, APP_ENV, DEMO_MODE, CORS_ALLOWED_ORIGINS, FORECAST_MODEL_ID, FORECAST_DEVICE and SOLVER_TIME_LIMIT_SECONDS. FORECAST_PROVIDER and DEMO_FIXED_DATE are proposed app extensions; implement their parsing deliberately. DEMO_ADMIN_TOKEN stays on the server. Never put it in the frontend public environment.
6. Prefer synchronous bounded baseline inference for six tiny series. If using 202 background jobs, choose a durable or explicitly recoverable execution path: an in-process FastAPI background task can be lost on restart. Persist queued/running/failed status; add restart reconciliation or label the limitation. Do not leave jobs running forever after a host restarts.
7. Measure Chronos model download/load/inference, memory and startup separately. Load lazily or prewarm an authorized persistent cache. Do not assume GPU availability. If hosting cannot support it within the event, keep verified precomputed outputs with metadata and use the baseline live; disclose that mode.

## Frontend and integration

Set Vercel project root to apps/web, build with the locked package's build script, and configure NEXT_PUBLIC_API_BASE_URL for each environment. Its value is public and typically embedded at build time; changing it requires a rebuild. Only API URL belongs there, never database credentials. Confirm framework output settings rather than forcing an unrelated output directory.

Use exact https URLs for demo origins and API targets. Confirm error envelopes, preflight behavior, background forecast polling and plan POSTs through the deployed frontend. CORS is not authentication: protect reset and any consequential mutations server-side. The public demo should contain synthetic data, conservative request limits and an admin/presenter boundary around reset/adjustment. If there is no time to build a safe presenter reset flow, disable public reset and use a private server-side seed command on the dedicated demo database; document that tradeoff.

Capture a release manifest containing web commit/build URL, API commit/image/revision/URL, schema revision, demo dataset version/hash, forecast run/provider/checkpoint/cutoff, solver version/settings, allowed origins, feature flags and rollback target. Never put secret values in it. A deployment is verified only after actual URL readback and main workflow smoke test.

## Release and rollback

Run full and E2E gates on one stable combined tree, review screenshots, then deploy the authorized preview. Test cold start, known provider failure, scenario replan and protected reset. Preserve the last working web/API pair. Freeze after five clean reset-to-finish rehearsals.

On failure: classify web/API/config/DB/model, restore the known-good frontend/API pair and compatibility flags, then recheck health and the main path. Prefer forward-compatible additive migrations during the event. Rolling back application code does not roll back data/schema automatically. Never run an untested destructive downgrade against the demo database. Restore/reseed only the dedicated demo dataset after verifying scope.

Keep a local runnable release with dependencies and model/cache already present, a short backup recording and screenshots. Rehearse loss of network. State clearly when demonstrating a recording or cached result. Do not rely on a paid feature, cloud review plugin, dynamic workflow or particular GPU being available on demo day.

Provider references: [Vercel environments](https://vercel.com/docs/deployments/environments), [Railway FastAPI](https://docs.railway.com/guides/fastapi), [Neon branches](https://neon.com/docs/manage/branches). The environment separation, release manifest and rollback policy above are project recommendations.
