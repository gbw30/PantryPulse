# PantryPulse V4 — Forecasting & ML Implementation Plan

> **Current authority:** [Project specification V5](../SPEC-V5.md). V5 supersedes conflicting V4-era instructions. BD-41 requires explicit `HUB_ONLY` or `HUB_AND_PANTRY` with no default in the full operational scenario; the forecast-only handoff does not select topology. Experimental policies and live integration gates remain open.

**Workstream:** Task 03 — Forecasting and ML
**Revised:** October 24, 2026 (America/New_York)
**Status:** Reconciled execution plan; implementation and acceptance evidence remain unverified.
**Scope:** P0 forecasting, persistence/API integration, and frozen planning handoff. This revision does not resume hosting/model setup or supplier planning.

## 1. Authority, changes, and definition of done

V5 is authoritative. Apply the accepted resolutions BD-01–BD-41 in the attached backend checkpoint and the repository's [Backend Specification](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/BACKEND-SPEC.md). The attached consolidated evaluation supplies contract and data-integrity corrections. This plan translates those requirements into Task 03 work; it does not silently settle the remaining OPEN topics or replace the backend specification/checkpoint.

**Labels used below:**

- **REQUIRED:** Carried-forward V4 requirement or explicit accepted BD decision, identified where relevant.
- **PROPOSED:** Concrete implementation detail to finalize under the named OPEN topic before its dependent migration, public contract, or behavior is frozen.
- **P1:** Enhancement after the mandatory core and research gates.

### Changes from the previous plan

| Previous wording or gap | Reconciled direction |
|---|---|
| Chronos-native input implied by the shared input object | `ForecastInput`/`ForecastOutput` are PantryPulse application contracts; adapters own provider-native formatting. |
| Donation target described as allocatable supply, with donor/site ambiguity | Forecast actual units received, aggregated from individual receipts by receiving site/product/local day. Receipt does not itself imply lot eligibility. |
| Fulfilled-demand proxy presented as a suggested default | Explicit opt-in only; preserve target basis and warnings through forecasts and plans (BD-06). |
| Chronos history imputation proposed | Preserve gaps; no replacement historical observations through backend imputation (BD-27). |
| Point estimate always called `p50` | Separate a central estimate from optional median/quantiles; a mean is not a median. |
| Synchronous/precomputed alternatives to durable execution | Persisted background jobs are mandatory; fixtures do not qualify the live core (BD-11, BD-33). |
| Every rerun necessarily creates fresh inference | Reuse exact matching immutable results by default; explicit forced recomputation creates a new result (BD-29). |
| Conditional donation subtraction offered as temporary integration rule | Confirmed-only baseline; conditional donation reconciliation remains an explicit OPEN-10/19 gate. No automatic subtraction rule is adopted. |
| Runtime and fallback budgets unspecified | One active/two waiting; 900-second queue wait; 300-second forecast wall limit, with primary stopped by 270 seconds when fallback is allowed (BD-34–38). |
| Partial inputs and scenario freshness ambiguous | Explicit partial scope only; scenarios freeze all selected inputs at creation (BD-08–10). |
| Chronos fallback treated as equivalent to qualification | Qualify live baseline/core separately from actual pinned Chronos; research validation remains mandatory (BD-33). |

### Goal

Produce immutable, reproducible seven-day forecasts for two distinct targets:

1. `DEMAND`: requested units, including unmet requests; opted-in fulfilled-demand proxies remain explicitly labeled.
2. `DONATION`: actual donated units received at the receiving site, predicted as uncertain future receipts; exclude purchases and transfers from this historical target.

Series identity is `(organization_id, site_id, product_id, target_type)` on a site-local daily calendar. Products retain explicit base units. Forecasting never posts inventory, reserves stock, approves purchases, dispatches goods, or invokes the optimizer implicitly.

### P0 definition of done

- Exactly seven unique, correctly dated predictions for every required usable series in the frozen requested scope.
- Observed/proxy/simulated distinctions, explicit missingness, exact source revisions, and units survive preparation, persistence, and handoff.
- Date-aware weekly seasonal naive and a documented sparse-history path work without Chronos dependencies.
- Invalid input fails clearly; permitted provider failure triggers bounded, truthful fallback; unavailable required series prevent planning readiness.
- Measured chronological MAE, bias, and WAPE where defined are accompanied by scoring counts, windows, and actual-provider evidence.
- Results become planning-ready only after complete transactional publication; reads do not run inference.
- Persisted jobs, reuse/refresh, interruption/manual retry, compute admission, and hard deadlines meet accepted backend requirements.
- The live core runs through real PostgreSQL/API integration and both real allocation methods against one frozen scenario. The independent research gate must also pass.
- Actual pinned Chronos inference/evaluation is qualified separately. A mock, cache hit, fixture replay, dependency declaration, or setup pause does not prove Chronos works or is infeasible.

**Required demonstration:** At least six fictional beneficiaries plus hub(s), two products, and the designated demand/donation series. Small fixtures are useful unit tests but do not replace this population. Record required/optional/ineligible series explicitly; do not assume every hub must have a demand target.

## 2. Architecture and ownership

Use the existing modular FastAPI backend under `apps/api/app`, PostgreSQL, and Next.js. The browser uses a thin same-origin Next.js proxy; FastAPI retains authorization and domain validation (BD-13–14). Pydantic/OpenAPI is authoritative for public contracts; generate TypeScript after validation.

The production path is: validate submission → freeze exact forecast inputs → reuse matching completed result or durably queue work → prepare daily series → invoke adapter/fallback → validate every series → commit immutable results → expose saved reads → select result into a fully frozen scenario → inventory projection → explicit allocation/comparison job.

The evaluation path uses the same preparation/adapters at historical origins, then scores later observed outcomes. It never changes physical stock. Backtests are separate identified computations; do not rerun a full backtest on dashboard reads or silently add it to every forecast's budget.

