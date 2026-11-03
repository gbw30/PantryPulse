# Railway FastAPI setup

> Historical alternative: superseded by the [Fly.io external services installation guide](../../EXTERNAL-SERVICES.md). Railway is not part of the selected MVP setup; these instructions are retained for reference.

Purpose: host the Python API and OR-Tools runtime. This guide uses the existing Dockerfile, not a new Python build system. Complete [GitHub](GITHUB.md) and [Neon](NEON.md) first.

## Manual account and repository connection

1. Sign in at https://railway.com and select the intended workspace.
2. Review available plans, resource limits and spend controls.
3. Create a project for the synthetic demo and connect the existing gbw30/PantryPulse GitHub repository.
4. Select the reviewed branch/commit. Repository connection can trigger an initial deployment; wait for configuration/verification before sharing its address.
5. Create/use one API service named pantrypulse-api. Do not add a second PostgreSQL service: Neon is the selected hosted database.

GitHub imports use pushed files, not local uncommitted work. The setup described here has not been executed against a Railway account.

## Build and networking settings

| Setting | Project value |
|---|---|
| Service root directory | /apps/api |
| Builder | Dockerfile, detected as Dockerfile within that root |
| Docker context | apps/api contents |
| Healthcheck path | /api/v1/health |
| Target/application port | Follow the start-command configuration below |
| Region | Close to the selected Neon region |

Root-directory behavior is documented in [Railway monorepos](https://docs.railway.com/deployments/monorepo); detection is documented in [Dockerfile builds](https://docs.railway.com/builds/dockerfiles). Do not use the repository root as Docker context with the current relative COPY statements.

The current Docker CMD binds to 0.0.0.0:8000. For a platform-selected PORT, set this explicit **Railway Start Command** in the dashboard:

```sh
/bin/sh -c 'exec uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"'
```

Paste this in Railway, not in a local PowerShell prompt. Docker command overrides need an explicit shell for variable expansion; see [start commands](https://docs.railway.com/deployments/start-command).

Alternatively, keep the existing CMD and explicitly configure the service/public-domain target to port 8000. Use one consistent configuration and verify it in deployment logs. EXPOSE by itself does not make an application listen on a provider-selected port.

## Variables

| Variable | Value / status |
|---|---|
| DATABASE_URL | Pooled Neon connection in postgresql+psycopg format |
| APP_ENV | demo; proposed configuration, not consumed yet |
| DEMO_MODE | true; proposed configuration, not consumed yet |
| CORS_ALLOWED_ORIGINS | JSON list of exact Vercel origins; middleware not implemented yet |
| FORECAST_PROVIDER | seasonal-naive; adapter not implemented yet |
| FORECAST_MODEL_ID | amazon/chronos-2; optional future adapter |
| FORECAST_DEVICE | cpu initially; validate before inference |
| SOLVER_TIME_LIMIT_SECONDS | 5; future domain solver setting |
| DEMO_FIXED_DATE | 2026-10-24; future deterministic seed setting |

Only the runtime smoke script currently reads DATABASE_URL; API settings loading remains pending. Setting DEMO_MODE does not by itself protect an endpoint. Never put database/model credentials in browser variables or Docker build arguments.

The Docker image excludes optional forecast dependencies and includes development test tooling. It is a development scaffold, not a hardened production image.

## Deploy and verify the scaffold

Apply the settings and deploy the selected commit. Confirm build logs use apps/api/Dockerfile. Generate an HTTPS domain under Settings → Networking → Public Networking; see [Railway networking](https://docs.railway.com/networking/public-networking). Use the actual returned address.

From PowerShell, replacing the illustrative hostname:

```powershell
Invoke-RestMethod 'https://YOUR-API-HOST/api/v1/health'
```

Expected JSON is {"status":"ok","scope":"process"}. Open /docs to inspect the implemented routes.

From a shell in the deployed API container:

```sh
uv run --frozen python scripts/check_runtime.py --database
uv run --frozen pytest
```

These check dependencies, database connectivity and scaffold health, not a complete allocation platform. No migration/pre-deploy command should be configured until Alembic revisions exist.

## Complete integration after Vercel

Set CORS_ALLOWED_ORIGINS to the actual frontend origins, with no paths/trailing slash, and redeploy after implementing settings parsing/CORSMiddleware. The current app has no CORS middleware, so a successful curl/health response does not establish browser integration.

Then validate browser requests, structured errors, pending/result states and the paired solver workflow when implemented. Public reset/adjustment endpoints need a presenter boundary before exposure.

## Completion checklist

- [ ] Correct root, Dockerfile, commit, region and port verified.
- [ ] HTTPS health returns process scope.
- [ ] Deployed container connects to the intended Neon database.
- [ ] Actual API URL supplied to Vercel.
- [ ] CORS/settings and domain features recorded as pending or tested.

