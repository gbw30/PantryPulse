# Current source and runtime status

Updated October 25, 2026. The inspected main baseline is `3251ca6`, through PR #90: baseline forecasting/OR and operational APIs, the live Overview, shared navigation/themes, read-only visitor access and atlas motion. The `feat/forecasting-next` candidate includes that main baseline and adds opt-in Chronos jobs and a completed retail-proxy qualification experiment; see [the dossier](../forecasting/QUALIFICATION.md). SPEC-V5 remains authoritative for product decisions. Dated review reports, task packets and immutable evidence retain their original scope; source changes do not update a running image, migrate a database or deploy a website.

| Area | Implemented source | Limits / next step |
|---|---|---|
| API and persistence | Presenter sessions/CSRF; forecast and operational APIs/imports; immutable assumptions, scenarios, plans, comparisons and result reads; generated OpenAPI/TypeScript; typed dashboard/shortage responses | Presenter access remains required for compute and mutations; optional `PP_VISITOR_ORGANIZATION_ID` permits only saved Overview/catalog reads; general management UI and real dispatch remain separate |
| Worker | Baseline `forecast.v1`, paired `or-comparison.v2`, single `or-allocation.v2`; candidate opt-in `forecast.chronos.v1` on the shared PostgreSQL lane | Capability version 2 and exact model/profile advertisement are required; runtime upgrades remain deliberate |
| Optimization | Classical and research-inspired methods on identical frozen inputs, independent result verification, honest partial outcomes | Bounded simulated policy/domain; no real-world efficacy or automatic stock movement claim |
| Web | Root opens the live `/overview` Network Atlas; shared navigation/themes and draggable panels; connected `/optimization` workspace and thin same-origin proxy; optional illustrative `/design-lab` | Overview preserves incomplete/fallback provenance; static fixture fallback is labelled; configure server-only API origin and matching presenter/proxy settings |
| Migrations/demo | Single source head `ppvp_0007` after #78; explicit loader creates a NEW `ppor_demo_*` schema and simulated history/stock/assumptions | Forecasting follow-up adds no migration; no startup migrations/resets or fabricated results |
| Chronos | Candidate pinned lazy adapter, opt-in jobs/API and real contained model/fallback/downstream OR checks | Full demo donation quantiles invalid; final retail availability 92%; experimental, defaults unchanged; no pantry/donation accuracy or calibration claim |
| Compute | Opt-in `compose.compute.yaml`, bounded Windows builder/tools, persistent model cache; separate Fly API/worker configuration | No Fly login/platform validation/deployment or paid resources established |
| CI | `.github/workflows/pantrypulse-ci.yml` runs Linux/PostgreSQL backend, web/contracts/build and connected browser gates | Skips are rejected; an ignored Vercel build is not application validation |

## VP API integration in the inspected main baseline

[PP-50 review](VP-API-INTEGRATION.md) records VP `35615a6` on main `9df7c51`.
PR #78 merged that operational convergence at `5add760`. It adds inventory/receipt/supply/import/dashboard APIs and
canonical single-method plans/reviews. Main planning contracts and the connected
workspace remain authoritative. New migration head `ppvp_0007` preserves both
planning histories; legacy VP records are read-only and non-executable. This is
source status after merge; no live deployment/migration is implied.

## Execution limits

| Setting | Default | Maximum |
|---|---:|---:|
| Native solver search per method | 120 s | 300 s |
| Whole method | 150 s | 330 s |
| Sequential comparison | 330 s | 690 s |
| Queue wait / waiting jobs | 1,800 s / 2 | Same; one active expensive operation |
| Forecast primary / whole operation | 270 s / 300 s | Same |
| Local worker CPU / RAM | 6 CPU equivalents / 8 GiB | Ceilings, not reservations |
| Fly worker CPU / RAM | 4 shared vCPUs / 8 GiB | API has separate 1-vCPU/1-GiB sizing |

Supervisor drain allows 720 seconds; local container grace is 725 seconds. Fly's 300-second platform shutdown window cannot finish the longest comparison: deliberately drain/confirm an idle lane before deployment. Never stop existing work merely to apply these configuration files.

## Use the right procedure

- [Windows installation](../../INSTALLATION.md) and [quickstart](../setup/WINDOWS-QUICKSTART.md).
- [Local compute and measured evidence](../setup/LOCAL-COMPUTE.md); [worker recovery](../setup/WORKER-QUEUE.md).
- [Connected OR seed/runtime/browser contract](../optimization/CONNECTED-INTEGRATION.md); [forecast/auth/proxy flow](FORECAST-API-FLOW.md).
- [External-service map](../../EXTERNAL-SERVICES.md), [laptop demo](../setup/LOCAL-DEMO.md), [Fly](../setup/FLY.md), and [Vercel preview boundary](../setup/VERCEL.md).
- [Deployment and recovery](DEPLOYMENT.md); [SPEC-V5 acceptance](SPEC-V5.md#16-validation-and-release-acceptance).

Keep private API/web environment files, presenter secrets, model tokens and connection strings outside Git. No secret belongs in a `NEXT_PUBLIC_*` value. Public health proves process liveness only; it does not prove schema, compute, model, browser or release readiness.

Supplier planning, general-purpose import/data-management UI, broader visitor workflows, production reset and real purchasing/reservation/dispatch remain separate work. An implemented demo does not close those gates.