| Owner | Deliverable and boundary |
|---|---|
| Task 00 | Resolve naming/policy dependencies and reconcile accepted decisions; retain OPEN IDs. |
| Task 03 | Service contracts, preparation, baselines, provider adapter, fallback, output validation, evaluation. Pure adapters do not require HTTP or PostgreSQL. |
| Task 04 | Revision-aware historical reads, receipt aggregation, schema/repositories, immutable results, inventory reconciliation, frozen snapshots. |
| Task 05 | Presenter authorization, proxy integration, persisted job/attempt lifecycle, admission/deadlines, errors, reads and transactional orchestration. |
| Task 06 | Display saved estimates, actual provider, proxy/gap/fallback warnings, original timestamps, partial scope, and job status. |
| Tasks 01/02 | Independently validate mathematical policy and both optimization methods; consume identical frozen targets and operational inputs. |

## 3. Historical data semantics and proposed persistence contract

### 3.1 Demand observations

**REQUIRED (BD-02, BD-03, BD-05–06):** Store daily demand totals separately from donation receipts. Requested, fulfilled, and unmet units are different facts. Preserve nullable requested/unmet values where unknown.

Enforce nonnegative supplied quantities and `requested_units = fulfilled_units + unmet_units` when all three are known. When requested and fulfilled are known, fulfillment must not exceed requested. Do not convert unknown requested units to zero. A derived missing component must be explicitly documented as derived, rather than misrepresented as an observed measurement.

Select requested units as the demand target where available. Substitution of fulfilled units requires explicit opt-in in the frozen request/policy and `target_basis=FULFILLED_PROXY`; preserve the original fields. Mixed requested/proxy history must retain per-day basis, proxy fraction, and warnings. Exact mixed-history eligibility remains OPEN-13.

### 3.2 Donation receipts and daily aggregation

**REQUIRED (BD-03–05, BD-25–27):** Keep separate `donor_id` and `receiving_site_id`. One receipt header identifies an event; its lines contain products and actual `received_units`. Offered, accepted, pledged, confirmed, purchased, and transferred quantities are not interchangeable receipt observations.

For a selected revision set, sum received donation lines by `(organization, receiving_site, product, local_day)`. Two genuine receipts on the same day are valid and both contribute; two revisions of the same receipt must not both contribute. A corrected header/line set must be selected consistently.

Keep the logical `donation_observations` boundary as a derived daily view or versioned materialization of receipts, with contributing receipt/line revision references. It is not a second independently editable truth. Final representation remains OPEN-04/07/08.

**No receipt is not automatically an observed zero.** Use explicit reporting coverage or a recorded zero-activity observation to establish a genuine zero. Otherwise preserve a gap. The completeness/zero declaration contract remains OPEN-07/12.

Historical imports never post current stock. New receipt posting is a separate, deliberate, exactly-once stock transaction linking receipt, lots, ledger, and audit. Operators declare lot eligibility; unknown eligibility remains unavailable. Forecasting actual received quantities does not establish future eligibility or usable shelf life.

Partial imports accept valid demand rows individually and accept/reject a complete receipt with all lines together (BD-26). Return precise accepted/rejected counts and row/receipt errors; duplicates are not silently overwritten. Corrections append revisions; posted-stock corrections require separate linked audited adjustments.

### 3.3 Concrete schema proposal — not an accepted migration

The following closes placeholder types for review under OPEN-04–12. Counts are proposed as whole standardized base units; confirm that assumption and numeric bounds before migration. If a product requires fractional base units, agree one exact decimal policy across history and inventory instead of truncating values.

| Record/field group | Proposed PostgreSQL representation | Integrity requirement |
|---|---|---|
| Entity/revision/run/result IDs | `UUID NOT NULL PRIMARY KEY` | Identifier-generation policy shared with the backend. |
| Ownership and references | `organization_id UUID NOT NULL`; scoped composite FKs using `(organization_id, referenced_id)` | Cross-organization references fail in DB and application validation. Donor ownership semantics require OPEN-05. |
| Local observation/cutoff/forecast day | `DATE NOT NULL` | Timezone comes from versioned site configuration; finalize day boundaries under OPEN-06. |
| Event/record/execution times | `TIMESTAMPTZ`; created/recorded times required, start/completion nullable until reached | Store receipt instant as well as its resolved local day; retain timezone rules used. |
| Demand components | `BIGINT`; requested/unmet nullable, fulfilled nullable when unknown | Nonnegative supplied values; consistency checks above. No unknown-to-zero default. |
| Receipt-line received quantity | `BIGINT NOT NULL` | Nonnegative, with receipt/line revision identity; offered/accepted quantities are separate optional facts. |
| Revision identity | Logical source key `TEXT NOT NULL`, revision number `INTEGER NOT NULL`, prior revision `UUID NULL`, recorded time | Unique organization/source/logical-key/revision; immutable originals; no ambiguous active selection. |
| Source classification | `TEXT NOT NULL CHECK (...)` for observed/simulated; target basis separately requested/proxy | Provenance details `JSONB NOT NULL DEFAULT '{}'`; require relevant details, not an arbitrary unvalidated blob. |
| `forecast_runs` | IDs, input snapshot/hash, cutoff `DATE`, horizon `SMALLINT CHECK (=7)`, strategy, policy/provider configuration, job linkage, times, readiness/outcome | Execution metadata separate from numerical points; status vocabulary remains OPEN-30. |
| `forecast_series_results` | Run/series FK, availability, actual provider/checkpoint/version, fallback, errors/warnings, basis/quality diagnostics | Unique `(run_id, site_id, product_id, target_type)`; failed series has no fabricated points. |
| `forecast_points` | Run/series FK, `target_type TEXT CHECK IN ('DEMAND','DONATION')`, day, central estimate `DOUBLE PRECISION NOT NULL`, nullable `p10/p50/p90 DOUBLE PRECISION`, interval metadata | Unique `(run_id, site_id, product_id, target_type, day)`; finite nonnegative numbers and matching ownership/series identity. |
| Configurations, errors, warnings, snapshots | Validated, versioned `JSONB`; hash `TEXT` | Hash algorithm/canonical encoding proposed SHA-256; finalize OPEN-19. Never hash unspecified serialization. |

