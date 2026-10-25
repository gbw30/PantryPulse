# Forecasting execution plan and backlog

Updated October 25, 2026. Owner: **@GestebanFalcon**. Inspected baseline:
`main` at `5add76008faddae08a969514c2e827299bc84d50` (through PR #78).
Status: **local implementation and qualification decision complete** on
`feat/forecasting-next`, pending review/publication. The user
authorized two coordinated agents through #86. [Protocol v1](QUALIFICATION-PROTOCOL.md)
freezes the shared contracts. Local implementation and measured acceptance remain
distinct from merged/deployed status and predictive qualification.

## Existing work and issue ownership

The repository already has a forecasting roadmap, an evaluation service, and broad
GitHub work packages. The older [completion roadmap](MVP-COMPLETION.md) and
[decision notes](DECISIONS-AND-ENHANCEMENTS.md) retain historical scope and status.
This plan refines their remaining work against integrated main. SPEC-V5 remains
the product authority; proposed protocol choices below become execution contracts
through FC-01 rather than implicitly changing production policy.

| Existing owner | Scope retained | New child PBIs |
|---|---|---|
| [#9 / PP-31](https://github.com/gbw30/PantryPulse/issues/9) | Forecast contracts and outstanding policy decisions | FC-01 supplies a bounded review packet |
| [#38 / PP-55](https://github.com/gbw30/PantryPulse/issues/38) | Data-source qualification and fixtures | FC-02, FC-03 |
| [#40 / PP-56](https://github.com/gbw30/PantryPulse/issues/40) | Chronological evaluation and benchmark evidence | FC-01, FC-03, FC-06, FC-07 |
| [#46 / PP-62](https://github.com/gbw30/PantryPulse/issues/46) | Actual pinned Chronos integration and qualification | FC-01, FC-04, FC-05, FC-07 |
| [#70 / P1-FORECAST](https://github.com/gbw30/PantryPulse/issues/70) | Calibrated uncertainty, covariates and later model improvements | Remains the existing follow-up; no duplicate issue |
| [#48 / backlog index](https://github.com/gbw30/PantryPulse/issues/48) | Repository dependency/ownership index | Links this staged forecast work |

All seven PBIs are assigned to @GestebanFalcon and have explicit implementation
boundaries. Other developers should coordinate on the relevant issue before
starting overlapping work. Existing API, data, worker and frontend owners retain
their shared-service responsibilities; an assignee is not an exclusive claim to
every file named by a broad parent issue.

## Reuse the working system

Main already includes baseline providers, history preparation, output validation,
chronological backtesting, paired metrics, immutable planning handoff, persisted
forecast APIs, presenter access, the Next proxy, durable Linux jobs, cancellation,
retry, fenced publication and the connected OR workspace. PRs #75–#78 integrate
these pieces. Start implementation from current main, not `bed0854` on the old
forecasting branch.

At the inspected main baseline, the Chronos application adapter reported
unavailable and `BaselinePolicy` accepted only seasonal naive and moving average.
FC-04 now supplies a real pinned adapter locally; its [measured smoke](evidence/chronos-adapter-review.md)
accepted 12 demand series and rejected all 14 donation series for negative raw
quantiles under the unchanged output policy. This is execution evidence, not
full-scope planning readiness or a forecast accuracy report. FC-05 owns job/API
integration and preserves the baseline contract separately.

The existing 90-day synthetic fixture supplies 26 demand/donation series and four
backtest origins. Reuse it for regression and full-demo plumbing. Its deliberately
weekly pattern does not establish representative accuracy. The evaluation CLI's
old `postgres_api_jobs=NOT_IMPLEMENTED`/`OFFLINE_ONLY` qualification fields describe
the historical experiment; update their interpretation when extending reports,
without rewriting immutable historical evidence.

## Ordered PBIs and dependencies

| PBI | Deliverable | Dependencies | Status |
|---|---|---|---|
| [FC-01 / #80](https://github.com/gbw30/PantryPulse/issues/80) | Freeze provider contracts and experiment protocol | Existing code/spec review | Protocol v1 written and mirrored in issue |
| [FC-02 / #81](https://github.com/gbw30/PantryPulse/issues/81) | Qualify pantry sources and FreshRetailNet fallback | FC-01 for final acceptance; source reconnaissance can start now | Retail proxy sample/files qualified locally; pantry/donation gap remains |
| [FC-03 / #82](https://github.com/gbw30/PantryPulse/issues/82) | Versioned dataset adapters, cohorts and split manifests | FC-01, FC-02 | Local 100-series pilot/manifests; 25 tests passed; final truth sealed |
| [FC-04 / #83](https://github.com/gbw30/PantryPulse/issues/83) | Implement pinned Chronos adapter | FC-01; existing synthetic fixture is sufficient to start | Local implementation and real smoke; agent stopped |
| [FC-05 / #84](https://github.com/gbw30/PantryPulse/issues/84) | Connect Chronos to jobs/API and qualify containment | FC-01, FC-04; coordinate #29 and #44 owners | Local integration and actual contained HTTP/PostgreSQL/downstream OR checks passed |
| [FC-06 / #85](https://github.com/gbw30/PantryPulse/issues/85) | Extend rolling evaluation and publish comparable reports | FC-01, FC-03; actual Chronos report also needs FC-04 | Implemented; frozen 100-series/four-fold real validation executed |
| [FC-07 / #86](https://github.com/gbw30/PantryPulse/issues/86) | Final holdout, operational acceptance and scoped model decision | FC-02, FC-03, FC-05, FC-06 | One final opening completed; experimental / insufficient evidence, defaults unchanged |

See [the final dossier](QUALIFICATION.md) for exact evidence and limits: 1,312
backend tests passed with zero skips; actual jobs/fallback/OR handoff passed;
final retail availability was 92%, below the predeclared qualification threshold.
Completing these implementation milestones does not qualify full-scope Chronos
planning, representative pantry/donation accuracy, calibration or deployment.

The data track (FC-02 → FC-03 → baseline FC-06) and model track
(FC-04 → FC-05) can proceed independently after FC-01. They join at FC-07.
Do not make the entire evaluation parent a prerequisite for writing the adapter:
that would create an unnecessary cycle. Real-model accuracy acceptance still
requires the evaluated data and protocol. Fitted calibration and automatic model
selection are later work under #70, not hidden acceptance requirements for the
first functioning adapter.

## Milestone exit criteria

| Milestone | Required evidence |
|---|---|
| M0: contracts agreed | Checkpoint/settings identity, missing-data/output policy, frozen temporal protocol and explicit operational/quality criteria; resolve or record OPEN-15/18 decisions |
| M1: benchmark ready | Actual source-sample findings, licensing/attribution, target/unit limitations, pinned adapter and immutable development/validation/holdout manifests |
| M2: adapter works | Actual full-demo inference, exact date/series/provider mapping, meaningful edge cases and cold/warm resource measurements |
| M3: application works | Real API → PostgreSQL → contained Linux worker → saved result → frozen scenario; bounded fallback/cancellation/publication and unchanged baseline/OR behavior |
| M4: comparisons reproduce | Paired and full-coverage baseline/Chronos reports, failures/cohorts, leakage tests and uncalibrated quantile diagnostics where available |
| M5: qualification decided | Untouched holdout, operational evidence and a scoped qualified / experimental / rejected / insufficient-evidence decision; negative results retained |
| Later: calibrated improvements | Existing #70; fitted intervals, stronger intermittent methods, covariates or ensembles require separate validation |

## Chronos implementation contract to settle in FC-01

- Preserve seven future local dates, required scope, actual provider identity,
  requested-versus-proxy basis, and point/mean/median distinctions. Start with
  univariate inputs; covariates need a typed availability/version contract.
- Retain missing values. Test native support for gaps, all-missing and short
  histories; do not introduce blanket imputation to make inference succeed.
- Resolve the standalone runner's negative raw quantiles versus integrated
  nonnegative-output validation. No silent clipping or replacement by zero.
- Freeze checkpoint revision, package, adapter/preprocessing version, grouping and
  relevant inference settings before admission. Include them in reuse identity;
  a changed model must not reuse old-model results accidentally.
- Load heavy dependencies/model only inside controlled inference. Verify whether
  model reuse/batching needs a provider-local extension to the current per-series
  protocol; measure full-demo cost rather than repeatedly loading per series.
- Extend or version `forecast.v1` and worker capabilities deliberately. Preserve
  old saved results and baseline operation when Chronos dependencies are absent.
- Keep primary/operation deadlines at 270/300 seconds, the shared forecasting/OR
  lane, cancellation, ownership fences and atomic publication. Any multi-provider
  fallback schedule needs an explicit bounded design; do not nest unconstrained
  retries inside a worker step.
- A model smoke proves execution. The full job journey proves integration. Neither
  alone proves useful predictions or calibrated intervals.

## Data acquisition and adaptation

See [source research and acceptance checklist](DATA-SOURCES.md). First preference
is an authorized anonymized daily pantry/food-bank export with stable site/product
and unit definitions, requested versus fulfilled demand, actual received
donations, opening/reporting coverage, and revisions/as-of timestamps where
available. Prefer at least six months and ideally a year or more for seasonal
coverage; record shorter-history limits rather than fabricating coverage.
Access to such an export has not been established; no partner outreach is part of
this planning task.

If no suitable direct source qualifies in the bounded sourcing milestone,
FreshRetailNet-50K is the preferred public retail-proxy candidate to inspect.
The adapter must retain its normalized source units and stockout masks. Compare
observed sales as a clearly named proxy task; an uncensored-days diagnostic can
supplement it. Latent demand during stockouts is not observed truth. No store-to-
pantry renaming, fabricated requested demand, fake donation histories, or direct
conversion to stock units is permitted by this plan.

Proposed execution sizes are a deterministic 100-series pilot, a 1,000-series
expanded run, and an optional full run after measuring cost. These are offline
benchmark cohorts, not one production job exceeding its scope/resource bounds.
Final choices and seeds are frozen in FC-01/FC-03 before inspecting model scores.
Missing real donation data remains a separate explicit qualification gap.

## Evaluation protocol to freeze before comparison

1. Pin source revision/checksums and retain native target basis and unit. Keep
   simulated pantry, retail proxy and any direct pantry/donation results separate.
2. Select cohorts using training data only. Preserve original train/eval dates
   where suitable; verify actual lengths before deciding the folds. Use seven-day
   rolling origins and keep the final holdout separate from development/validation.
3. Fit transforms, recovery, tuning, selection and any later calibration within
   training/validation only. Never use final-period values or realized future
   weather, stockouts or corrections as inference inputs. If historical revision
   availability is missing, label retrospective event-time evaluation honestly.
4. Score identical origin/series/date/unit/basis keys. Report both full coverage
   and common paired sets; preserve unavailable/missing/censored/basis-mismatch,
   fallback and failure counts. A dropped hard series is not an accuracy gain.
5. Reuse MAE, signed bias and WAPE, including null zero-denominator/no-pair cases.
   Add per-horizon/per-series summaries, counts and dependence-aware uncertainty
   where supported. Separate requested strategy from actual fallback provider.
6. For raw quantiles report pinball loss, empirical coverage and interval width
   with counts. Label them uncalibrated; sums of daily p90 are not joint 90% bounds.
7. Freeze candidate settings and predeclared criteria before the one final
   holdout run. Publish worse/inconclusive Chronos outcomes. Retuning after seeing
   the final holdout requires a new experiment/holdout and disclosure.
8. Record dataset/model/code/fold/settings hashes, runtime and memory, predictions,
   metrics, commands and scope. Do not call retail-only results pantry-qualified.

## Implementation and acceptance practice

Each issue records its base SHA, branch and owned paths before coding. Use a new
branch from updated main (for example `feat/forecasting-next`, with small PBI PRs).
Coordinate shared worker/schema/generated-contract edits rather than giving
multiple implementations ownership of the same integration point.

Use deterministic adapter/arithmetic/leakage tests in normal CI; run actual model
and Linux/PostgreSQL/browser gates explicitly when their environment is available.
Reuse existing baseline and OR regression coverage. Heavy model benchmarks do not
belong on every unit-test run. Verify links and Markdown for this planning change;
it does not require rerunning the application suite.

This backlog does not deploy a service, migrate an existing database, contact
partners, change OR objectives, enable automatic provider selection or perform
real inventory/dispatch operations. Parent issues remain open until their complete
acceptance is evidenced. Operational readiness, accuracy, calibration and release
readiness remain separate recorded outcomes.
