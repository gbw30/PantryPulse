# Forecasting core implementation

Date: 2026-10-24. Scope confirmed by the user: implement the forecasting core and
retain shared-contract gates. [ADR 0003](../../architecture/0003-forecasting-core.md)
records the boundary; [task packet](../tasks/PP-09-forecasting-core.md) records ownership.
The supplied implementation plan remains intact.

## Implemented

| Module | Behavior |
|---|---|
| `app/services/forecasting/schemas.py` | Immutable experimental Pydantic contracts; ownership, finite quantities, demand components, receipt local dates, missingness, quantiles and result completeness |
| `preparation.py` | Explicit named dataset and knowledge cutoff; one highest visible numbered revision per logical fact; complete receipt revision/line sets; daily sum by receiving site/product; coverage-backed zeros; explicit calendar gaps and proxy opt-in |
| `adapters/seasonal_naive.py` | Exact `cutoff+h-7` calendar reference, including real zero values |
| `adapters/moving_average.py` | Explicit trailing calendar window/minimum, observed samples only, mean estimate and null quantiles |
| `adapters/chronos2.py` | Lazy, dependency-free unavailable boundary while real model qualification is paused |
| `service.py`, `postprocessing.py` | Seven unique future dates; classified provider failure/fallback, mixed-provider metadata, required/optional outcomes, exact-reuse eligibility and explicit fresh result IDs |
| `evaluation.py` | Explicit historical origins and knowledge cutoffs, separate held-out truth cutoff, missing/zero/basis accounting, MAE/bias/WAPE, actual-provider evidence and common paired scored sets |
| `handoff.py` | Frozen inputs/results and explicit exclusions; central or p90/buffer choices, per-day ceiling, canonical hash and verification |
| `app/services/inventory/projection.py` | Versioned eligible lots and confirmed arrivals, dated FEFO/expiry and daily lost-sales service/unmet recurrence |

`ready_for_publication` is a computational completeness check. It does not claim
database publication, a live `planning_ready` state or a persisted scenario.
The handoff freezes forecast-derived demand only; the full operational scenario
must later freeze inventory, routes/capacities, attributes, policies and assumptions.

## Explicit experimental policies

- Select the highest **visible revision number** within one named dataset/logical
  fact. Duplicate revision numbers/IDs and competing daily facts fail; whole receipt
  revisions replace whole line sets. `recorded_at <= snapshot_as_of` controls visibility.
  Dates after the data cutoff never enter the selected snapshot. A correction moving
  an event past the cutoff removes the old event rather than reviving its old revision.
- Freeze full selected fact content, including receipt donors, instants and individual
  lines. Hash canonical UTF-8 JSON with sorted keys, compact separators and no NaN;
  sort scopes, revisions, dates and line IDs. Dates are ISO, timestamps UTC. Hashes
  retain original revision identities, masks, source classifications, policy versions,
  provider configuration and knowledge cutoff. A changed receipt header changes identity
  even if the daily aggregate is unchanged.
- No backend imputation or historical clipping. Requested demand stays unknown when
  missing. Fulfilled proxies require explicit opt-in; mixed requested/proxy histories
  require a second opt-in. Original requested/fulfilled/unmet components remain frozen.
- A receipt sum without complete reporting coverage remains labeled
  `INCOMPLETE_RECEIPT_COVERAGE`. No receipt and no coverage stays missing. A complete
  coverage declaration with no receipts supplies a genuine observed zero.
- Seasonal naive requires all seven reference dates. Only explicit fallback permits
  the sparse mean. The demo specifies 14 days and three observations; there is no
  production threshold default. Baselines have no p50/p10/p90 or fabricated confidence.
- Negative/nonfinite predictions, wrong dates, duplicates and crossed quantiles are
  rejected. Classified provider failures may fall back; invalid inputs and programming
  errors are not hidden by provider substitution. Chronos-unavailable fallback remains
  attributed to the actual baseline, never Chronos accuracy evidence.
- Conservative demand uses an available p90, otherwise an explicitly supplied finite
  nonnegative buffer. No default buffer or public bound is selected. Decimal calculation
  precedes one ceiling per day; no extra rounding occurs in projection. Buffers do not
  create stored quantiles or calibrated stockout probabilities.
- Projection's experimental order is arrivals, expiry, service. Expiry D excludes D;
  unknown/held eligibility is unavailable. Null expiry is permitted in this pure
  experiment, pending operational policy. Receipt predictions are never arrivals.

