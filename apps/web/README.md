# PantryPulse web application

Current main implements the live Overview, Data Explorer and operational inputs, Recommendations, Scenario Lab and Methodology through a thin same-origin API proxy. Root redirects to `/overview`; `/optimization` redirects to `/scenarios`. The historical branch-scoped Vercel `/design-lab` preview is illustrative and independent of this connected source.

## Run

From the root workspace, install with `npm ci` and follow [local installation](../../INSTALLATION.md) or [the existing-demo launch guide](../../docs/setup/LOCAL-LAUNCH-GUIDE.md). The tracked `scripts/demo-local.ps1` prepares the local API/worker/database and matching website environment; it recreates its own API/worker and is not safe to rerun during active work.

For an already configured backend:

```powershell
npm run dev:web
```

The default is loopback port 3000. To select a port manually use `npm run dev --workspace @pantrypulse/web -- --port PORT`, updating the API allowed origin at the same time. Stop any other Next dev server using this checkout first.

## Routes and access

| Route | Role |
| --- | --- |
| `/overview` | Live saved inventory/forecast projection with explicit fixture/error fallback |
| `/data` | Dashboard; `/data/pulse`, `/data/operations`, `/data/inventory`, `/data/inputs` subviews |
| `/recommendations` | Saved plans/comparisons, transfer impact and simulation review |
| `/scenarios` | Forecast/provider selection, frozen scenario revisions, paired comparison, saved outcomes and job controls |
| `/methodology` | Research explanation |
| `/optimization` | Compatibility redirect, not the retired monolithic workspace |
| `/design-lab` | Explicitly illustrative experiment; optional 3D exception |

Shared presenter sign-in/out lives in the sidebar. Optional visitor configuration permits only selected saved API reads; a rendered screen is not permission to compute or mutate. Data input and inventory write/read boundaries remain enforced in FastAPI.

## Configuration and validation

`apps/web/.env.example` documents server-only `PANTRYPULSE_API_ORIGIN` and `PP_TRUSTED_PROXY_TOKEN`. Match the backend's token, actual browser origin and cookie policy. No database, presenter or model credential belongs in browser-public configuration.

Python owns physical quantities, forecasts, objectives and independent verification. The frontend renders typed backend records, preserves units, null/unknown states, native outcomes and actual provider/fallback provenance. Chronos is selectable in Scenario Lab only as an opt-in experimental job; baseline defaults are unchanged.

Run types/lint/build from root, frontend units with `npm run test:unit --workspace @pantrypulse/web`, and contract drift with `npm run contracts:check --workspace @pantrypulse/web`. See [testing](../../docs/testing/README.md) for mocked versus actual connected browser scope, PostgreSQL/Linux prerequisites and the separate CI jobs. Never describe default skipped connected tests as passing the application.
