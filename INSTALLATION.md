# Install and run PantryPulse locally

Updated October 25, 2026 for main `647f6a8`. The application is connected; a process-only API or static preview does not establish demo readiness. For the existing laptop video demo, use [the launch guide](docs/setup/LOCAL-LAUNCH-GUIDE.md) rather than creating another database.

## 1. Required tools

| Tool | Repository version / purpose |
| --- | --- |
| Git | Preserve local changes and choose the intended checkout |
| Node.js | `>=24.16.0 <25` |
| npm | `>=11.13.0 <12`, root `package-lock.json` |
| uv | Setup scripts pin 0.11.15; Python dependencies use `apps/api/uv.lock` |
| Python | 3.12; setup selects 3.12.13 |
| Docker Desktop | Running Linux engine for the supported worker/process tests |
| PostgreSQL | Version 16 in the supplied local/CI configurations |
| Chromium | Install through Playwright for browser QA |

Check versions and Docker in PowerShell:

```powershell
git status --short --branch
node --version
npm --version
uv --version
docker info --format '{{.OSType}}'
```

Expected Docker OS: `linux`. Preserve other worktrees and services. Native Windows cannot qualify the Linux process-containment worker, and DLL/security restrictions must not be bypassed to run it.

## 2. Install frozen dependencies

From the selected repository root, with its website stopped:

```powershell
npm ci --no-audit --no-fund
uv sync --frozen --project apps/api --python 3.12.13 --no-extra forecast
npm run test:e2e:install
```

The root workspace owns web installs. Do not create `apps/web/package-lock.json` or run unsolicited dependency upgrades. Optional model dependencies are excluded by default.

The existing [Windows setup script](scripts/setup-windows.ps1) can perform installation with `-WithBrowser` or `-WithContainerApi`; inspect those options before use. Its container API option builds/starts the developer stack and runs a small solver/database probe, not the full connected seeded application. Never replace an active developer API merely to install dependencies.

## 3. Choose one local environment

