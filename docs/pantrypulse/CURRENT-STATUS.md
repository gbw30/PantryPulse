# Current source and runtime status

Updated October 25, 2026. This is the current navigation/status summary for the source containing PR #75 (baseline API), PR #76 (connected OR), and PR #77 (bounded compute setup). SPEC-V5 remains authoritative for product decisions. Dated review reports, task packets and immutable evidence retain their original scope; a merge does not update a running image, migrate a database or deploy a website.

| Area | Implemented source | Limits / next step |
|---|---|---|
| API and persistence | Presenter sessions/CSRF; baseline forecasts; immutable assumptions, scenarios, comparisons and result reads; generated OpenAPI/TypeScript | Reads currently require presenter access; general imports, visitor access and real dispatch remain outside the accepted demo |
| Worker | `forecast.v1` and `or-comparison.v2` on the shared PostgreSQL lane; Linux containment, cancellation, manual retry and fenced publication | Capability version 2 is required; an older running supervisor must be upgraded deliberately after schema/environment review |
| Optimization | Classical and research-inspired methods on identical frozen inputs, independent result verification, honest partial outcomes | Bounded simulated policy/domain; no real-world efficacy or automatic stock movement claim |
| Web | Root redirects to `/optimization`; connected workspace and thin same-origin proxy; optional illustrative `/design-lab` | Configure server-only API origin and matching presenter/proxy settings; the old branch-scoped Vercel preview remains separate |
| Migrations/demo | Single head `ppor_0005`; explicit loader creates a NEW `ppor_demo_*` schema and simulated history/stock/assumptions | No startup migrations, resets, fake forecasts or fake solver results; old applied revisions remain unchanged |
| Chronos | Full pinned model downloaded and real standalone CPU inference/ten-run benchmark verified on the laptop | Not registered as an application forecast provider; no predictive-accuracy or interval-calibration qualification |
| Compute | Opt-in `compose.compute.yaml`, bounded Windows builder/tools, persistent model cache; separate Fly API/worker configuration | No Fly login/platform validation/deployment or paid resources established |
| CI | `.github/workflows/pantrypulse-ci.yml` runs Linux/PostgreSQL backend, web/contracts/build and connected browser gates | Skips are rejected; an ignored Vercel build is not application validation |

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

Supplier planning, general-purpose import/data-management UI, visitor access, production reset and real purchasing/reservation/dispatch remain separate work. An implemented demo does not close those gates.
