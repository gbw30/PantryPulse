# Current source and runtime status

Updated October 25, 2026 against main **`647f6a8ccdb210de96204a314b62ae7d3d6b2701`**, through PR #99. This supersedes scaffold-only, baseline-only, branch-candidate and disabled-view implementation statements in older documents. It does not retroactively extend historical evidence or change accepted product decisions.

## Implemented source

| Area | Current source | Limits |
| --- | --- | --- |
| Web | `/overview`, `/data` with pulse/operations/inventory/inputs subviews, `/recommendations`, `/scenarios`, `/methodology`; shared presenter controls/themes | Root → Overview; `/optimization` → Scenario Lab. Settings and broader product workflows are separate |
| API | Forecast/catalog/jobs, inventory, receipts/reconciliation, expected supplies, atomic demand/coverage imports, product creation, saved scenarios/comparisons/plans/reviews, dashboard and shortages | See generated OpenAPI for exact contracts. Historical receipt/import facts do not implicitly become physical stock |
| Access | Presenter sessions, server-bound tenant, same-origin proxy, Origin/CSRF and bounded idempotent mutations | Optional `PP_VISITOR_ORGANIZATION_ID` permits saved forecast-catalog/dashboard/shortage reads only; it does not grant compute, jobs, planning or stock APIs |
| Forecasts | Seasonal naive, moving average and opt-in experimental pinned Chronos; actual-provider, fallback, completeness and saved readiness | Chronos disabled by default; incomplete results remain readable but cannot freeze planning scenarios |
| Worker | `forecast.v1`, `forecast.chronos.v1`, `or-comparison.v2`, `or-allocation.v2`; one active expensive operation, two waiting | Linux containment/capability matching required. CPU/RAM ceilings do not reserve host resources |
| Planning | Frozen operational snapshots, both transfer modes, classical and research-inspired methods, independent verification, partial outcomes, immutable saved reads/revisions | Up to 8 products, 12 beneficiaries, 2 hubs, 256 lot/arrival records, 7 dates, one first-day dispatch batch in a 1–3-day allocation window; numeric/domain checks may reject unsupported inputs |
| Persistence | Single migration head `ppvp_0007`; explicit new-schema fictional-history/stock seed | No startup migrations/reset/fake computed results; legacy VP records are read-only and non-executable |
| Local launcher | `scripts/demo-local.ps1`: 2- or 4-product fixture, persistent `pp-local-pgdata`, visitor read configuration and saved credentials | Selected ports must be free; API/worker are recreated by the script. `-Reset` is destructive to that launcher's demo |
| CI | Parallel `verify` and `full` jobs; full rejects skipped backend/browser gates | Fast static merge check is not full product/release acceptance |

The earlier prototype-preview Vercel deployment is branch-specific; its existence is not evidence that current main is deployed. Fly configuration remains prepared rather than a verified public deployment.

## Chronos qualification

PR #93 merged the provider/job/evaluation follow-up. The [dossier](../forecasting/QUALIFICATION.md) records real contained model execution, incomplete donation output, whole-batch moving-average fallback, and downstream verified OR. This is no longer merely a standalone model runner or unmerged provider candidate.

The frozen retail-proxy experiment yielded 644/700 valid Chronos points (92%). Conditional paired MAE improved on that subset, but availability missed the predeclared requirement; the decision is **INSUFFICIENT_EVIDENCE / experimental**, with no production-default switch. Pantry/donation predictive accuracy and calibrated uncertainty are not established. Invalid quantiles are rejected without clipping; a moving-average fallback is labelled MOVING_AVERAGE.

## Execution limits

| Setting | Default | Maximum |
| --- | ---: | ---: |
| Native solver search per method | 120 s | 300 s |
| Whole method | 150 s | 330 s |
| Sequential comparison | 330 s | 690 s |
| Forecast primary / whole operation | 270 s / 300 s | Same |
| Queue wait / waiting jobs | 1,800 s / 2 | Same; one active operation |
| Local worker CPU / RAM ceiling | 6 CPU equivalents / 8 GiB | Additional API/database/OS headroom needed |

Supervisor drain allows 720 seconds; local grace is 725. Fly's 300-second shutdown window requires an already drained/idle lane. Never interrupt unrelated work to apply a source/configuration update.

## Source, running environment and local video materials

The prepared `presenter_demo_20261025_135726` environment and its VIDEO 01–03 records are machine-local artifacts. It used copied API/worker images from an earlier source; current source does not prove that runtime has the newer model, product, visitor or frontend behavior. Source-bind mounts in the separate `pp-local-*` launcher behave differently. Record image/mount, commit, schema and URL before applying a fix.

The former video shortcuts in an untracked `apps/web/src/app/optimization/workspace.tsx` are not an active current-main route: `/optimization` redirects to `/scenarios`. Saved database records persist, but the optional public video manifest is not automatically consumed by the new screens. Do not promise those shortcut buttons without verifying that particular frontend.

Use [the launch guide](../setup/LOCAL-LAUNCH-GUIDE.md) for the exact prepared paths, existing-demo restart, automatic new-demo ports and coordinated existing-demo port repair. The local recipe helpers under ignored `artifacts/demo-recipe` are not included in a fresh Git clone.

## Evidence and release status

Checked-in [OR finalization](../optimization/FINALIZATION.md), [forecast qualification](../forecasting/QUALIFICATION.md) and task packets preserve their recorded commits, commands and counts. The source audit is documentation validation, not a fresh complete application test. CI `verify` has a two-minute ceiling; `full` separately exercises PostgreSQL/Linux, contracts, build and real connected Chromium. Inspect both jobs on the exact release SHA. PR #99 cancels superseded PR runs while allowing main runs to finish; the local `647f6a8` builder-width commit is additional source, not proof that the upstream full job passed.

Supplier planning remains paused. General production operations, reservation/completion, broader roles, representative pantry forecasting, calibrated intervals, public target smoke, a frozen release manifest and five clean rehearsals remain separate. [SPEC-V5 §16](SPEC-V5.md#16-validation-and-release-acceptance) and [release checklist](RELEASE-CHECKLIST.md) govern sign-off.

## Read next

- [Installation](../../INSTALLATION.md), [launch guide](../setup/LOCAL-LAUNCH-GUIDE.md), [local demo](../setup/LOCAL-DEMO.md), [setup index](../setup/README.md)
- [Testing](../testing/README.md), [API runbook](ALL-API-RUNBOOK.md), [contracts](../../packages/contracts/README.md), [migrations](../../apps/api/migrations/README.md)
- [Forecast/model jobs](../forecasting/CHRONOS-JOBS.md), [connected planning](../optimization/CONNECTED-INTEGRATION.md), [deployment](DEPLOYMENT.md), [documentation audit](DOCUMENTATION-AUDIT-2026-10-25.md)
