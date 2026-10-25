# Forecasting implementation and qualification decision

October 25, 2026. Workstream #80–#86, branch `feat/forecasting-next`, originally based on
main `5add760` and now integrated with main `f7a921a` (through PRs #91–#92).
Implementation through the qualification decision is complete
locally; review/publication and deployment are separate. Chronos stays
**experimental / insufficient evidence**, with no provider-default change.

## What was implemented

- Frozen provider/output/evaluation contracts under
  [protocol v1](QUALIFICATION-PROTOCOL.md).
- Qualified, checksum-pinned FreshRetailNet-50K acquisition, source-native
  adapters and a deterministic 100-series pilot with immutable temporal splits.
- Actual pinned Chronos-2 CPU inference, lazy cache-only loading, explicit gaps,
  real quantiles, strict validation and provider/checkpoint provenance.
- Opt-in `forecast.chronos.v1` jobs/API/workspace selection, live model/profile
  capability matching, immutable reuse/retry identity and atomic publication.
- Reusable rolling evaluation, complete failure/coverage accounting, paired
  metrics, quantile diagnostics and series-cluster uncertainty estimates.
- A guarded one-time final holdout and an explicit qualification decision.

The two agents first worked independently on data and the adapter. Both stopped
before one owner changed shared job/API code. That owner stopped before the
evaluation agent resumed. Both were stopped for the final combined gates and the
single root-owned holdout opening. No concurrent model/domain runs were used for
the final qualification.

## Data and experimental scope

The official FreshRetailNet files were pinned to revision
`c374e85975c82816c495acfa904cc55ab14a47d3`, with exact raw checksums, source-native
normalized retail-sales units and stockout annotations preserved. The 100-series
cohort was selected from training IDs with seed 20261025. Four seven-day validation
origins precede the upstream June 26–July 2, 2024 final week.

Moving average was selected using baseline-only validation MAE before opening
final truth. The model, dependencies, code files, data/cohort/fold identities,
raw validation predictions and selected baseline were frozen. The exclusive
opening journal confirms one final run. No settings, output policy, cohort or
selection rule changed after seeing the final week.

The first validation run was retained; a second freeze followed a Windows-only
RSS import portability fix. Both have identical predictions and metrics. This
was an infrastructure revision before any final truth, not model tuning.

This is a **retail observed-sales proxy**, not observed latent demand or pantry
need. Stockout-day sales are censored. Uncensored diagnostics are conditional on
realized availability; missing pantry-demand/donation truth remains a distinct gap.
No imputed labels, invented donations, inverse stock-unit conversion or future
covariates were introduced. Model-pretraining overlap remains unknown.

## Final holdout result

Each method had 700 expected points across 100 series and seven dates. Fallback
was disabled for model comparison. Quantities below use normalized retail units.

| Strategy | Available / expected | MAE on all available points | MAE on the identical 644-point intersection |
|---|---:|---:|---:|
| Seasonal naive | 700 / 700 | 0.473759 | 0.439644 |
| Moving average | 700 / 700 | 0.439680 | 0.422079 |
| Chronos-2 | 644 / 700 | 0.394295 | 0.394295 |

Chronos's available-point MAE is approximately **6.58% lower** than the frozen
moving-average baseline on the same points. The 500-replicate series-cluster
bootstrap MAE difference is -0.027784, with a 95% interval approximately
[-0.055209, -0.000284], covering 92 paired series. This conditional result does
not account for the missing model predictions as if they were successes.

**Eight series / 56 points failed strict provider-output validation.** Model
availability is 92%, below the predeclared 99% requirement, and only 92 series
contribute paired predictions versus the required 100. The frozen quality
decision is therefore **INSUFFICIENT_EVIDENCE**, not general model superiority.

On valid model points, the nominal raw 80% interval covered approximately 75.78%
of outcomes, with mean normalized width 1.16440. These are uncalibrated diagnostics;
they do not establish pantry stockout probabilities or joint multi-day coverage.
The final execution took 10.24 seconds with peak RSS 988,328 KiB in the recorded
CPU-float32/two-thread environment.

Full scope, hashes, failures, cohorts, horizon metrics and runtime are in
[final-qualification-v1.json](evidence/final-qualification-v1.json). The full report
and 2,100 provider/point records remain under `/tmp/pantrypulse-forecast-final-v1`,
with file hashes retained in the checked-in evidence. The one-time opening journal
is under `/tmp/pantrypulse-forecast-validation-v2`.

## Application and downstream acceptance

The actual loopback HTTP → PostgreSQL → production Linux supervisor → contained
model child journey passed in disposable test schemas:

- Without fallback, the full 26-series synthetic model job saves 12 valid demand
  series / 84 points and remains `planning_ready=false`. All 14 donation series
  produce negative raw quantiles and are rejected without clipping.
- With explicit whole-batch fallback, all 26 series / 182 points are available,
  planning-ready and truthfully labelled **MOVING_AVERAGE**. This is baseline
  fallback evidence, not full-scope Chronos qualification.
- Real child cancellation/empty-boundary confirmation, frozen retry, absence of
  database credentials in the child, saved reads/reuse while offline and 503 for
  new offline computation passed.
- A committed fallback result froze one canonical scenario and ran both actual
  OR methods with the same operational/policy/settings hashes and explicit equal
  15-second native budgets. Both returned independently verified OPTIMAL results
  for this particular simulated seed. This does not revise the production
  120-second default/300-second maximum or generalize to larger OR scenarios.
- The downstream saved result replay matched, and the generated test schema and
  this smoke's processes were cleaned up. No existing runtime was stopped.

Evidence: [real downstream smoke](evidence/chronos-or-qualification-smoke.json).
Reproduce it with the explicit test-database configuration and:

```sh
python -m scripts.smoke_chronos_jobs --output /tmp/new-qualification-smoke.json \
  --compare-methods --or-search-seconds 15
```

The `operational_qualified=false` field in the final model decision records that
the **complete required Chronos model scope** has not passed. The application
wiring, containment, fallback and OR handoff passed separately. Durable success
and a functioning model adapter do not imply full-scope model planning readiness.

## Combined checks and remaining work

The stable combined backend passed **1,312 tests, zero skips**, including real
Linux process-control and isolated PostgreSQL tests. Ruff and whitespace checks
passed. All **18 configuration tests passed**, after supplying checksum-verified
portable PowerShell 7.6.6 in `/tmp`; no system installation or test weakening was
used. Frontend typecheck/lint/generated-contract/proxy-unit/build passed in FC-05.
Browser E2E was not rerun at that original qualification checkpoint. Recorded verification:
[combined-verification-v1.json](evidence/combined-verification-v1.json).

The subsequent main integration preserves its live Overview, shared shell/themes,
visitor reads and typed dashboard contracts. The expanded real Chronos job smoke
also checks Overview's incomplete-result rejection, moving-average fallback
provenance and presenter-only computation. Integration checks and their precise
browser scope are recorded separately in
[main-integration-v1.json](evidence/main-integration-v1.json): **1,322 backend tests
with zero skips, 40 browser checks, 20 configuration checks**, frontend build,
typecheck/lint, contract drift and six proxy unit tests all passed. Browser checks
include actual forecast-to-OR, failure/cancellation/retry and live Overview journeys;
the added result-display checks cover desktop/mobile readiness, provenance and
accessibility. This is scoped integration verification, not every browser suite.
PRs #91–#92 merged while PR #93 was being checked, replacing the legacy workspace
with Scenario Lab and expanding product support. Chronos selection and truthful
provider/readiness reporting were moved into `/scenarios`; the retired workspace
stays removed, legacy forecast links still resume, and the multiplier controls
support all eight products. Updated combined verification is recorded in
[scenario-lab-integration-v1.json](evidence/scenario-lab-integration-v1.json).
The model experiment was not rerun and its one-time final holdout was not reopened.

Keep Chronos opt-in/experimental and preserve existing defaults. Follow-up under
existing #9/#46/#70 must explicitly qualify a nonnegative-output policy for
zero-heavy histories, measure its effect using a newly declared experiment or
holdout, and address interval calibration. The inspected final week is no longer
an untouched holdout for tuning. Real pantry-demand and donation histories remain
necessary for domain accuracy claims. Broader source/quality parent issues remain
open; this work does not claim deployment or a full product release.
