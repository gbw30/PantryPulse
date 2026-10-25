# Forecasting contract and qualification protocol v1

Frozen for implementation on October 25, 2026 under #80. Owner: @GestebanFalcon.
Base: main `5add76008faddae08a969514c2e827299bc84d50`. The user's subsequent
instruction authorizes implementation through #86 using two coordinated agents.
This protocol defines this bounded experiment and provider integration; it does
not change baseline production defaults or claim representative pantry accuracy.

## Provider contract

- Model: `amazon/chronos-2`; optional locked `chronos-forecasting==2.3.2`.
  Resolve the checkpoint to a full immutable 40-character commit SHA during an
  explicit preparation step, never by following a moving branch during execution.
  Record model-file hashes, package/runtime versions and device settings.
- Initial profile: univariate, CPU float32, two inference threads, seven local
  future days, no covariates, no cross-series learning or fine-tuning. Histories
  remain daily, gap-explicit and bounded to the existing 366-day contract.
  Load the model lazily and reuse it across series within one contained child;
  no network/model loading on module import, API startup, admission or saved reads.
- Existing ForecastPolicy checkpoint/package/revision fields carry immutable
  identity. A named adapter/execution profile must also be frozen in identity
  before public admission. FC-05 owns any necessary shared-schema extension;
  FC-04 must not make competing public contract changes.
- Preserve missing values as native NaN only where verified against the pinned
  API; zero remains zero. Require at least one finite observed value. All-missing,
  unsupported gaps/lengths or unavailable dependencies/cache are explicit provider
  failures, never inferred zeros or silent fill-forward. Test native behavior.
- Return p10/p50/p90 only when actually provided; central estimate is p50 and
  estimate_kind is MEDIAN, interval_method MODEL_QUANTILES. Keep raw precision.
  Native mean/point fields must not masquerade as a median.
- Keep `reject-invalid-v1`: reject negative/nonfinite values, crossed quantiles,
  duplicate/missing/misaligned dates and wrong series identity. The standalone
  runner's raw negative diagnostics are not valid application outputs. No clipping,
  flooring, sorting quantile values or repair. Record failures and fallback.
- Classify expected provider availability/native output failures narrowly.
  Programming errors and invalid application inputs must escape as failures and
  may not enable substitution. Mocked outputs test mapping only; real inference
  remains a separately recorded acceptance check.

## Durable application contract

FC-05 uses a distinct Chronos-capable handler contract (proposed
`forecast.chronos.v1`) rather than letting old `forecast.v1` workers accept new
strategies. Baseline `forecast.v1`, its saved records and OR contracts remain
unchanged. Advertise the new capability only with explicit configured checkpoint
identity and available local model/dependencies; do not advertise a fake heartbeat.

Resolve and freeze the approved model/profile at admission; do not let a browser
request name arbitrary paths, checkpoints or devices. Reuse identity includes the
checkpoint revision, package, adapter, precision, threads/context/grouping and
preprocessing policy. Retry preserves that frozen input. A changed model/profile
cannot read or reuse another model's output accidentally.

Use the existing one-active/two-waiting PostgreSQL lane and 270-second primary /
300-second operation limits. Preserve reserves, containment, cancellation,
ownership checks and atomic publication of outputs with successful job state.
The existing whole-batch fallback is retained: one controlled Chronos primary,
then one controlled moving-average fallback when opted in and eligible. This
bounded first integration deliberately does not add an uncontrolled nested
Chronos → seasonal → mean chain. An expanded chain needs its own versioned budget.
The pure/offline service's existing baseline behavior remains compatible.

No optional inference import is needed for ordinary baseline jobs. Model startup
or full-scope execution that misses the runtime ceiling is an honest failure with
eligible fallback; do not widen OR deadlines or silently raise resource ceilings.
Any successful required scope must retain exact provider/fallback metadata and
feed planning with the existing single daily ceiling. Predicted donations do not
become physical stock or confirmed supply.

## Data and split contract

Use direct daily pantry/food-bank exports when actually available and qualified.
Otherwise use the official FreshRetailNet-50K files as a **retail observed-sales
proxy**. Keep normalized source units, original store/product IDs, stockout flags
and retrospective availability semantics; never relabel sales as requested demand
or donations, nor invent historical revision timestamps. Source inspection must
verify file revisions, checksums, observed lengths/dates, schema and terms.

