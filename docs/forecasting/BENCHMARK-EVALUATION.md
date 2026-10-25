# Retail proxy evaluation and sealed qualification

FC-06 / #85 extends the existing forecasting arithmetic and actual baseline
provider logic to the source-native envelope prepared by FC-03. It does not
manufacture a production `HistoryBundle` or label retail sales as requested
pantry need, donations or physical stock.

## Reproduction

The ordinary data envelope and metrics tests require neither Arrow nor model
packages. Actual validation uses the isolated pinned model/tooling environment:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/tmp/pantrypulse-chronos-fc04/bin/python \
  apps/api/scripts/evaluate_retail_forecasting.py \
  --manifest /tmp/pantrypulse-forecast-pilot-v1/manifest.json \
  --output-dir /tmp/pantrypulse-forecast-validation-v2 \
  --model-revision 29ec3766d36d6f73f0696f85560a422f50e8498c \
  --model-cache /tmp/pantrypulse-chronos-hf/hub
```

For a rerun, choose a new empty output directory; existing frozen artifacts are
never overwritten. The model/checkpoint/profile, actual model-file hashes,
source-code hashes, raw dataset/cohort/fold identities, runtime dependencies and
validation-selected baseline are saved before any final truth is opened.

`app.services.forecasting.benchmark_evaluation.evaluate_benchmark(dataset,
providers)` accepts explicit `BenchmarkProvider` execution functions and defaults
to validation. Each receives only an immutable origin-limited `BenchmarkWindow`.
The baseline adapters expose narrow `predict_values` helpers reused by both
production and offline callers; their existing forecast semantics and input
identity remain unchanged. The moving-average experiment uses an explicit
14-calendar-day window and at least three observed values.

All expected points remain represented, including failed outputs and missing or
censored truth. Reports include full-population and common-key paired metrics,
per-series/per-horizon/actual-provider cohorts, training-has-zero/missing/censoring
cohorts, fallback reasons, and MAE/signed bias/WAPE with null denominator cases.
Quantile diagnostics include pinball loss and empirical 80% interval coverage/
width, explicitly uncalibrated. Future realized stockout status stratifies truth
diagnostics only and is never a model input. No imputation or output clipping is
performed. Provider errors are counted; programming exceptions abort the run.

Primary model comparison has fallback **disabled**. An explicit injectable
offline fallback can be tested/reported per series/origin, with actual provider
labels; that mode is distinct from the application's supervised whole-batch
fallback and is not used in the frozen comparison.

## Executed validation result

The [compact evidence record](evidence/retail-validation-v1.json) retains hashes,
full coverage, paired metrics, cohort/horizon summaries, versions and timing.
The complete report and raw predictions are under
`/tmp/pantrypulse-forecast-validation-v2/`; large records stay outside Git.

| Strategy | Available / expected points | MAE on all available points | MAE on the identical 2,527-point intersection |
|---|---:|---:|---:|
| Seasonal naive | 2,800 / 2,800 | 0.480171 | 0.469794 |
| Moving average | 2,800 / 2,800 | 0.434074 | 0.416365 |
| Chronos-2 | 2,527 / 2,800 | 0.384476 | 0.384476 |

The 100-series / four-origin run yields 2,800 expected points per strategy.
Chronos has **273 invalid-output points** (39 series/origin requests), retained in
coverage and failure counts. Its 90.25% point availability is below the frozen
99% qualification threshold. The lower error on the available intersection does
not remove those failures or establish a generally superior planning provider.
This is validation evidence, not the final qualification decision.

On that available intersection, the predeclared 500-replicate series-cluster
bootstrap covers 98 series and yields a Chronos-minus-mean MAE difference of
-0.031890 (95% interval approximately -0.051246 to -0.015171). Entire series, not
individual adjacent days, are resampled. This conditional improvement evidence
does not cover the unavailable predictions or satisfy the full-population
availability/series qualification gates.

Moving average is selected as the strongest baseline using **baseline-only
common validation MAE**, with a deterministic lexical tie break and full coverage
disclosed. Chronos availability never filters the baseline-selection population.
That choice is frozen before final evaluation. On valid model points, raw 80%
intervals have approximately 77.998% empirical coverage and mean normalized width
1.14919; these are diagnostics, not calibrated uncertainty or pantry probabilities.

Actual validation wall time was 28.98 seconds, with process peak RSS 944,948 KiB,
on the recorded Linux environment using CPU float32/two inference threads.
These offline measurements do not replace contained job/runtime acceptance.
RSS measurement is a lazy optional platform feature; Windows returns null when
the `resource` module is unavailable rather than breaking baseline test imports.

The initial run in `...validation-v1` preceded this Windows portability fix. A
new run froze `...validation-v2` after the infrastructure-only change. Both runs
have **identical canonical predictions, prediction-file SHA-256 and metric
hashes**; no provider settings, data cohorts, output policy or tuning changed.
Both directories remain recorded, and neither opened final truth.

Active freeze hash:
`62054d6c13ce60c02f6ca9e88f459a048cfb1cf868aef4742ae5e3ec5e443784`.
Canonical prediction hash:
`8eedbe2264682ea89e7341ff6ef67f1f9b915021e2ca4affa9e6044d3763b377`.
Metric hash:
`d28cc1a3db5d534b52da841624154502aae3206799649d6fca1d36ae2ef85c8b`.

## FC-07 guarded handoff and completed opening

The combined gates subsequently passed and root executed the one frozen final
opening. Its [decision and evidence](QUALIFICATION.md) record insufficient
coverage; the opening journal now exists. The interface below documents the
guarded handoff, not a request to repeat the consumed experiment or retune against
its final labels.

The CLI has no final-evaluation command. After the combined review/full gate,
the serial owner can explicitly call
`scripts.evaluate_retail_forecasting.run_final_holdout` with:

- `validation_dir=Path('/tmp/pantrypulse-forecast-validation-v2')`;
- `data_cache_dir=Path('/tmp/pantrypulse-frn50k/c374e85975c82816c495acfa904cc55ab14a47d3')`;
- a new empty `output_dir`;
- `model_cache_dir='/tmp/pantrypulse-chronos-hf/hub'`;
- an explicit `operational_qualified` value supported by the separate runtime
  evidence, and `allow_final_holdout=True`.

Without that opt-in it fails before reading any artifact. With it, the helper
checks frozen validation/model/data/code/dependency identities, writes an
exclusive `final-holdout-opened.json` in the validation directory, then opens the
seven-day final truth and runs the frozen providers. The marker survives failures
and prevents silent repeated opening. Code identity is checked again after final
inference; a change does not reset the marker. Retuning after seeing final results
requires a separately named experiment/holdout with disclosure.

The qualification helper applies the existing protocol: at least 100 paired
series and 99% availability, MAE no more than 5% above the validation-selected
baseline, and improvement only when a 500-replicate seed-20261025 series-cluster
bootstrap 95% upper MAE-difference bound is below zero. Adjacent dates and
overlapping origins remain inside each resampled series. Runtime qualification
is reported separately. Retail results leave pantry demand, donation accuracy
and fitted interval calibration unqualified, and never switch a production
provider/default automatically.

New deterministic tests cover arithmetic, missing/zero/basis cases, uneven model
coverage, temporal perturbation, exact scope/date mapping, fallback/bug behavior,
duplicate truth, sealed holdout, one-time opening, code changes and optional RSS.
The synthetic evaluation CLI now labels its fresh results as offline synthetic
baseline evidence and says implemented API/jobs/OR are **not exercised by that
command**. Historical checked-in JSON remains unchanged.