Use composite checks/FKs to prevent a point's denormalized target/site/product disagreeing with its series result. Index scoped history by series/day and revision-selection fields; index points by run/series/day and jobs by queue/status/time after query review. SQL constraints and application validation complement each other; JSONB does not replace typed contracts.

### 3.4 Revision selection and temporal reproducibility

**REQUIRED:** A run must identify exact selected revisions and preprocessing configuration, not just a cutoff or a mutable `source_version` string. Corrections must not alter prior forecasts or scenarios (BD-05, BD-09–10).

**PROPOSED (OPEN-07/18):** Select one authoritative eligible revision per logical fact from an explicitly named dataset/import set, as known at an explicit `snapshot_as_of` instant. Reject ambiguous competing revisions rather than summing or arbitrarily taking the latest row. Keep `data_cutoff_date` (last target day) distinct from `snapshot_as_of` (knowledge/revision selection time).

For backtests, late receipts and corrections unknown at the origin must be excluded from historical inputs. If the dataset lacks historical availability timestamps, label evaluation as a retrospective corrected-history experiment; do not claim a faithful as-of replay. Store exact revision references, coverage declarations, aggregation policy, and content hash in either an immutable input package or a reference to one.

## 4. Application service contracts

These are **PROPOSED field contracts (OPEN-12–15)**, to implement in Pydantic after shared review. They describe PantryPulse's forecasting service, not the native input accepted by Chronos-2. Never pass service-only fields such as `allow_fallback`, provenance, or policy objects directly to a provider.

| Type | Proposed fields and meaning |
|---|---|
| `SeriesKey` | `organization_id`, `site_id`, `product_id`, `target_type`; resolve standardized `unit` and versioned `timezone`. |
| `DailyObservation` | `day`, `value: number|null`, `is_missing`, `source_classification`, `target_basis`, `quality_flags`, exact source revision references. Missing value and observed zero are distinct; reject contradictory flags. |
| `ForecastInput` | `schema_version`, `run_id`, `request_id`, frozen required/optional series scope, ordered daily observations, `data_cutoff_date`, `snapshot_as_of`, `horizon_days=7`, requested strategy, `allow_fallback`, explicit proxy policy, preprocessing/policy versions, covariates, provider/checkpoint/settings, input snapshot/hash. |
| `ForecastOutput` | `run_id`, input hash, per-series results, aggregate completeness/planning readiness, generation/completion times, warnings, structured errors, evaluation references when available. |
| `ForecastSeriesResult` | Result ID/key, status/availability, target basis and proxy diagnostics, actual provider/checkpoint/package version, inference configuration, fallback flag/reason, exact input reference/hash, timestamps, warnings/errors, points. |
| `ForecastPoint` | `day`, `central_estimate`, `estimate_kind`, nullable `p10/p50/p90`, `interval_method`, applied postprocessing policy. |
| `StructuredError` | Stable code, safe message, series/field context, retryability/category; expose via the backend's `{error:{code,message,details},request_id}` envelope where applicable. |

Suggested series outcomes are `AVAILABLE`, `INSUFFICIENT_DATA`, `FAILED`, and `EXCLUDED_BY_SCOPE`; these are proposals, not the accepted job-state enum. Keep low-history/low-confidence warnings separate from availability. A successful result can carry quality warnings without implying statistically calibrated confidence.

### Central estimates and quantiles

- `p50` means a median, `p10/p90` mean the stated marginal quantiles. All may be null for a point-only method.
- A moving-average central estimate has `estimate_kind=MEAN`, not `p50`. A seasonal-naive value has `estimate_kind=POINT` unless the method justifies another interpretation.
- Chronos may use its median as the central estimate when available, labeled `estimate_kind=MEDIAN`.
- `interval_method=NONE` accompanies absent intervals. Use `MODEL_QUANTILES` only for actual provider quantiles. Calibrated intervals remain P1 unless evaluated and explicitly implemented.
- Run metadata must summarize mixed providers; a single top-level Chronos label cannot stand in for per-series outcomes.

### Covariates and preparation

**PROPOSED P0 default:** No external covariates until OPEN-15 approves a typed, versioned feature catalog. Future-known features need name, type, series/date, availability time, source/version, and known-versus-forecast classification. Reject unavailable or observed future outcomes. Allowed preprocessing should be a bounded configuration schema, not arbitrary executable transformations.

All canonical observations and masks remain unchanged. Any provider-native missing-value representation must be supported and documented for the pinned provider. Backend-generated replacement historical values are prohibited by BD-27.

## 5. Work package A — Preparation and historical validation

**Difficulty:** Moderate; target meaning and as-of selection are the main risks.

1. Resolve organization/site/product ownership, standard units, timezone, target type, and requested scope.
2. Select exact revisions and aggregate actual donation receipts once per receiving-site/product/day.
3. Validate finite nonnegative history, component consistency, uniqueness, and source identity. Invalid negatives are errors, not clipped history.
4. Sort and build a complete calendar through the cutoff, retaining missing masks and explicit observed zeros.
5. Apply the opted-in proxy policy without filling absent dates; record per-day basis and warnings.
6. Produce observed/missing counts, reference-weekday availability, proxy fraction, simulated-source labels, and revision/hash diagnostics.
7. Validate future covariate availability and freeze exact provider-independent input before execution.

**Accepted missing-data policy (BD-27):** Preserve gaps; never interpolate, forward-fill, or synthesize replacement historical observations in the backend. Seasonal naive uses a real dated reference observation. A provider may use its supported native gap handling; otherwise select a labeled permitted fallback or return insufficient data. The proxy policy is a separate explicit choice.

Acceptance: input reordering leaves the canonical hash/results unchanged; missing differs from zero; revisions cannot double count a receipt; invalid ownership/units/components fail; changing post-cutoff or not-yet-known data cannot alter an as-of fold's input.

## 6. Work package B — Mandatory deterministic baselines

### Weekly seasonal naive

