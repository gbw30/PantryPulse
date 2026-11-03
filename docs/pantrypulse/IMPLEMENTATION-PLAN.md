# Current implementation plan and remaining work

Updated October 25, 2026 for main `647f6a8`. [SPEC-V5](SPEC-V5.md) governs accepted requirements; [current status](CURRENT-STATUS.md) records implementation. Earlier hour-based V4 plans are historical and do not describe today's unfinished backlog.

## Delivered source

- Operational schema/ledger, audited stock/receipt/supply services and bounded atomic history imports.
- Baseline and opt-in experimental Chronos forecasts, frozen inputs, durable publication/reuse and actual-provider provenance.
- Shared Linux lane, deadlines, cancellation/manual retry, partial results and ownership fencing.
- Immutable planning scenarios, both transfer modes and both native allocation methods with independent replay.
- Overview, Data Explorer/Inputs, Recommendations, Scenario Lab, Methodology, shared presenter controls and optional saved visitor reads.
- Up to eight planning products, explicit product creation, standard two-product and optional four-product seed.
- Generated contracts, single migration head, and separate CI verify/full jobs.

## Next work in order

| Priority | Work | Completion evidence |
| --- | --- | --- |
| Release blocker | Run full current-SHA QA rather than relying on static verify | No-skips Linux/PostgreSQL/backend and connected browser evidence, current production build/contracts |
| Release blocker | Reconcile source with the intended running demo | Recorded image/mount/SHA/schema/ports/provider settings; controlled upgrade after idle, then real forecast→scenario→comparison smoke |
| Release blocker | Human visual/accessibility review and five clean rehearsals | Three viewports, keyboard/reduced motion, cold/failure case, saved results and backup recording |
| Release blocker | Freeze actual target, rollback/recovery and disclosures | Manifest, validated target URLs, backup and accurate simulated/model limitations |
| Model follow-up | Qualify nonnegative-output policy and complete pantry/donation scope | Reviewed new experiment/holdout; failures/availability and baseline/fallback remain explicit |
| Model follow-up | Pantry demand/donation data and interval calibration | Representative licensed data, temporal leakage controls, complete expected/scored sets and measured coverage |
| Paused accepted scope | Supplier proposals and dependent offer/budget/lifecycle decisions | Explicit resumption/decisions, implementation and acceptance; do not quietly remove scope |
| Deferred P1 | Broader roles, reservations/completion, richer routing and research fidelity | Separate approved contracts, concurrency/stock-conservation and domain evidence |

Chronos's merged integration does not change its experimental qualification or baseline defaults. The completed retail-proxy study is not proof of pantry accuracy; do not tune against its already inspected final holdout. Simulation reviews do not reserve or dispatch stock.

For original task/decision provenance use [the board](BOARD.md), [research/architecture](../architecture/README.md), [forecasting dossier](../forecasting/QUALIFICATION.md), [OR evidence](../optimization/FINALIZATION.md) and [release checklist](RELEASE-CHECKLIST.md).