| Environment | Procedure |
| --- | --- |
| Already prepared video demo | [Launch guide A](docs/setup/LOCAL-LAUNCH-GUIDE.md#a-reopen-the-existing-video-demo); preserve its database and saved results |
| Tracked local connected launcher | `scripts/demo-local.ps1`; persistent `pp-local-*` stack and generated private credentials |
| API/worker plus local database | `compose.yaml` + opt-in `compose.compute.yaml`; explicitly migrate/seed/configure |
| Laptop API/worker with Neon | `compose.forecast.yaml`; explicit private `apps/api/.env` and selected schema |

Example for the tracked launcher, **only after its own worker is idle and the chosen ports are free**:

```powershell
pwsh -File scripts/demo-local.ps1 -WebPort 3030 -ApiPort 8030 -DbPort 55434
```

The script rebuilds the API image and recreates its own `pp-local-api`/`pp-local-worker`, preserving `pp-local-pgdata`. It submits a baseline forecast unless `-NoForecast` is chosen. `-NoWeb` leaves the website stopped. `-Products 4` selects the provided four-product fixture; the default is two products. The source contract supports up to eight, but the launcher accepts only 2 or 4.

`-Reset` deletes that launcher's containers, database volume and generated credentials. It is not a restart or a port-cleanup option. Startup does not automatically refresh an old saved seed to today's planning date.

## 4. Configure a manually selected API/worker

Tracked examples: `apps/api/.env.example`, `apps/api/compute.env.example`, `apps/web/.env.example`. Copy only when destinations are absent; never overwrite private files.

| Setting | Consumer and meaning |
| --- | --- |
| `DATABASE_URL` | Explicit runtime PostgreSQL connection; host and container addresses differ |
| `DATABASE_URL_UNPOOLED` | Direct connection for deliberate migration/new-schema seed commands |
| `PP_DATABASE_SCHEMA` | Exact selected isolated application schema |
| `PP_PRESENTER_USERNAME`, `PP_PRESENTER_PASSWORD_HASH`, `PP_PRESENTER_ORGANIZATION_ID` | Backend-configured presenter and tenant; no shipped default password |
| `PP_ALLOWED_ORIGINS` | Actual browser origin(s), including port |
| `PP_TRUSTED_PROXY_TOKEN` | Matching private API/Next server proxy token |
| `PP_COOKIE_SECURE` | True for HTTPS; false only for local loopback HTTP |
| `PP_VISITOR_ORGANIZATION_ID` | Optional saved catalog/dashboard/shortage reader tenant; no mutation/compute access |
| `PANTRYPULSE_API_ORIGIN` | Next server-only API origin |
| `PP_CHRONOS_ENABLED`, `PP_CHRONOS_REVISION`, `PP_CHRONOS_MODEL_CACHE` | Explicit opt-in experimental model job identity/cache; see Chronos guide |

`FORECAST_PROVIDER`, `SOLVER_TIME_LIMIT_SECONDS`, `NEXT_PUBLIC_API_BASE_URL` and `CORS_ALLOWED_ORIGINS` in historical examples are not the authorities for current job selection, deadlines or the same-origin proxy. Requests/frozen solver settings and the actual source configuration control behavior. No secret belongs in a `NEXT_PUBLIC_*` value.

The [new-schema loader](docs/optimization/CONNECTED-INTEGRATION.md) deliberately creates fictional history, stock and assumptions; it does not fabricate forecasts or solve on startup. Migration head is `ppvp_0007`. Source/API startup never resets a database.

## 5. Open and verify

Use the actual URL printed by the selected launcher. Root opens `/overview`; `/data`, `/recommendations`, `/scenarios` and `/methodology` are implemented. Shared presenter sign-in is in the sidebar. `/optimization` redirects to `/scenarios`.

Verify process health at `/api/v1/health`, then catalog/database access, a real forecast, a frozen scenario and a completed verified comparison. A health response is only `{"status":"ok","scope":"process"}`. Optional visitor reads require explicit configuration. An old running image may not expose current-source routes.

Stop a website with Ctrl+C. Wait for expensive jobs to finish before stopping the selected worker. Local worker shutdown grace is 725 seconds. Preserve volumes and private schema/settings on routine restart. See [launch troubleshooting](docs/setup/LOCAL-LAUNCH-GUIDE.md) for Docker pipes, busy ports, PowerShell variables, stale sessions and extension-induced hydration warnings.

## 6. Validate the selected source

```powershell
npm run test:config
npm run typecheck
npm run lint
npm run test:unit --workspace @pantrypulse/web
npm run contracts:check --workspace @pantrypulse/web
npm run build
```

Full backend and connected browser acceptance require Linux, an isolated `*_test` database and the explicit environment from [the testing guide](docs/testing/README.md). Native Windows skipped/unsupported checks do not count as a full pass. Avoid pointing tests at a presenter's demo database. Existing containers without source mounts may test old copied code.

CI has separate parallel `verify` (two-minute static/unit merge check) and `full` (backend/PostgreSQL/contracts/build/connected browser, no skipped gates). Both matter for release readiness. Do not call a fast green merge check full QA.

## 7. Optional Chronos and UI libraries

The default API image excludes the optional forecast extra. The compute image includes it and supports persistent model storage. To intentionally install it into a native environment:

```powershell
uv sync --frozen --project apps/api --python 3.12.13 --extra forecast
```

Installation alone neither downloads a checkpoint nor enables model jobs. Follow [Chronos jobs](docs/forecasting/CHRONOS-JOBS.md) for an exact pinned cache, API/worker configuration and capability checks. Chronos is integrated but experimental; the [qualification](docs/forecasting/QUALIFICATION.md) did not establish full-scope pantry readiness or calibration. Baselines remain available without it.

The implemented web uses Next/React, Tailwind 4, shadcn/Radix, Recharts, Motion and Lucide. Three.js is confined to the optional design lab exception. Component registries are configured in `apps/web/components.json`; intentionally add source with `npm run ui:add -- COMPONENT` and inspect using `npm run ui:info`. Do not rerun initialization or copy whole catalogues during setup.

For architecture, persistence, hosting and release boundaries, see [current status](docs/pantrypulse/CURRENT-STATUS.md), [contracts](packages/contracts/README.md), [migrations](apps/api/migrations/README.md), [external services](EXTERNAL-SERVICES.md) and [release checklist](docs/pantrypulse/RELEASE-CHECKLIST.md).
