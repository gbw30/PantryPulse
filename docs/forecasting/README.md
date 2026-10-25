# Forecasting and the connected application

Updated October 25, 2026. [SPEC-V5](../pantrypulse/SPEC-V5.md) controls product requirements; [current status](../pantrypulse/CURRENT-STATUS.md) separates source, runtime and release evidence.

Next work: [forecasting execution plan and owned PBIs #80–#86](EXECUTION-PLAN.md)
refines existing data/evaluation/Chronos issues #38/#40/#46. See
[evaluation data-source research](DATA-SOURCES.md) for the direct-pantry sourcing
requirements and the proposed FreshRetailNet-50K retail benchmark.

| Area | Implemented | Remaining qualification |
|---|---|---|
| Preparation/baselines | Immutable history/cutoffs, missingness/proxy handling, seasonal/sparse methods and explicit fallback provenance | Representative chronological accuracy/selection evidence |
| Persistence/API | PostgreSQL forecast publication, presenter/CSRF controls, scoped saved reads, generated contracts and same-origin proxy | Visitor access, general history/import UI and broader production controls |
| Jobs | Durable admission, one active/two waiting operations, Linux containment, deadlines, cancel/retry/recovery and fenced publication | Actual target capability/migration/operator qualification |
| Planning | Committed forecasts feed fully frozen scenarios and verified paired OR results; connected `/optimization` | Broader scenario support, supplier planning and real operations remain separate |
| Chronos | Pinned full model downloaded and standalone real CPU smoke/benchmark executed | Application adapter registration, deadline/fallback/publication integration and forecast accuracy/calibration |
| Release | Active Linux/PostgreSQL CI and connected browser gates; source-bound review evidence | Actual selected hosted target, manifest, rollback and operational rehearsal |

Production contracts are `forecast.v1` and `or-comparison.v2`. The application forecast contract still offers baselines; it does not advertise the standalone model exercise as a live model provider. A health response or fresh heartbeat is not Chronos readiness.

Demand and donation remain separate targets. Preserve actual provider/checkpoint/cutoff, missing data and proxy warnings. Raw quantiles are not calibrated intervals or stockout probabilities. Forecast donations never become confirmed inventory, and inventory/policy edits create new scenarios against a saved forecast.

- [Forecast HTTP/auth/proxy flow](../pantrypulse/FORECAST-API-FLOW.md).
- [Connected OR integration and accepted budgets](../optimization/CONNECTED-INTEGRATION.md).
- [Worker startup/recovery](../setup/WORKER-QUEUE.md).
- [Bounded compute and model evidence](../setup/LOCAL-COMPUTE.md).
- [Historical offline core](../pantrypulse/forecasting/IMPLEMENTATION.md) and [synthetic evaluation](../pantrypulse/forecasting/evaluation.synthetic-v1.json).
- [Historical MVP roadmap](MVP-COMPLETION.md) and [decision/enhancement notes](DECISIONS-AND-ENHANCEMENTS.md): interpret unfinished-work claims against current status, not as a rollback of merged functionality.

Full operational scenarios require explicit `HUB_ONLY` or `HUB_AND_PANTRY`, with no default. Source completeness, representative accuracy, model qualification and public release are distinct gates. Supplier scope and paid/public deployment are not resumed merely by a code merge.