These details are versioned internal experiments. OPEN-04–18/19–22 and the public
contract/research gates stay open; they require shared review before live adoption.

## Running and integration

From the repository root with the existing pinned toolchain:

```bash
uv run --frozen --directory apps/api pytest -q tests/forecasting
uv run --frozen --directory apps/api ruff check .
uv run --frozen --directory apps/api python -m scripts.evaluate_forecasting --output /tmp/pantrypulse-forecast-evaluation.json
```

The script expands `data/demo/forecasting-v1.json` deterministically: six fictional
beneficiaries plus one hub, two products, 90 local days, 12 required demand and 14
required donation series. Hub demand is explicitly ineligible; no series is optional.
Early deliberate gaps, an unknown requested day, genuine same-day receipts, a late
receipt correction and coverage declarations exercise preparation. All data is simulated.

The full JSON artifact contains typed inputs/outputs, exact selected source snapshots,
run/result IDs, forecast handoff, per-fold outcomes/pairs, source/provider metadata,
coverage counts and grouped metrics. Its run IDs and execution timestamps change on
recomputation; the canonical input hash remains stable. It writes no database or stock.

Application integration uses:

```python
inputs = prepare(history, data_cutoff_date=cutoff, snapshot_as_of=as_of, policy=policy)
computed = forecast(inputs)  # future controlled durable worker only
# Future repository: atomically publish outcomes/points before planning-ready reads.
handoff = freeze_handoff(inputs, computed, choices=explicit_demand_choices)
```

`HistoryBundle` is a trusted repository boundary for already resolved organization/site/
product records. Pure UUID checks cannot prove database existence or donor ownership.
No HTTP routes, stock posting/import endpoints, ORM models, migrations or TypeScript
contracts are exposed. Never call the synchronous service from startup, probes or GET.
It is not a background job implementation and does not enforce wall/resource limits.
The future supervisor must supply serialized admission, process containment, shared
300/270-second forecast deadlines, leases, heartbeat, queue expiry and manual retry.

## Evidence and remaining gates

Executed on Python 3.12.3 in an isolated `/tmp/pantrypulse-forecast-venv`:
`python -m pytest -q` from `apps/api` passed **44 tests**; `ruff check .` passed.
The full API suite ran outside the execution sandbox because its existing
FastAPI TestClient checks stalled inside it. There was one existing Starlette
httpx TestClient deprecation warning. The local `uv` executable was unavailable;
the isolated environment used the locked versions listed in the evidence JSON.
Optional model/solver dependencies and the complete locked runtime were not qualified.
Independent review and the live/research checks below remain outstanding.

See [synthetic evaluation summary](evaluation.synthetic-v1.json) for the measured
dataset hash, origins, grouped metrics and counts. MAE/bias/WAPE use central predictions;
bias is prediction minus actual and positive means overprediction. WAPE is null for
zero total actuals; all metrics are null with zero scored pairs. Groups pool only the
same target/product/unit/actual basis. Paired comparisons retain the full reports'
failure/coverage counts. No automatic model selection, holdout calibration or accuracy
claim outside this deterministic simulated fixture is made.

| Plan acceptance IDs | Evidence scope |
|---|---|
| F-01–05, F-07–12 | Pure expected-value/adversarial tests: full designated scope, proxies/gaps/zeros, components/ownership, receipt revisions, baselines, fallback/output validation and chronological/paired scoring |
| F-14 | Pure identity/reuse eligibility and explicit fresh computation tests; PostgreSQL races/dedup are pending |
| F-15–17 | Pure frozen forecast handoff and projection tests; complete operational scenarios and conditional donation reconciliation are pending |
| F-06, F-13, F-18–22 | NOT IMPLEMENTED: import/stock transactions, atomic publication, authorization/proxy/public reads, durable jobs, admission, recovery, process deadlines/resources |
| F-23–24 | GATED: live PostgreSQL/API and both independently validated allocation methods, full judge journey |
| F-25 | UNQUALIFIED/PAUSED: actual pinned Chronos inference/evaluation/resources/native gaps |
| F-26 | UNVERIFIED: live saved-read/per-method performance targets |

The complete V4 plan is not declared done by the offline results. These gates are
retained under the user's scope decision, including all mandatory live/research gates.