For cutoff day `T` and horizon `h=1,...,7`, use `prediction(T+h) = observed(T+h-7)`. Look up actual calendar dates, not the last seven array positions. Every reference must be available at the origin under the frozen target/proxy policy.

### Sparse-history fallback proposal (OPEN-13)

The previous 14/7/3 observation bands were illustrative, not accepted defaults. Finalize and version minimum history, trailing calendar window, fallback eligibility, and whether a failed weekday causes whole-series fallback or an explicitly recorded per-point strategy.

**Concrete starting proposal:** Use seasonal naive when all seven required reference days have usable observations. Otherwise, when fallback is allowed, use the mean of observed valid values in the preceding 14 calendar days if at least three are available; return the same point estimate for all seven future dates and warn about sparse/partial coverage. Fewer than three gives `INSUFFICIENT_DATA`. These numbers require fixture review and OPEN-13 resolution before becoming defaults.

Computing a forecast from available observations does not insert replacement observations into history. Record the actual trailing window, sample count, target basis, selected method, and policy version. Observed all-zero history can yield valid zero predictions; all-missing history cannot.

**Acceptance:** Known weekday fixtures, real zeros, missing weekdays, leap dates, sparse history, opt-in proxy behavior, and exactly seven future dates. Point-only baselines retain null quantiles and `interval_method=NONE`. No database, GPU, model download, or network is required for these unit tests.

## 7. Work package C — Chronos adapter, qualification, and fallback

Chronos-2 remains preferred where demonstrated feasible (BD-33). Keep imports lazy and optional. Read the actual lockfile and official interface for the installed version before implementation; the repository dependency range alone does not pin a checkpoint or demonstrate inference.

The adapter converts validated application series into the pinned provider's supported historical tabular/other native input, maps stable IDs, supplies permitted future covariates separately, requests seven dates and supported quantiles, and maps results back without mixing targets or sites. Record package/adapter/checkpoint revision, settings, grouping/batch identity, cutoff, and actual method per series. Provider-native preprocessing is not permission for backend imputation.

**PROPOSED:** Reuse a loaded checkpoint in controlled compute execution when compatible with termination and memory limits. This is subordinate to enforceable deadlines; do not use an unkillable shared inference thread. Batching must be frozen and recorded if results can depend on which series are grouped.

### Failure policy

- Invalid input, inconsistent revisions, ownership failures, or corrupt units fail validation; another provider must not hide them.
- Provider unavailability, inference failure/timeout, or invalid provider output may use a baseline only if the finalized policy permits that category and `allow_fallback` is true.
- Persist actual provider/fallback/error metadata per series; if fallback is unavailable or prohibited, retain an explicit unavailable result.
- A provider fallback within one attempt is different from retrying a lost worker. Interrupted jobs require manual retry against saved inputs (BD-12).

**Accepted deadline (BD-35, BD-38):** The entire forecast operation has 300 seconds, shared across all series, providers, preparation, validation, and publication. When fallback is permitted, stop the primary attempt by 270 seconds; the remaining allowance covers actual termination, baseline work, validation, and persistence. Early failure may fall back early. There is no additional 300-second budget and no guarantee the reserved time suffices.

**Separate Chronos qualification evidence:** Actual pinned inference, correct mapping/quantiles, preserved gaps or documented unavailability, failure/fallback tests, full required scope, latency/memory measurements, and chronological comparison. Distinguish cold loading, warm inference, cached reuse, and fixtures. Setup remains paused; this plan authorizes no downloads, containers, heavy builds, or benchmarks now.

## 8. Work package D — Output validation and uncertainty

**REQUIRED:** Successful series have exactly cutoff+1 through cutoff+7, unique keys, matching units/ownership, finite nonnegative central estimates, and valid nullable quantiles. When present, quantiles are ordered, including `p10 <= p50 <= p90` when all exist. A mean central estimate need not equal `p50`.

**PROPOSED OPEN-14 policy:** Reject nonfinite values, wrong dates, duplicates, and crossed quantiles. Negative predictions may be clipped to zero only if an explicitly selected/versioned postprocessing rule preserves auditable raw outputs and transformation counts. Until that rule is approved, reject negatives. Never clip invalid historical observations or silently repair quantile crossing.

Keep nonrounded predictions for evaluation and storage. UI integer formatting must not mutate them. Downstream planning rounds each scenario-adjusted daily demand upward before aggregation (BD-17); avoid a second rounding pass.

**Conservative planning (BD-28):** Use available demand upper quantiles according to the frozen policy; where absent, require an explicit presenter-selected buffer stored in the scenario. Buffer defaults, bounds, and granularity remain OPEN-16. Label each series as quantile-based, buffer-based, or unavailable; keep stored quantiles null when absent. A buffer is not a fabricated `p90`, and summed daily quantiles are not a calibrated joint stockout probability.

Uncertain donation quantile/buffer assumptions apply only in explicitly conditional scenarios. Confirmed-only primary planning does not need or silently include a donation lower-quantile supply assumption.

## 9. Work package E — Chronological backtesting and selection

**Difficulty:** Highest statistical risk; causal separation matters more than metric formulas.

For each historical origin, freeze the same eligible series/revisions, cutoff, availability-time rules, and future-known information for both methods. Generate seven dated predictions using only information available then. Score against observed held-out targets of matching identity and basis. Missing actuals remain unscored, with counts/reasons reported; never impute labels.

**Proposed example:** With 90 complete days, use expanding histories through days 62, 69, 76, and 83 and score the following seven days. Final windows, minimum counts, and an untouched later test period require OPEN-18. Shorter or gappy data needs a disclosed alternative, not invented sample sufficiency.

For `n` scored pairs with actual `y` and central prediction `y_hat`:

- `MAE = sum(abs(y_hat-y))/n`.
- `Bias = sum(y_hat-y)/n`; proposed sign convention: positive means overprediction.
- `WAPE = sum(abs(y_hat-y))/sum(y)`; report unavailable when the denominator is zero. For `n=0`, all metrics are unavailable.

