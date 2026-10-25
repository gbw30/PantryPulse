# FC-04 / #83: pinned adapter implementation and real execution evidence

October 25, 2026. Baseline main `5add760`, working branch `feat/forecasting-next`.
This is the adapter milestone only. Public strategy admission, worker capability,
fenced job publication and representative evaluation remain FC-05/06/07.

## Implemented boundary

`Chronos2Adapter` now performs real lazy, cache-only CPU float32 inference from an
explicit full checkpoint SHA. The pinned optional package is 2.3.2; the fixed
profile is `chronos2-univariate-cpu-f32-v1`, two threads, context 366, seven future
dates, batch one and no cross-learning/covariates. One pipeline is reused for all
series in that adapter/child. No model package or numeric dependency loads merely
by importing the adapter. Ordinary unpinned CHRONOS2 requests remain unavailable.

`predict` checks the immutable ForecastPolicy checkpoint/package/revision and
series membership. Explicit trusted `ChronosConfig(revision, cache_dir)` may
select an operator cache location, never a browser path; pin mismatch raises an
application error rather than permitting fallback. `predict_values` accepts a
gap-explicit daily sequence for a source-specific offline benchmark without
fabricating requested-demand or donation records.

Native inference uses `predict_quantiles`, checks the exact one-variate/seven-day/
three-quantile shape and takes p50 explicitly. Negative/nonfinite/crossed outputs
are rejected without clipping or repair. Missing history becomes native NaN;
zeros remain zero; all-missing/invalid-length inputs fail before loading.
Missing packages/pins/cache files and framework memory exhaustion are narrowly
classified. Programming exceptions propagate. No public schema, worker, API,
registry, generated contract, shared evaluation code or lockfile was changed.

Primary API evidence: [pinned upstream v2.3.2 pipeline](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/src/chronos/chronos2/pipeline.py).
The native method's second return slot is misleadingly called mean; the adapter
ignores it and uses the actual 0.5 quantile. The list input form supports the
univariate, no-cross-learning contract without a provider-specific public frame.

## Real-model result

Checkpoint: `amazon/chronos-2` at
`29ec3766d36d6f73f0696f85560a422f50e8498c`. Preparation explicitly downloaded only
the official config and safetensors into a separate `/tmp` cache. Their hashes
and exact dependency versions are recorded in
[the machine summary](chronos-adapter-smoke.json).

Both cold and warm runs executed the complete 26-series synthetic fixture:

| Check | Observed result |
|---|---|
| Native model calls | 26 per run; actual inference, no mocks/fallback |
| Accepted demand series | 12, producing 84 valid future points per run |
| Rejected donation series | All 14: negative raw quantiles, `INVALID_PROVIDER_OUTPUT` |
| Required-scope planning readiness | **False**, correctly retained |
| Cold full run, including model import/load | 5.932 seconds |
| Pipeline import/load component | 4.002 seconds; one load only |
| Warm full run | 1.929 seconds |
| Peak process RSS, including edge checks | 910,028 KiB |

Additional real edge checks: gappy and all-zero histories reached native inference
but their negative quantiles were rejected; a one-observation history produced a
valid forecast; all-missing history was classified `INSUFFICIENT_DATA` before
inference. There were 55 native calls across both full runs and three inferable
edge cases. Raw shape was `[1, 7, 3]`. These results verify execution and rejection
behavior, not pantry accuracy, interval calibration or successful full-scope
planning. No negative output policy was widened to make the smoke pass.

The first cache-only attempt exposed Hugging Face 2.3 snapshot-completeness
checking of unneeded README/attributes files after a minimal download. The loader
now explicitly requests the same two essential file patterns with
`local_files_only=True`; the final smoke ran with `HF_HUB_OFFLINE=1` and no network.
The upstream `torch_dtype` deprecation notice remained visible; no inference
warning or failed scope was suppressed.

## Reproduction and handoff

Prepared environment: `/tmp/pantrypulse-chronos-fc04/bin/python`.
Trusted model cache: `/tmp/pantrypulse-chronos-hf/hub`.
Preparation pin/file hashes: `/tmp/pantrypulse-chronos-fc04-pin.json`.
Full 204,046-byte raw run evidence:
`/tmp/pantrypulse-chronos-adapter-smoke.json`, SHA-256
`bb7624576b564ba59404dfd37a0301c1d40c57142071195fb6bf5eaaf73bca2d`.
These `/tmp` resources are local operational artifacts, not deployed resources.

From `apps/api`:

```sh
HF_HUB_OFFLINE=1 HF_HOME=/tmp/pantrypulse-chronos-hf \
  /tmp/pantrypulse-chronos-fc04/bin/python -m scripts.smoke_chronos_adapter \
  --revision 29ec3766d36d6f73f0696f85560a422f50e8498c \
  --cache-dir /tmp/pantrypulse-chronos-hf/hub \
  --output /tmp/pantrypulse-chronos-adapter-smoke.json
```

Targeted deterministic tests check pin/config mismatch, actual median mapping,
lazy loading/reuse, gaps/zeros, invalid input/output, scope, strict native shapes,
cache-only loader arguments, missing dependencies and narrow memory classification.
Mocks in those tests establish boundary behavior only; the separate smoke above
establishes actual model execution. The shared baseline environment and lockfiles
were left unchanged.

Validation: all **177 forecasting tests passed** in 11.55 seconds, including
baseline/publication regressions. The existing Starlette/httpx deprecation warning
remained visible. The first full-suite attempt inside the restricted process
sandbox stalled at the existing TestClient check and was interrupted; the same
suite completed outside that sandbox. Ruff check/format and diff whitespace
checks passed for the adapter, new tests and smoke script. No database or API
runtime acceptance is inferred from these provider tests.

FC-05 must retain whole-batch baseline fallback provenance and the distinction
between a functioning adapter and required-scope-valid model outputs. A demand-only
contained-child test can prove valid Chronos output, but cannot be relabelled as
the complete 26-series application journey.
