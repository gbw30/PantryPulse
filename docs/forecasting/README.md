# Forecasting and the path to a complete MVP

> **Current authority:** [Project specification V5](../pantrypulse/SPEC-V5.md). V5 supersedes conflicting V4-era instructions. BD-41 requires explicit `HUB_ONLY` or `HUB_AND_PANTRY` with no default in the full operational scenario; the forecast-only handoff does not select topology. Experimental policies and live integration gates remain open.

Updated: October 24, 2026 (America/New_York).

The forecasting core works offline. A complete PantryPulse MVP still needs the
persisted backend, controlled background computation, validated allocation methods,
operational workflows and connected interface. More forecasting code alone will
not complete the product.

- [MVP completion roadmap](MVP-COMPLETION.md): implementation order, dependencies,
  acceptance checks and the final demonstration.
- [Open decisions and optional improvements](DECISIONS-AND-ENHANCEMENTS.md): choices
  blocking implementation, work that can proceed now and improvements after P0.
- [Implemented core and recorded checks](../pantrypulse/forecasting/IMPLEMENTATION.md):
  what already exists and how to run it.
- [Synthetic evaluation evidence](../pantrypulse/forecasting/evaluation.synthetic-v1.json):
  dataset identity, windows, counts and measured metrics.

## Current position

| Area | Current evidence | Remaining gap |
|---|---|---|
| Forecast preparation/baselines | Immutable internal contracts, exact revision snapshots, calendar gaps, proxy opt-in, seasonal and sparse methods | Public policies, repository adapters and live execution |
| Provider handling | Validation, fallback metadata and unavailable Chronos boundary | Actual pinned Chronos inference and qualification |
| Evaluation | Four synthetic chronological folds; 728 scored observations per strategy | Approved evaluation/selection protocol and evidence on representative data |
| Planning input | Frozen forecast handoff and pure lot projection | Complete frozen operational scenarios and replay |
| Persistence/API | API exposes process health; domain persistence remains scaffolded | PostgreSQL schema, repositories, transactions, public contracts and authorization |
| Jobs | Pure synchronous computation functions | Durable queue/attempts, supervisor, admission, termination and recovery |
| Allocation | Optimization package remains scaffolded | Independent mathematical gate, both methods and feasibility checker |
| Frontend | Development landing page and scaffold smoke test | Dashboard, imports, forecasts, shortages, paired comparison and presenter controls |
| Release gates | Quick-gate configuration exists | Missing full-gate commands/tests, active CI, live E2E and release evidence |

The previous implementation session recorded 44 passing API tests, Ruff checks,
and 182 forecast points across 26 designated series: six fictional beneficiaries,
one hub and two products. Those are offline results. This documentation task does
not rerun tests or establish database, model, solver, UI or deployment readiness.

## Which standards control completion?

Use [V4 research architecture](../architecture/0001-v4-research-first.md), the
[backend specification](../pantrypulse/BACKEND-SPEC.md), its
[accepted decisions/checkpoint](../pantrypulse/BACKEND-DESIGN-CHECKPOINT.md), and the
[forecasting core boundary](../architecture/0003-forecasting-core.md). The detailed
[forecasting implementation plan](<../pantrypulse/forecasting/PantryPulse_V4_Forecasting_Implementation_Plan(1).md>)
provides F-01–F-26 acceptance targets. Existing experimental defaults do not resolve
the checkpoint's OPEN topics.

Some older acceptance/demo documents still describe three sites, six total series,
historical priority labels or older comparator requirements. Reconcile those with
V4 and accepted BD decisions before using them as a release checklist. The target
population is at least six beneficiaries plus hub(s), with two products. The primary
comparison is `CLASSICAL_GP` versus `EGP_PI_INSPIRED` on identical frozen inputs.

This roadmap documents outstanding work. It does not resume paused model/hosting
setup or supplier planning, freeze public contracts, or authorize deployment.