Report metrics separately by target and product/unit, with per-series/fold details. An aggregate across incompatible units requires an explicitly justified normalization; do not silently sum bottle and meal errors. State whether aggregates are pooled or macro-averaged.

Use a common scored set for head-to-head claims, and also report each method's coverage/failure counts across the full eligible set. A Chronos request that fell back to baseline is a service-strategy result, not Chronos-only accuracy evidence. Report actual-provider and strategy metrics separately. Unknown requested demand cannot be scored as actual need using fulfilled values without the explicit proxy label.

**PROPOSED model selection:** Select separately by target/product or another approved comparable group on adequate chronological validation evidence; avoid noisy tiny per-series winners. Preserve a final later holdout where possible. Prefer the dependable baseline if evidence is inconclusive, recording the uncertainty. Thresholds and selection grouping remain OPEN-18. Any ensemble weights must be fitted before the final test period.

Only report empirical quantile coverage if measured on held-out observed values with sample counts. Synthetic evaluation is measured performance on simulated data, not evidence of real-world accuracy.

Acceptance includes post-origin observation/correction perturbation, no future-feature leakage, identical paired dates, zero-denominator handling, provider failures/coverage accounting, and preservation of a held-out selection boundary. Full backtests must obey serialized compute admission; define bounded fold batches/jobs under OPEN-30/35 rather than extending an operation indefinitely.

## 10. Work package F — Reuse, jobs, persistence, and API

### 10.1 Exact reuse and forced refresh (BD-29)

Reuse matching immutable completed results by default; preserve original `generated_at`, provider/checkpoint, and fallback provenance. A reuse event may have its own timestamp and audit/request linkage, but it is not new inference. Explicit presenter forced refresh bypasses result reuse and produces a new immutable result after computation.

**PROPOSED cache identity (OPEN-17):** Include organization, exact required/optional scope, source revision content/hash and knowledge cutoff, cutoff/horizon/calendar/unit versions, proxy/missing/preprocessing policies, covariates and availability, requested strategy/fallback permission, selection-policy version, provider/checkpoint/adapter/settings, grouping/batching, and any stochastic seed. Downstream scenario buffers do not belong in a forecast key unless they actually alter inference.

Define concurrent-request deduplication atomically, eligibility of older fallback results, model/config changes, and retention before implementation. Do not automatically evict or refresh fallback output merely because Chronos later becomes available; preserve provenance and use the agreed reuse policy or explicit refresh. Failed/incomplete output cannot masquerade as a reusable planning-ready result.

### 10.2 Durable job behavior

**REQUIRED (BD-11–12, BD-31, BD-34–38):** Forecasting, allocation, and comparisons are persisted background jobs. No synchronous computation fallback or in-memory-only task satisfies this requirement. Persist accepted input references and queue records before returning `202 Accepted` for new computation. Acceptance is not completion.

Suggested lifecycle: queued → running → terminal success/failure/interruption/expiry/cancellation, with separate attempt history and `planning_ready`. Exact enum names, ownership/leases, cancellation, retry endpoints, and partial child results remain OPEN-30; this arrow is not a finalized wire contract.

| Accepted runtime rule | Required effect |
|---|---|
| One active expensive operation | Forecasting and allocation share the same serialized slot; API reads/polling remain outside it. |
| At most two waiting; maximum queue wait 900 seconds | Persist bounded admission/expiry; exact queue-full/expired wire mappings remain OPEN-29/30. |
| Supervisor heartbeat every 5 seconds, unavailable after 15 seconds without update | Supervisor stays responsive during computation. Fresh heartbeat is not Chronos qualification. |
| Compute unavailable with usable API/DB | Reject new computation promptly with structured `503`; preserve saved reads and existing queued records. Stock operations do not depend on forecasting. |
| Forecast wall limit 300 seconds | Bound actual computation and cleanup/publication, with the 270-second primary deadline when fallback is allowed. |
| Worker ceilings: configurable 6 CPU equivalents, 8 GiB RAM | Verify effective limits later; ceilings exclude API/DB needs and do not prove a model fits. |
| Lost running worker | Persist interruption/failure; manual retry creates a linked attempt against saved inputs. Do not auto-retry interrupted jobs. Retain queued work subject to the agreed expiry rules. |
| Comparison is one top-level operation | Sequential methods: 15-second native solver search and 25-second whole-method limits each; 60-second comparison wall limit. Same snapshot and equivalent settings. |

Enforce deadlines with terminable computation and protection against stale-attempt publication. Merely cancelling a future/HTTP request or marking a record failed does not stop resource use. Finalize admission races, queue expiry after downtime, cancellation containment, and DB clock/ownership boundaries under OPEN-30/33/35.

### 10.3 Transactional publication and partial series

1. Freeze required/optional scope, inputs, policies, and exact source references; durably create/reuse the identified run/job.
2. Claim one attempt with explicit ownership; calculate under the shared deadline.
3. Attempt permitted fallback per failing series within the same operation budget.
4. Validate complete seven-day coverage for every required series and all numerical/identity constraints.
5. Transactionally persist per-series outcomes, immutable points, provenance, and completion/readiness. Results become visible as committed output, never a partially published success.
6. If a required series is unavailable, keep diagnostics but do not expose the run as planning-ready. Older successful runs remain available.

Optional unavailable series may be absent only under the frozen disclosed policy. A deliberately partial scenario must explicitly select/exclude scope and recompute denominators; missing data must not silently remove a beneficiary. Do not convert a failed full run into a partial planning success without an explicit authorized scope. Exact aggregate status representation remains OPEN-12/30.

### 10.4 Candidate API and observability contract

The following routes are **PROPOSED (OPEN-29)**, not implemented endpoints:

| Route family | Behavior |
|---|---|
| `POST /api/v1/forecast-runs` | Presenter-controlled submission, reuse/forced refresh options; new work returns durable `202` with run/job identifiers. Cache-hit response status/body remains to finalize. |
| `GET /api/v1/forecast-runs/{id}` | Persisted lifecycle/readiness, actual mixed-provider summary, original timestamps, diagnostics, input identity, evaluation references. |
| `GET /api/v1/forecast-runs/{id}/points` | Saved scoped points and per-series metadata; never inference. |
| Job polling/manual retry | Finalize paths, attempt linkage, expected versions, and structured errors with Task 05. |

