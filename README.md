# PantryPulse

PantryPulse helps a food-bank coordinator forecast upcoming need and compare feasible allocations of limited supplies. It is a simulated planning application for Gator Hack V, October 23–25, 2026; it does not purchase, reserve or dispatch real stock.

## Current implementation

Documentation was reconciled against main **`647f6a8`** on October 25, 2026, through PR #99. Start with [current status](docs/pantrypulse/CURRENT-STATUS.md), [local launch and troubleshooting](docs/setup/LOCAL-LAUNCH-GUIDE.md), and [SPEC-V5](docs/pantrypulse/SPEC-V5.md).

| Screen | Implemented behavior |
| --- | --- |
| [Overview](docs/design/reference/overview.md) — `/overview` | Live inventory/shortage Network Atlas, selected-product/date inspection, chart/table alternatives and explicit fixture/unavailable states |
| [Data Explorer](docs/design/reference/data-explorer.md) — `/data` | Forecast/risk dashboard, Seven-Day Pulse, Operations Board, inventory/lots and presenter data entry |
| [Recommendations](docs/design/reference/recommendations.md) — `/recommendations` | Saved verified plans/comparisons, transfer/impact information and simulation review |
| [Scenario Lab](docs/design/reference/scenario-lab.md) — `/scenarios` | Forecast generation/selection, immutable assumptions/scenarios, both transfer modes, paired methods, saved results and cancel/retry |
| Methodology — `/methodology` | Research and simulated-policy explanation |

The root redirects to `/overview`. `/optimization` is a compatibility redirect to `/scenarios`; the former monolithic workspace is retired. The optional `/design-lab` remains an illustrative experiment, not live planning.

FastAPI owns authorization, historical imports, inventory/receipt/supply services, forecasting, scenario capture and result publication. A thin Next.js same-origin proxy carries selected credentials and intent. PostgreSQL stores the history, ledger, immutable snapshots, jobs and results. One Linux worker lane executes expensive operations sequentially.

The connected planner accepts up to **eight products**, at most twelve beneficiaries and two hubs, seven forecast dates and a one-to-three-day allocation window. The standard seed has six beneficiaries, one hub and two products; an explicit four-product fixture is also supplied. Do not combine meal, bottle or other unlike units into a single quantity.

## Forecasting and comparison

Seasonal-naive and moving-average forecasting are integrated. **Chronos-2 is also integrated as an opt-in experimental provider**, with pinned identity, capability admission, contained execution, truthful fallback and saved provenance. It is disabled by default. The [qualification dossier](docs/forecasting/QUALIFICATION.md) reports insufficient evidence for general model qualification: retail-proxy availability was 92%, and the full synthetic donation scope produced invalid raw quantiles. A working model adapter is not a pantry-accuracy or calibration claim.

Both **classical goal programming** and **EGP-PI-inspired allocation** operate on the same frozen inputs and constraints. Independent replay verifies proposed results. Constraints include conservation, donor protection, expiry/FEFO, routes and capacities; failed/partial methods remain visible. Simulated review does not move stock.

The research basis is Rampazo et al., *An extended goal programming framework incorporating poverty measures: application to food bank logistics* ([DOI](https://doi.org/10.1111/itor.70252)). This is a bounded adaptation with fixed simulated attributes, not a full-paper reproduction or proof of social benefit. Compare common service/unmet/cost/waste metrics rather than unlike native objective values.

## Run locally

Install the pinned tools using [INSTALLATION.md](INSTALLATION.md). To resume the already prepared video demo, follow [section A of the launch guide](docs/setup/LOCAL-LAUNCH-GUIDE.md#a-reopen-the-existing-video-demo); its database, ports and saved scenes are separate from the standard developer stack.

For the tracked local launcher, after confirming its `pp-local-*` worker is idle and selected ports are free:

```powershell
pwsh -File scripts/demo-local.ps1 -WebPort 3030 -ApiPort 8030 -DbPort 55434
```

These are example ports, not automatic selection. The launcher recreates its own API/worker, preserves its database volume and generates credentials under ignored `artifacts/local-demo`. It enables saved visitor reads. **Do not use `-Reset` unless intentionally discarding that launcher's local demo data.** See [local demo procedures](docs/setup/LOCAL-DEMO.md) for restart and resource implications.

## Validation and remaining work

CI runs `verify` (two-minute static/unit merge check) and `full` (Linux/PostgreSQL backend, contract drift, build and connected Chromium, 25-minute ceiling) in parallel. A green `verify` alone does not establish a passing full application. See [testing](docs/testing/README.md) and [the workflow](.github/workflows/pantrypulse-ci.yml). Dated test counts remain evidence for their original source, not a fresh pass for main.

Supplier proposals remain paused. Broader roles, operational reservation/completion, calibrated pantry forecasts, real dispatch and public hosting/release qualification remain unfinished. Product-source integration does not automatically rebuild running containers, migrate databases or refresh the historical Vercel preview.

## Documentation

- [Current source/runtime status](docs/pantrypulse/CURRENT-STATUS.md)
- [Documentation map and audit](docs/pantrypulse/DOCUMENTATION-AUDIT-2026-10-25.md)
- [Installation](INSTALLATION.md), [launch/troubleshooting](docs/setup/LOCAL-LAUNCH-GUIDE.md), [service/setup index](docs/setup/README.md)
- [Specification V5](docs/pantrypulse/SPEC-V5.md), [delivery board](docs/pantrypulse/BOARD.md), [remaining plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md)
- [Forecasting](docs/forecasting/README.md), [Chronos jobs](docs/forecasting/CHRONOS-JOBS.md), [optimization](docs/optimization/README.md)
- [Operational/API runbook](docs/pantrypulse/ALL-API-RUNBOOK.md), [contracts](packages/contracts/README.md), [migrations](apps/api/migrations/README.md)
- [Demo narrative](docs/pantrypulse/DEMO.md), [release checklist](docs/pantrypulse/RELEASE-CHECKLIST.md), [external services](EXTERNAL-SERVICES.md)

Historical task packets, ADRs and experiments retain their source-bound evidence. V5 governs accepted product requirements; current source and generated contracts govern implemented behavior.
