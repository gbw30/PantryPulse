# Forecasting and the connected application

Updated October 25, 2026. [SPEC-V5](../pantrypulse/SPEC-V5.md) controls product requirements; [current status](../pantrypulse/CURRENT-STATUS.md) separates source, runtime and release evidence.

The [execution plan and PBIs #80–#86](EXECUTION-PLAN.md) refine existing
data/evaluation/Chronos issues #38/#40/#46. The local candidate now includes the
adapter, opt-in jobs and the completed [qualification decision](QUALIFICATION.md):
Chronos remains experimental because full required-scope output and retail
coverage gates fail. See [data-source qualification](DATA-SOURCES.md),
[operator setup](CHRONOS-JOBS.md) and [benchmark reproduction](BENCHMARK-EVALUATION.md).

| Area | Implemented | Remaining qualification |
|---|---|---|
| Preparation/baselines | Immutable history/cutoffs, missingness/proxy handling, seasonal/sparse methods and explicit fallback provenance | Representative pantry/donation accuracy remains unqualified |
| Persistence/API | PostgreSQL forecast publication, presenter/CSRF controls, scoped saved reads, generated contracts and same-origin proxy | Visitor access, general history/import UI and broader production controls |
| Jobs | Durable admission, one active/two waiting operations, Linux containment, deadlines, cancel/retry/recovery and fenced publication | Actual target capability/migration/operator qualification |
| Planning | Committed forecasts feed fully frozen scenarios and verified paired OR results; connected `/optimization` | Broader scenario support, supplier planning and real operations remain separate |
| Chronos | Pinned lazy cache-only adapter, capability-gated jobs/API and actual contained execution/fallback/publication | Strict validation rejects donation quantiles; complete model scope remains unavailable for planning |
| Evaluation | Qualified retail proxy source, frozen splits, rolling/paired metrics, raw-quantile diagnostics and one-time final holdout | Final Chronos availability 92%; insufficient evidence; no pantry/donation or fitted calibration claim |
| Release | Active Linux/PostgreSQL CI and connected browser gates; source-bound review evidence | Actual selected hosted target, manifest, rollback and operational rehearsal |

Baseline forecasts retain `forecast.v1`. The candidate adds opt-in
`forecast.chronos.v1`; planning retains `or-comparison.v2` and `or-allocation.v2`.
Chronos is disabled by default and requires an approved exact checkpoint/profile
matching the actual worker advertisement. A health response or fresh heartbeat
alone is not Chronos readiness. Implementation is local pending review/publication;
no deployed runtime was changed.

Demand and donation remain separate targets. Preserve actual provider/checkpoint/cutoff, missing data and proxy warnings. Raw quantiles are not calibrated intervals or stockout probabilities. Forecast donations never become confirmed inventory, and inventory/policy edits create new scenarios against a saved forecast.

- [Forecast HTTP/auth/proxy flow](../pantrypulse/FORECAST-API-FLOW.md).
- [Connected OR integration and accepted budgets](../optimization/CONNECTED-INTEGRATION.md).
- [Worker startup/recovery](../setup/WORKER-QUEUE.md).
- [Bounded compute and model evidence](../setup/LOCAL-COMPUTE.md).
- [Historical offline core](../pantrypulse/forecasting/IMPLEMENTATION.md) and [synthetic evaluation](../pantrypulse/forecasting/evaluation.synthetic-v1.json).
- [Historical MVP roadmap](MVP-COMPLETION.md) and [decision/enhancement notes](DECISIONS-AND-ENHANCEMENTS.md): interpret unfinished-work claims against current status, not as a rollback of merged functionality.

Full operational scenarios require explicit `HUB_ONLY` or `HUB_AND_PANTRY`, with no default. Source completeness, representative accuracy, model qualification and public release are distinct gates. Supplier scope and paid/public deployment are not resumed merely by a code merge.