Use presenter authorization at FastAPI even behind the proxy. Visitors inspect saved synthetic data only. Finalize session forwarding, CSRF, filtering/pagination, request limits, and generated TypeScript under OPEN-29/31/36.

Use correlated structured JSON logs and durable PostgreSQL job/audit records (BD-30). Include request/job/attempt/run/series context, requested/actual provider, fallback/reuse, queue/execution timing, limits, and safe error codes. Redact credentials, raw imported rows, and full snapshots. Distributed tracing is deferred. Process liveness, DB readiness, compute heartbeat, and model qualification remain separate; probes must not load/download models or run inference.

## 11. Frozen scenario and inventory handoff

**REQUIRED (BD-07–10, BD-15–17, BD-19, BD-41):** Fully freeze a scenario at creation. Pin selected forecast results, eligible inventory/lot versions, confirmed supply, routes/capacities, scope, policies, attributes, and assumptions in a validated versioned JSONB package with hash and source references. Store model identities, not weights. New operational inputs require a new scenario; historical reruns do not silently refresh data.

Primary planning uses eligible current stock and qualifying confirmed arrivals only. Donation forecasts remain charted predictions and may inform explicitly conditional scenarios. Unapproved supplier proposals stay outside confirmed resources. Do not automatically subtract confirmed arrivals from a donation forecast or add both blindly; event/pool identity and reconciliation policy remain OPEN-10/19. The earlier `max(0, forecast-confirmed)` heuristic is not adopted.

Inventory projection must distinguish daily demand, service, lost/unmet demand, received/on-hand stock, arrivals, uncertainty, transfers, eligibility, and expiry. A signed cumulative stock expression alone is insufficient: later arrivals cannot repair already missed demand, and cumulative deficits cannot be summed as independent daily shortages.

Forecast receipts do not guarantee an eligible lot, expiry date, or usable quantity. Conditional use requires explicit frozen eligibility/arrival/shelf-life/reconciliation assumptions. Keep these assumptions separate from model outputs and label the projection conditional.

Both allocation methods consume the same daily scenario-adjusted demand, rounded upward per day before aggregation, and the same operational snapshot. Fairness goals span the allocation window; RP groups use included positive-demand beneficiaries separately per product. Preserve explicit exclusions and proxy warnings in plan methodology. The full frozen scenario selects `HUB_ONLY` or `HUB_AND_PANTRY` explicitly, with no default. Both methods use the same mode. Hub origins are allowed in both; beneficiary origins are allowed only in `HUB_AND_PANTRY`, subject to protected source demand/reserves and no same-batch forwarding. Forecasting does not choose donor surpluses or bypass lot/ETA/FEFO/capacity constraints.

Plan review has no stock effect (BD-01). Draft supplier proposals remain in scope but their OPEN-26–28 details are paused; preserve after-arrival coverage and a coordinated simulated budget without choosing offer splitting, cover days, or priority rules (BD-22–24). Supplier arrival coverage cannot extend beyond available forecast dates without an explicitly specified new forecasting contract.

**Handoff acceptance:** No duplicated received/confirmed/uncertain supply; selected revisions and policies immutable; full and partial scope distinct; scenario changes do not mutate forecasts; new inputs create a new scenario; both methods use the same targets/hash; stockout probability is never inferred from an uncalibrated buffer.

## 12. Repository placement and inspected status

Use the canonical outer repository; do not create a second service or use a nested preserved copy.

```text
apps/api/app/services/forecasting/
  schemas.py
  preparation.py
  service.py
  postprocessing.py
  evaluation.py
  adapters/
    base.py
    seasonal_naive.py
    moving_average.py
    chronos2.py
apps/api/tests/forecasting/
apps/api/app/models/          # shared Task 04 domain persistence
apps/api/app/repositories/    # shared revision/snapshot/result access
apps/api/app/routers/         # Task 05 public API
apps/api/migrations/          # Alembic after schema gates
packages/contracts/          # generated public TypeScript boundary
```

Placement within these boundaries is proposed. Reuse existing job/orchestration modules once their ownership is settled; do not add another queue product or deployment service by implication.

### Repository inspection for this revision

GitHub branch discovery returned `main` and `VP`. Both inspected READMEs had blob SHA `efcf8e4ae5650f0367f90b93fa04565ef5217014` and described a scaffold. `main` contains the detailed backend specification; it was not found at the same path on `VP`. Therefore use the attached checkpoint and current `main` backend specification rather than assuming VP contains the latest design.

