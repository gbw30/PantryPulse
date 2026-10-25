# Opt-in Chronos jobs

FC-05 / #84 extends the existing forecast submission/result routes with the
separate `forecast.chronos.v1` contract. Seasonal naive and moving average remain
on `forecast.v1`. Existing saved baseline input hashes are unchanged; the frozen
policy gained no default-valued fields. The new adapter profile is represented in
the existing `adapter_version` field only for newly admitted Chronos inputs.

## Operator configuration

Both the API and actual worker must have deliberately selected the same approved
revision/profile. The API may run without optional model packages or a mounted
model cache: it freezes the configured identity and uses the worker's live
advertisement for admission. The worker must have the exact locked optional
packages and the actual cached files. No model is downloaded during admission,
inference, startup, polling or saved reads.

The existing explicit Compose model tools use `CHRONOS_PIN_FILE=/cache/model-pin.json`
and `HF_HOME=/cache/huggingface`. After preparing that model, inspect the pin file
and copy its **full revision SHA** into the new setting in the private environment:

```dotenv
PP_CHRONOS_ENABLED=1
PP_CHRONOS_REVISION=29ec3766d36d6f73f0696f85560a422f50e8498c
PP_CHRONOS_MODEL_CACHE=/cache/huggingface/hub
```

The shown SHA identifies the model actually exercised for this change. Copy the
exact deliberately prepared pin; do not replace it with `main`, resolve a moving
ref per job, or silently update an existing worker. Defaults in `.env.example`
and `compute.env.example` remain `PP_CHRONOS_ENABLED=0`, with no revision selected.
The cache setting is a trusted absolute worker filesystem path, not a browser
parameter. Local non-container smoke used `/tmp/pantrypulse-chronos-hf/hub`.

The production registration is always available to validate saved records and
API requests. The supervisor advertises Chronos only when opt-in configuration,
package identity and local checkpoint/config files pass its cheap preflight.
Admission and retry match the frozen checkpoint/package/profile against that
advertisement. A stale/missing/different capability returns compute unavailable.
Removing an optional model dependency does not break baseline imports or saved
reads. A checkpoint update creates different reuse identity and requires an
appropriate new worker advertisement; it never changes a frozen retry's model.

No existing runtime was restarted, container rebuilt, deployed service changed or
shared database migrated by this implementation. Apply runtime/environment changes
deliberately using the existing drain/recovery procedure.

## Request and execution

Use existing presenter authentication, Origin/CSRF and Idempotency-Key requirements
on `POST /api/v1/forecasts`. Set `policy.strategy` to `CHRONOS2` and explicitly
choose `allow_fallback`. Browser attempts to choose Chronos checkpoint/package/
revision/profile metadata fail validation. The server supplies the approved pin
before freezing inputs. No request accepts an arbitrary local path or device.

The workspace now offers seasonal naive, moving average and experimental Chronos.
It identifies the last generated job, actual providers, fallback and incomplete
planning readiness rather than assuming the selected strategy actually ran.
Raw model intervals are uncalibrated.

Main's live Overview consumes the same committed forecast records. An incomplete
result keeps physical inventory visible while marking forecast statuses as not
evaluated; it cannot supply a planning projection. A complete fallback result
shows the actual moving-average method and fallback reason. Optional visitor
access applies only to saved dashboard, shortage and catalog reads; job status,
forecast submission and mutations still require a presenter session.

The actual child receives only trusted Chronos enable/revision/cache settings in
addition to existing non-secret process/thread settings. Database URLs and model
tokens remain outside the child environment. Inference stays univariate CPU
float32, two model threads, context 366, no cross-learning, seven future dates.

One primary step keeps the existing 270-second cutoff within a 300-second
operation. If explicitly allowed, a classified primary failure permits one
supervised whole-batch moving-average fallback. There is no nested uncontrolled
provider chain. The shared one-active/two-waiting lane, OR budgets, ownership
fences, cancellation and atomic output/job publication are retained.

## Honest outcomes

Actual full-demo model execution currently produces valid demand forecasts but
negative donation quantiles. Under `reject-invalid-v1`, those donation outputs
are rejected without clipping. With fallback disabled, the successful durable
job may publish an incomplete, readable forecast with `planning_ready=false`.
Durable success does not mean full model scope is suitable for planning.

With fallback enabled, the whole batch is recomputed by moving average and can
be planning-ready. Its actual provider is **MOVING_AVERAGE**, with explicit
fallback metadata and null model quantiles. It is not Chronos quality evidence.
The publisher rechecks provider/profile, quantile semantics, whole-batch fallback
uniformity and explicit fallback authorization at the actual publication boundary.

Saved results, polling, cancel and frozen retry use the existing routes for both
forecast contracts. Identical committed planning-ready fallback results can be
reused during worker outage; new computations still return 503. Partial forecasts
are not reused as planning-ready results and cannot freeze an operational scenario.

## Verification entry point

`scripts/smoke_chronos_jobs.py --output /tmp/chronos-jobs.json` requires an explicit
`PP_TEST_DATABASE_URL` whose database name ends in `_test`, plus configured actual
model capability. It creates one uniquely named disposable schema, explicitly
migrates/seeds fictional history and audited stock, starts its own loopback HTTP
server and production supervisor, and executes real contained model children.
It verifies partial publication, whole-batch fallback, real cancellation/empty
boundary/frozen retry, database-free child environment, canonical scenario capture,
saved reuse and truthful worker-unavailable admission. Cleanup is confined to its
own server, worker and generated schema. It does not evaluate a final holdout.

See `evidence/chronos-jobs-review.md` for measured results and exact gate scope.