No general stockout recovery or imputation is part of v1. Score observed sales on
all available days, with a separately labelled uncensored-days diagnostic. Latent
demand under stockout is unobserved. Masks may stratify reports after prediction;
future realized masks/weather must never be model inputs. Record a donation-data
gap if no suitable donation history is available.

Deterministic pilot: 100 series, seed 20261025, minimum 28 training calendar days.
Use a larger 1,000-series run only after recording pilot cost; full-corpus execution
is optional. Sampling uses training-only history and stable IDs, not model scores
or final-period labels. Include zero/intermittent/gappy/censored cohorts, with
counts and explicit excluded populations. Do not fabricate a cohort absent in
the source. Initial pilot selection can be a stable hash sample; broader claims
need a separately frozen stratified expansion.

Preserve suitable upstream final eval dates. Verify the actual file split before
freezing manifests. If train has 90 daily dates and eval has the following seven,
use seven-day validation folds ending at training dates 62, 69, 76 and 83; the
first subsequent seven days are each fold's truth. The untouched upstream eval
week is the final holdout. An alternative source length requires an explicit
new split manifest before scores. No tuning/calibration on the final week.
The synthetic pantry fixture remains a separate correctness experiment.

## Evaluation and decision contract

Extend the current evaluator and paired metrics; a narrowly typed external-sales
envelope is allowed to preserve source semantics without bypassing production
requested-demand guards. Actual provider execution must be reusable by that
envelope. Shared production schemas remain FC-05's serialized responsibility.

Compare seasonal naive, explicit 14-day/three-observation moving average (an
experiment setting, not a production default), and real Chronos. Primary strategy
scores and actual fallback provider scores remain separate. Compare identical
series/origin/date/unit/basis keys and retain full availability counts alongside
the paired intersection. Report MAE, signed bias (positive=overprediction), WAPE
(null with zero truth denominator), per-horizon/cohort metrics and all missing,
censored, unavailable, basis-mismatch, invalid-output and fallback counts.

For raw quantiles additionally report pinball loss and empirical 80% interval
coverage/width with counts. This is diagnostic, not fitted calibration. #70 retains
calibration, covariates, stronger intermittent methods and ensembles.

Before examining final truth, freeze adapter/settings/model/dataset/split/code
identities and validation report. Run the registered final week once per frozen
experiment. Later tuning requires a new experiment and disclosure of holdout
reuse. Real-runtime and final-holdout work must remain serialized so two agents
cannot independently consume the final holdout.

Predeclared decision rules:

1. **Operationally qualified** requires real required-scope inference and the
   contained API/PostgreSQL/worker/publication/planning journey, with existing
   deadlines and failure fences; mocks or a model import alone do not pass.
2. **Retail-proxy compatible** additionally requires at least 100 final-holdout
   series, >=99% available points and paired MAE no more than 5% above the best
   validation-selected baseline. Report aggregate bias/WAPE and cohort failures;
   the tolerance is an experiment rule, not a pantry deployment guarantee.
3. **Improvement evidence** additionally requires the 95% series-cluster-bootstrap
   interval for paired MAE difference versus that preselected baseline to lie
   below zero (500 replicates, seed 20261025). Do not treat seven adjacent days or
   overlapping origins as independent samples. Zero baseline error requires
   exact non-worsening; undefined/no-pair cases are insufficient evidence.
4. Missing real-model/runtime evidence, too few pairs, material coverage loss,
   invalid quantiles or unresolved provenance yield **experimental / insufficient
   evidence**; a materially worse measured result is reported as **rejected for
   the evaluated scope**. Keeping baselines is an acceptable outcome.
5. Retail success does not qualify pantry demand or donation accuracy. These
   remain unqualified until representative sources pass the same protocol.
   No automatic provider/default switch follows from this experiment.

Record exact commands, hardware, wall time/peak memory, dependency/checkpoint/file
hashes, raw predictions, metrics and limitations. Ordinary CI uses deterministic
boundary/arithmetic/leakage tests; real-model and real Linux/PostgreSQL/browser
checks are explicit measured gates. FC-07 records a decision even when that
decision is insufficient evidence, without claiming unperformed acceptance.