| Inspected source | Finding |
|---|---|
| [Main backend specification](https://github.com/gbw30/PantryPulse/blob/main/docs/pantrypulse/BACKEND-SPEC.md), blob `a869b58c0754c89bf820f37e55dd7b124bb303de` | Confirms accepted runtime, data, proxy, scenario, and qualification directions; unfinished schemas remain OPEN. |
| [VP API entrypoint](https://github.com/gbw30/PantryPulse/blob/VP/apps/api/app/main.py), blob `fdb20e283417e17395f43063efdb55d698f4fd11` | Implements only process-health liveness. This is not domain/DB/solver readiness. |
| [VP dependency declaration](https://github.com/gbw30/PantryPulse/blob/VP/apps/api/pyproject.toml), blob `cdc9a76afbfe44720fa1886ad9ffc7a3b2768c0a` | Optional `chronos-forecasting>=2.0,<3`; declaration is not installed-version/checkpoint qualification. |
| [Main research architecture](https://github.com/gbw30/PantryPulse/blob/main/docs/architecture/0001-v4-research-first.md), blob `a9233306ee1400aa07b5f31cdfa0cbf4b29487c9` | Canonical app boundaries and independent mathematical gate; no inference on startup/GET. Later explicit BD selections control conflicting illustrative values. |
| [Main contracts boundary](https://github.com/gbw30/PantryPulse/blob/main/packages/contracts/README.md), blob `4c80709867166cbea90ad664a906de4970a5f3ce` | Pydantic/OpenAPI authority; domain contracts not yet generated in this inspected document. |

Inspection was targeted, not an exhaustive branch/code audit. Branch URLs may change; blob SHAs identify the inspected file contents. No application acceptance tests, setup, migrations, inference, or solver execution were run for this documentation revision. No repository files were changed.

## 13. Execution sequence and deliverables

| Step | Priority / owner | Deliverable and dependency gate |
|---|---|---|
| 0 | Blocking; Tasks 00/03/04/05 | Resolve necessary OPEN-04/06/07/12–18 contract details; record versions and sample payloads. Do not reopen accepted BD directions. |
| 1 | P0; Tasks 03/04 | Small deterministic unit fixtures plus expanded six-beneficiary/two-product receipt/demand history; explicit coverage, missingness, and proxy labels. |
| 2 | P0; Task 03 | Pure preparation, revision/aggregation interface, calendar/mask validation, baseline and controlled sparse fallback. |
| 3 | P0; Tasks 04/05 | Isolated PostgreSQL migrations/integrity tests, immutable input/results, durable jobs, admission/containment, proxy/public contract integration. Depends on finalized schema/job details. |
| 4 | P0; Task 03 | Chronological baseline evaluation with genuine counts/metrics and leakage tests; provider-neutral evaluation harness. |
| 5 | P0 core; Tasks 03/04/05 | Live baseline → persisted forecast → frozen scenario → projections; reuse, force refresh, provider-failure fallback, interrupted-job manual retry, and deadline tests. |
| 6 | Separate Chronos qualification; Task 03 | After explicit resumption of setup, pin and verify actual Chronos input/missing handling, inference, output, failure boundaries, resources, and comparative evaluation. Track unverified status meanwhile. |
| 7 | Mandatory research/integration gate; Tasks 01/02/04/05 | Independent mathematical evidence and both live solver integrations on identical frozen data; do not relabel classical output as research output. |
| 8 | Acceptance; all owners | Expanded saved-input → forecast → shortage → paired allocation → disruption/new frozen scenario → review/reset demonstration; preserve versions and disclose limitations. |

Required artifacts: reviewed typed input/output examples; revision/coverage/target policy; deterministic adapters; adapter/fallback evidence; PostgreSQL/API contract tests; reuse and job evidence; measured evaluation report; frozen scenario hash and demo run IDs; acceptance ledger distinguishing core, Chronos, research, and performance outcomes.

Work can be split among preparation/baselines, provider integration, evaluation, and persistence/API owners once sample contracts are agreed. Chronos setup difficulties must not block pure baseline work. Supplier planning and hosting/model setup remain paused until separately resumed.

## 14. Remaining decisions and traceability

This revision supplies concrete proposals, not additional accepted interview decisions. Record resolutions under existing OPEN IDs and update the backend specification/checkpoint consistently.

| Gate | Remaining specification | Existing accepted boundary |
|---|---|---|
| OPEN-04–08 | SQL types/count precision, ownership, timezone/day boundaries, exact authoritative revision/coverage rules, receipt corrections | Daily demand plus individual receipts, append revisions, received target, separate stock posting. |
| OPEN-09–10 | Transaction/idempotency/concurrency and conditional supply reconciliation | Exactly-once explicit posting; confirmed-only baseline. |
| OPEN-12 | Exact typed contracts, per-series outcomes, aggregate readiness | Application contracts; seven dates; missing required input cannot silently vanish. |
| OPEN-13 | Seasonal eligibility, proposed 14-day/three-sample sparse rule, mixed proxy history, failure categories | Baseline mandatory; proxy opt-in; preserve gaps. |
| OPEN-14 | Estimate/quantile fields, clipping permission/raw retention, validation | No fabricated quantiles or silent historical repair. |
| OPEN-15 | Covariate catalog, pinned provider API/checkpoint, grouping/settings | Provider-native handling stays inside adapters. |
| OPEN-16 | Buffer bounds/defaults/granularity and mixed mode labels | Explicit selected buffer only; missing quantiles remain null. |
| OPEN-17 | Canonical identity, atomic deduplication, fallback-result reuse/retention | Exact immutable reuse by default; explicit forced recomputation. |
| OPEN-18 | Evaluation windows, minimum samples, aggregation/sign conventions, selection/coverage protocol | Chronological measured evidence; separate actual-provider qualification. |
| OPEN-19–22 | JSONB schema/hash, staleness, event ordering, donor protection and capacity | Fully frozen scenarios; forecast-derived targets; both explicit modes with no default; identical paired inputs. |
| OPEN-23–25 | Complete objective/parameter/numerical policy and independent verification | Preserve BD-15–21, including 10,000 fixed-point scale; Task 03 does not implement these objectives. |
| OPEN-29–33 | Wire catalog, job states/ownership/retry/cancellation, access/reset/retention, probes/audit | Background jobs, proxy, presenter-only mutation, manual retry, logs/audit and heartbeat. |
| OPEN-34–36 | Final fixture/test/evidence contracts, effective process limits, generated-contract/migration workflow | Accepted ceilings and independent core/Chronos/research gates; disclose responsiveness misses. |

OPEN-02/03 remain deferred; OPEN-26–28 remain paused. OPEN-01 is resolved by BD-41: both explicit transfer modes are required, with no default. Do not reopen these while implementing unrelated forecasting work.

### Evaluation coverage checklist

The consolidated evaluation's retained structures remain: separate demand/donation observation boundaries, forecast runs and points, target identity, source/version provenance, nullable uncertainty, fallback warnings, and application-level service contracts.

Its corrections are addressed in sections 3–10: donor versus receiving site; actual received quantity and event grain; concrete proposed SQL types; source classification and basis; demand consistency; proxy opt-in; duplicate/revision selection; exact snapshots; per-series provider/availability; job timing/errors/partial readiness; defined DailyObservation; preserved gaps; covariate availability; bounded preprocessing; run/result IDs; median semantics; finite/date/quantile validation; null baseline intervals; organization boundaries; and explicit `horizon_days`/`data_cutoff_date` names. Unresolved implementation specifics remain visibly proposed and assigned to OPEN gates.

## 15. Acceptance matrix and evidence rules

All application outcomes below are **NOT RUN / UNVERIFIED in this documentation task**. Add command, timestamp, fixture/config/hash/version, PASS/FAIL/UNVERIFIED, and evidence location when executed. A skipped test or mock proves only its stated scope.

| ID | Test | Required result |
|---|---|---|
| F-01 | Full required fixture and daily forecast identity | Seven future dates per required usable series; correct units/targets/site-local calendar. |
| F-02 | Unknown requested demand | No silent substitution; opt-in proxy and warnings persist to plan. |
| F-03 | Missing date versus observed zero | Distinct canonical values; no backend imputation; no-receipt day needs coverage evidence for zero. |
| F-04 | Invalid history/components/organization | Nonnegative/consistency/scoped-FK errors are actionable. |
| F-05 | Two receipts, duplicate receipt, corrected receipt | Genuine events sum once; duplicate rejected; exactly one revision set selected. |
| F-06 | Historical import and new receipt posting | Import does not alter stock; valid posting exactly once with lot/ledger/audit; receipt lines atomic. |
| F-07 | Seasonal and sparse baselines | Deterministic expected values, explicit insufficiency, point estimates not mislabeled medians. |
| F-08 | Forced provider failure, fallback allowed/prohibited | Actual method/reason truthful; explicit failure if no permitted usable fallback. |
| F-09 | Invalid provider dates/values/quantiles | Reject or apply only approved auditable postprocessing; no fabricated intervals. |
| F-10 | Mixed providers and unavailable series | Per-series outcome/version retained; aggregate label honest; missing required series blocks readiness. |
| F-11 | Backtest changes after origin, including revisions/features | Earlier available input and forecast unchanged; retrospective limitations disclosed. |
| F-12 | Evaluation alignment, missing/zero actuals, provider fallback | Same paired scored set plus full coverage counts; WAPE unavailable when undefined; fallback is not Chronos-only evidence. |
| F-13 | Atomic publication failure/stale attempt | No incomplete planning-ready success or stale-worker publication; old results survive. |
| F-14 | Exact reuse/forced refresh/concurrent submissions | Original generation/provenance retained; identity-sensitive reuse; explicit refresh produces new inference/result; dedup follows finalized policy. |
| F-15 | Changed inventory/config/forecast and scenario replay | Existing scenario unchanged; new operational inputs require new scenario; partial scope explicit. |
| F-16 | Confirmed/received/conditional donation overlap | No duplicated supply; uncertain receipt forecast never becomes physical inventory by itself. |
| F-17 | Conservative quantile/buffer mixed series | Explicit scenario buffer; null missing quantiles; no calibrated probability claim. |
| F-18 | GET, public visitor, and presenter mutation | Saved reads never compute; backend authorization enforced behind proxy. |
| F-19 | Busy worker, full queue, stale heartbeat | One active/two waiting; 900-second wait enforced; healthy busy distinguished from unavailable; new work gets structured 503 when unavailable. |
| F-20 | Lost running worker/manual retry | Interrupted/failed outcome with linked saved-input retry; no automatic retry; queued work preserved under defined expiry policy. |
| F-21 | Primary at 270 seconds/whole forecast at 300 | Actual primary termination/cleanup bounded; fallback/validation/persistence share remaining allowance; no extra budget. |
| F-22 | Effective resource limits/logs/probes | Recorded worker limits; responsive heartbeat/polling; correlated redacted logs/audit; no model work in probes. |
| F-23 | Live core with PostgreSQL/API and both solvers | Baseline/fallback → frozen projections → same-input paired results; 15/25/60-second solver/method/comparison ceilings enforced. |
| F-24 | Independent research gate and expanded demo | Mathematical oracles, FEFO/conservation/arrival checks, AP/RP boundaries/ablations, and required population pass; failed research method stays failed. |
| F-25 | Actual pinned Chronos qualification | Real inference and evaluation recorded separately; mocks/cache/fixtures are insufficient. |
| F-26 | Performance targets on expanded scope | Measure saved-read 1-second and per-method 5-second targets; disclose misses. Hard limits/correctness/research gate remain mandatory. |

### First implementation session, when coding resumes

1. Agree sample application payloads and the minimum dependent OPEN-12–14 policies.
2. Build small in-memory demand and receipt-derived donation fixtures with gaps, real zeros, and explicit proxy opt-in.
3. Implement pure calendar/validation functions and deterministic baseline/sparse behavior with expected-value tests.
4. Hand Task 04/05 the same payloads, errors, revision references, and readiness rules.
5. Add chronological baseline evaluation before claiming accuracy; integrate real PostgreSQL/jobs before claiming the live core works.

Do not resume paused model/hosting setup, supplier selections, or complex solver work ahead of its independent gate merely because this plan now describes those future tasks.

## 16. Sources and documentation status

Primary supplied sources: `PantryPulse_V4_Forecasting_Implementation_Plan(1).md` (previous version), `FORECASTING-PROPOSAL-EVALUATION.md`, and `BACKEND-DESIGN-CHECKPOINT(1).md` (BD-01–40). Repository sources inspected for this revision are listed with file identities in section 12.

[V4 requirements](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) and the [Task 03 guide](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.4q4ahys8aav9) remain authoritative reference pointers inherited from the supplied documents; those Google Docs tabs were not re-read for this revision. Prior page numbers are historical pointers, not verified current pagination.

The evaluation points to the [official Chronos-2 implementation](https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py). This is a future adapter-verification reference, not a claim that its current API or the installed package was tested during this documentation task.

This revision updates the forecasting plan only. It preserves unresolved choices, accepted decisions, supplier/setup pauses, and the distinction between documentation, implementation, and measured evidence.
