# PantryPulse OR implementation design

**Draft 1.1 • repository refresh October 24, 2026 America/New_York • implementation blueprint, not implemented code**

Revision scope: use the forecasting/projection core now integrated on main, preserve PR #51 numerical/evaluation regressions, and distinguish the static design lab from connected OR UI. Mathematical algorithms and selected OR decisions are unchanged.

Implement the mathematics in `01_OR_Mathematical_Specification.md` inside the existing FastAPI application. This file supplies exact module responsibilities, algorithms, persistence, APIs, process behavior, scripts and test strategy. All new contracts below are selected provisional draft choices under the user's instruction; preserve their `OR-DEC` markers. The third document supplies Codex's ordered execution contract.

No repository was modified by this document-creation task. Script paths and endpoint names labeled NEW below must be created during implementation; they do not exist merely because they appear here. Reuse equivalent landed upstream code after inspection, avoiding duplicate schemas, queues, stock authorities or generated clients.

## 1. Compatibility and source ownership

Use main `f3946c726e53fa546be1400d80ab717fcb2c3468` as the reviewed integrated baseline. Merged PR #51 incorporates PR #49's forecasting core and PR #50's design lab with review corrections; the original #49/#50 PRs remaining open does not mean their content is absent from main. Use main directly, not the older `forecasting` head `bed0854` or the older design-lab branch. VP `b82f85f` remains documentation-only and is now diverged two commits each way. Recheck actual refs before execution; do not merge/replay already-integrated features. `be/ready-1-6` is already merged.

Reuse main's `AllocationMethod`, `TransferMode`, `TransferModeSelection`, `check_mode_route`, `round_daily_targets`, `quantize_weighted_deficit`, `classify_solver_status` and history semantics, plus its merged forecasting preparation/provider/evaluation/handoff modules and experimental inventory projection. Do not broaden pure helper contracts or expose internal exceptions directly as HTTP errors. Main still has no complete domain SQL schema, public forecast publication, durable executor, complete operational scenario or OR engine. Chronos remains an unavailable adapter boundary. Code integration is not live database/API integration.

### 1.1 Main integration facts and adapter obligations

| Existing main contract or change | Required OR integration |
|---|---|
| `forecasting/schemas.py`: frozen experimental-v1 models; `SeriesKey`, `SeriesScope`, actual provider/basis, nullable genuine quantiles and float `Quantity` | Adapt existing types; do not rewrite the forecast core. OR's exact-decimal payload remains a separate versioned boundary under OR-DEC-010 |
| `ForecastOutput.ready_for_publication` | Computational coverage only; a persisted publisher must establish committed planning readiness |
| `ForecastHandoff`, `freeze_handoff`, `verify_handoff` | Validate and retain original identity; add the full operational snapshot and separate hash rather than overwriting the experimental forecast hash |
| `PlanningSeries.days`: daily units, float unrounded values, choice/provenance | Without additional OR demand overrides, assert equivalence to existing targets. With overrides, derive from source points/choices and ceil once into an OR-owned schema; never scale already-rounded units or mutate PlanningSeries to defeat validation |
| `DemandChoice`: CENTRAL/CONSERVATIVE and optional explicit buffer | Preserve per-series upper-quantile versus buffer interpretation and required-series/partial-scope validation |
| Existing `ProjectionLot`/`project_daily` | Extend through a compatible kernel/wrapper; network shipments, donor trajectories, transit and capacities are still new work |
| Moving-average exact Fraction sum/mean before final float conversion | Preserve constant-mean and genuine-above-integer behavior; do not add an epsilon or floor to hide arithmetic errors |
| Held-out truth permits mixed bases for mismatch accounting only | Keep training proxy authorization strict; report mismatches/missing actuals and exclude them from scored pairs |

`schemas.py` and `handoff.py` are unchanged from the originally reviewed forecasting branch; the numerical fix is in `adapters/moving_average.py`. The new interface work is OR/public/persistence adaptation. Keep regression tests where seven values of 29 produce target 29, sparse fallback preserves the constant, and genuine values just above 29 still ceil to 30. V5/backend spec retain historical consolidation/review-candidate status wording; use actual main code and PR #51 for implementation state. No backend checkpoint, BE helper, domain migration or accepted objective-policy change landed in this refresh.

The service's input boundary is a **committed immutable OR input package**, containing the complete normalized operational data needed to freeze a scenario. It can originate from (a) real upstream inventory/forecast read adapters or (b) explicit, validated SIMULATED packages for demo/tests. The latter is a real persistent OR workflow but does not qualify live upstream integration. Never create a second live inventory ledger to make an adapter pass.

Read ports:

```python
class ForecastReadPort(Protocol):
    def read_committed(self, org_id: UUID, result_ids: tuple[UUID, ...]) -> FrozenForecastSet: ...

class InventoryReadPort(Protocol):
    def read_committed(self, org_id: UUID, expected_revision: str) -> FrozenStockSet: ...

class OperationalReadPort(Protocol):
    def read_committed(self, org_id: UUID, expected_revision: str) -> FrozenNetworkRules: ...
```

Each read result carries immutable source revisions and content, not only a mutable ID. LIVE package creation must hold the authoritative source locking/revision contract long enough to guarantee a consistent set or retry before commit. If source schemas/transaction semantics are unavailable, fail `SOURCE_INTEGRATION_UNAVAILABLE`; preserve the explicit simulated path. A repository absence is not evidence to map guessed tables or use “latest” outside a transaction. OR does not implement historical import, receipt posting/correction, supplier selection, or Chronos setup as side work.

## 2. Files and callable contracts

All paths below are relative to repository root. Split modules further only when useful. Entries are NEW except the explicitly existing inventory projection. Reconcile new names with landed code, preserving one owner for each calculation.

| NEW location | Public internal contract |
|---|---|
| `apps/api/app/schemas/or_inputs.py` | Frozen strict `ORInputPackage`, `ORScenarioPayload`, `ORPolicy`; validated nested source, demand, lot, route and capacity models |
| `apps/api/app/schemas/or_outputs.py` | `MethodOutcome`, `TransferAssignment`, `ProjectionReport`, `VerificationReport`, `ComparisonResult`, HTTP job/error models |
| `services/optimization/decisions.py` | Registry of OR-DEC-001…020, statuses, affected policy fields and versions; no silent defaults outside seeded policy |
| `services/optimization/canonical.py` | `canonical_bytes(payload) -> bytes`, `operational_hash(payload) -> str`, exact numeric encoding |
| `services/optimization/forecast_adapter.py` | `adapt_forecasts(committed, choices) -> tuple[DemandSeries,...]`; actual provider/basis and source-literal retention |
| EXISTING `services/inventory/projection.py`, extended or reconciled successor | Add `simulate(package, assignments, include_planned_inbound=True) -> ProjectionReport` while retaining `project_daily` compatibility; no solver or DB imports |
| `services/optimization/candidates.py` | `prepare_problem(snapshot) -> PreparedProblem`; baseline, candidate order, bounds, exclusion diagnostics, common references |
| `services/optimization/packing.py` | Pure route-order FEFO packing for replay; CP encoding lives separately |
| `services/optimization/numerics.py` | Exact fraction/policy checks, interval-bound report, rational objective coefficient compiler |
| `services/optimization/constraints.py` | `build_physical_model(problem) -> PhysicalModel`; no method-specific weights/flags |
| `services/optimization/classical_gp.py` | `attach_classical(model, policy) -> ObjectiveHandles` |
| `services/optimization/egp_pi_inspired.py` | `attach_research(model, policy) -> ObjectiveHandles` |
| `services/optimization/extract.py` | `read_candidate(status, solver, handles) -> Candidate`; invoke BE-05 first |
| `services/optimization/verify.py` | `verify(problem, candidate, method) -> VerificationReport`; replay physical quantities without importing model/constraint modules |
| `services/optimization/metrics.py` | Independent exact/common metrics and decomposition from checker replay |
| `services/optimization/service.py` | `solve_one(snapshot, method, settings) -> MethodOutcome`; pure worker entry with bounded native search |
| `services/optimization/compare.py` | Assemble independent method outcomes and common differences; no hidden second solves |
| `services/jobs/*` | Shared PostgreSQL admission, supervisor, attempt state, containment, publication and manual retry |
| `models/or_*.py`, `repositories/or_*.py` | Immutable records and atomic writes; no calculation reimplementation |
| `routers/or_*.py` | Presenter-authorized submissions/reviews, saved reads, errors and OpenAPI |
| `packages/contracts/*` | Generated TypeScript, OpenAPI snapshot and generation/check script |
| `data/demo/or-v1/*` | Full, pantry-surplus, ETA/expiry, shared-capacity and ablation fixtures; all synthetic |
| `docs/optimization/*` | These three docs, decision/mapping/proof/evidence records and generated methodology schema |

Main's existing projection depends on experimental `PlanningSeries`. Refactor its pure recurrence into the accepted inventory input contract while retaining `project_daily` compatibility and regression tests; OR should not couple its model directly to that forecasting class. The experimental wrapper permits null expiry, while OR-DEC-001 excludes it. Use explicit versioned policy in the shared kernel or filter at the OR adapter; do not globally change the experimental behavior and silently break saved handoffs. Test both the preserved old policy and deliberate OR-policy difference.

## 3. Exact data contracts

Use Pydantic v2 frozen models, `extra='forbid'`, strict integer/boolean fields, explicit enum validation and immutable tuples. HTTP UUID/date strings are parsed deliberately; do not enable global strict mode in a way that rejects all valid JSON UUIDs. Reject booleans in quantity fields, NaN/infinity, unknown IDs, duplicates, cross-organization references and unordered/duplicate date coverage. Serialize ratios as `{numerator:int,denominator:positive_int}` and decimal estimates as canonical strings. Every model has a schema-version literal.

### 3.1 Input package

Required top-level fields:

```text
schema_version = "or-input-v1"
organization_id, dataset_id, source_kind = SIMULATED | LIVE
source_revision_token, source_refs[], snapshot_as_of
operational_timezone, first_planning_date
sites[], products[], forecasts[], inventory[], confirmed_arrivals[]
routes[], capacities, reserves[], vulnerability_attributes[]
source_coverage, source_manifest_hash, provenance_warnings[]
decision_ids[]
```

- Site: UUID, role HUB/BENEFICIARY, organization ID, name, operational timezone matching network zone, source revision.
- Product: UUID, base-unit code, handling coefficient 1–1000, source revision. Require two products for full demo; validate v1 bound ≤2.
- Forecast series: immutable committed result/run/source IDs, organization/site/product/unit, seven explicit dates, actual provider, basis, source classification, estimate kind, central literal, nullable genuine quantiles, interval method, cutoff/as-of and committed readiness metadata. Preserve required-series outcome/coverage; never turn unavailable series into zero.
- Inventory: original lot UUID/product/site/base unit, physical/free/reserved/committed/held integer components, known expiry or explicit exclusion, eligibility, original receipt/source line ID, original source revision, dispatchable-at-snapshot flag. Disjoint parts must reconcile; snapshot never changes original stock. Require commitment obligation/scope references. Reject `COMMITMENT_SERVICE_OVERLAP_UNSUPPORTED` when quarantined units also serve included demand; do not silently drop that fixed service or alter forecasts to hide overlap (OR-DEC-005).
- Arrival: unique source receipt/supply line identity, site/product/unit, confirmed status and revision, day/expiry/eligibility, quantity; not already posted in inventory. Expected/conditional records remain contextual exclusions.
- Route: source/destination IDs, enabled, ETA offset 0–2, residual handling capacity, per-product unit cost in integer minor units, explicit cost-unit code shared across routes. No self route, missing product price or inferred reverse route.
- Capacities: original/fixed-used/residual source, route, receiving/day, storage/day and global handling quantities, residual equality and fixed-consumption provenance. No nullable “infinity”; use a validated explicit finite bound. Cost budget may be null.
- Reserve: every site/product has seven nonnegative integer floors, including explicit zeros. HUB own operational demand is separate from beneficiary goals.
- Attributes: at least two prepared score values per beneficiary, coefficient identity, raw/source note, transformation description/version and classification. Missing scores fail, not zero vulnerability.

Precision: accept source estimate literals with ≤28 significant digits and ≤18 fractional digits, bounded nonnegative and finite. Scenario multipliers/buffers have ≤4 fractional digits and range 0–3 and 0–1 respectively (provisional validation limits under OR-DEC-010). Multiply finite decimals under local precision 64 and verify no rounding flags; then BE-03 ceilings dates. Float adapter uses `Decimal(str(value))`, records `LEGACY_FLOAT_LITERAL`, and rejects out-of-range precision rather than clipping or pretending to recover original values.

### 3.2 Scenario creation

Request: `input_package_id`, required exact `transfer_mode`, explicit `planning_days` 1–3, `policy_id`, per-series demand choices/multipliers, explicit exclusions/partial-scope declaration, `intent=CURRENT|HISTORICAL_REPLAY`, expected source revision for CURRENT and idempotency key. Policy includes `purpose=PRIMARY|ABLATION`; production paired submissions require PRIMARY and positive AP/RP penalties. Zero-gamma diagnostic policies are accepted only by explicitly labeled offline ablation paths and cannot be published as the primary research comparison. Never include method as part of transfer mode. Resolve choices before freezing; dates outside input scope are invalid.

Persist a complete `or-scenario-v1` payload with original package content, final daily unrounded and integer targets, window, mode, loading order, exact policy, common normalization references, source tokens, decision IDs and hash. Exclude only database IDs and record-created timestamps from the content identity. Include `snapshot_as_of`, actual source timestamps, calendar, dataset and all substantive scenario inputs.

Canonicalization algorithm: revalidate; emit UTF-8 JSON with sorted object keys, no whitespace, no floats/NaN, lowercase UUIDs, ISO dates, UTC instants with fixed six fractional digits plus Z, normalized decimal strings (no exponent, no negative zero), reduced rationals and sorted unordered identity collections. Preserve semantically ordered date/loading arrays. Hash these bytes with SHA-256. Do not hash arbitrary `model_dump_json()` output without canonical normalization. Store bytes/payload and hash; verify on every worker load.

### 3.3 Result contracts

Each method result includes `schema_version`, plan/scenario/job/attempt IDs, method, transfer mode, operational/policy/settings hashes, decision IDs, native status nullable, execution outcome, solver/package versions, search/total wall duration, termination reason, objective rational and integer/scale, decomposition, native bound/gap when meaningful, candidate/check report references, assignments, per-date/goal metrics, warning/error codes and historical/stale flags.

No vectors in unsuccessful/non-readable native results. `FEASIBLE` may publish only after independent verification and within deadlines; state that optimality is unproven. Preserve a valid zero-transfer vector explicitly. Failure messages must not expose credentials/raw snapshots or model-internal data to public visitors.

## 4. Core algorithms and CP-SAT construction

### 4.1 Preparation

```python
def prepare_problem(snapshot):
    validate_strict(snapshot)
    verify_content_hash(snapshot)
    require_complete_dates_units_sources(snapshot)
    policy = compile_exact_policy(snapshot.policy)
    baseline = simulate(snapshot, assignments=())
    candidates, exclusions = build_mode_eta_eligibility_candidates(snapshot, baseline)
    # OR-DEC-004 [PROVISIONAL]: loading policy is part of the feasible set.
    order = sorted_routes_per_source_product(candidates, key=(-eta, destination_uuid))
    refs = freeze_cost_and_waste_references(snapshot, candidates)
    bounds = prove_integer_activity_bounds(snapshot, policy, candidates, refs)
    require(bounds.all_abs_activity < 2**60)
    return PreparedProblem(snapshot, baseline, candidates, order, refs, bounds)
```

Baseline simulation is allowed to show unavoidable unmet demand; do not reject scarcity. Reject invalid negative balances or duplicate source accounting. A baseline storage violation may be a hard feasibility issue solvable by transfers; preserve the diagnostic rather than clamping it.

### 4.2 Packing encoding

For each route define integer load y and remaining request R0=y. For each compatible ordered source lot create x in [0,min(lot_Q,route_upper)]. Enforce `x=min(current_balance,Rprev)`, next balance/current request equations, and final request zero. Derive destination sublot quantity=x. Every original lot's route residual chain is shared across all destinations. No constant initial balance is reused independently for each route.

Use `model.add_min_equality` on nonnegative bounded quantities; constants may be affine expressions where supported by the locked version. Make each intermediate variable explicit for inspection. Build this once for both methods. Route-order exceptions come from eligibility metadata, never a tiny cost penalty.

### 4.3 Projection encoding

Unroll site/product/day FEFO simulation over local residual lots, confirmed arrivals and received sublots. At each point use exact min equalities for consumption, and deterministic 0 or full balance for expiry based on frozen dates. Add daily demand/served/unmet equalities. Create explicit in-transit and lot-lineage accounting; received sublots cannot enter source packing chains. Constrain each proposed sublot to be completely consumed within W and not expire within W.

Construct separate donor-protection trajectories without planned inbound, with the same source outbound residual. Reify `sending` both ways (`sum_y>=1` if true, `sum_y==0` if false). Enforce seven days of full own service and reserve floors for sending beneficiaries; enforce applicable own-demand/reserve protection for hubs as well. Add residual route/source/global/receiving and end-of-day storage limits. All physical constraints precede objective attachment.

### 4.4 Integer deficit and indicator encoding

Reference API usage sketch, to verify against the locked OR-Tools version:

```python
q = model.new_int_var(0, 20_000, name)
model.add(D*q <= 10_000*n_v*u)
model.add(10_000*n_v*u <= D*(q+1)-1)
ap = model.new_bool_var(f"ap_{name}")
model.add(q >= A+1).only_enforce_if(ap)
model.add(q <= A).only_enforce_if(ap.Not())
rp = model.new_bool_var(f"rp_{name}")
relative = N*q - group_q_sum
model.add(relative >= N*T+1).only_enforce_if(rp)
model.add(relative <= N*T).only_enforce_if(rp.Not())
# excess = max(0, 10000*flag_count - cap_bp*N)
# Z = max(all positive-goal q), explicit Z=0 when there are none
```

Use `add_max_equality` for max/excess and floor inequalities for cost/waste normalization. Compile the rational objective coefficients using Fraction, denominator LCM and coefficient GCD reduction; return the exact scale conversion. Run interval bounds on emitted expressions and `model.validate()` before solve. Do not use a float objective merely because the Python API accepts one.

### 4.5 Solve and verify

Default settings: one search worker, fixed seed 0, 15-second native search ceiling, locked package version; freeze identical settings for the pair. Native search receives the minimum of 15 seconds and remaining method/pair time minus termination/check/publication allowance. Method order is CLASSICAL_GP then EGP_PI_INSPIRED; store order as protocol metadata. A primary comparison has exactly those two methods.

Extract through BE-05, then reconstruct route y and lot x. Independent verifier replays the plain-Python packing and daily simulation from scratch, checks every input reference, route/capacity/donor/FEFO/no-relay/full-consumption rule, recomputes deficits/flags/objective via Fraction and compares the solver's claimed auxiliaries. It must not import `constraints.py` or objective attachment code. Also compare tiny full feasible sets with an independent brute-force oracle; a common bug in simulator/model must not pass through the same helper twice.

`solve_one` returns structured output but never publishes to DB. A worker child process has no database credentials or responsibility for stock mutations. The parent supervisor validates and publishes only owned, timely attempts. A method failure has no fallback to the other objective.

## 5. Concrete PostgreSQL design

Use SQLAlchemy 2/Alembic and actual PostgreSQL, not SQLite. Reconcile existing upstream schema before adopting these **NEW provisional** tables. UUID PKs generated in Python, UTC timestamptz, JSONB payloads, explicit CHECK constraints for enumerations, nonnegative BIGINT counts, SHA-256 lowercase hex strings, and restrictive deletion unless isolated reset explicitly permits it. Use composite `(organization_id,id)` uniqueness/FKs where needed to prevent cross-org references.

| Table | Required columns and integrity |
|---|---|
| `or_input_packages` | id, organization_id, dataset_id, schema_version, source_kind, revision_token, payload JSONB, content_hash, source_manifest_hash, created_at/by; immutable; unique `(org,dataset,content_hash)` |
| `or_policies` | id, organization_id, version, payload JSONB, hash, decision_ids JSONB, created_at/by; unique `(org,hash)`; immutable |
| `or_scenarios` | id, organization_id, input_package_id, policy_id, schema_version, transfer_mode CHECK, planning_days CHECK 1–3, intent, revision_token, org_epoch, payload JSONB, operational_hash, policy_hash, created_at/by; immutable input records; index `(org,created_at,id)` |
| `compute_control` | singleton id, owner UUID, generation BIGINT, heartbeat_at, lease_until, active_job_id nullable; one global expensive slot across forecast/allocation/comparison |
| `compute_jobs` | id, organization_id, kind, scenario_id nullable for non-OR jobs, state, input_hash, settings_hash, protocol_version, admitted_at, queue_deadline, started_at/finished_at, attempt_count, cancel_requested_at, active_dedup_key; index `(state,admitted_at,id)` |
| `compute_attempts` | id, job_id, attempt_no, parent_attempt_id nullable, owner, generation, lease_until, org_epoch, started/finished, outcome/error_code, timing JSONB; unique `(job_id,attempt_no)`; only one live owned attempt per job |
| `request_keys` | org, actor_id, route_operation, key, request_hash, job_or_resource_id, created_at; unique `(org,actor,route_operation,key)`; mismatched reuse is 409 |
| `or_plans` | id, org, scenario_id, job_id, attempt_id, method, native_status, outcome, settings_hash, result JSONB, result_hash, verified_at, created_at; unique `(attempt_id,method)`; result includes decision/policy/source identity |
| `or_transfers` | id, plan_id, original_lot_id UUID (immutable snapshot reference), source/dest/product UUID, unit, quantity CHECK >0, departure/arrival dates, expiry, source_revision, cost_minor; no self-transfer; aggregate uniqueness `(plan,lot,source,dest,product)` |
| `or_verifications` | id, plan_id unique, verifier_version, passed, checks JSONB, objective JSONB, report_hash; only passed plans are published with vectors |
| `or_comparisons` | id, job_id/attempt_id unique, scenario_id, first_plan_id nullable, second_plan_id nullable, outcome, payload JSONB, created_at; method identities and shared hashes validated |
| `or_reviews` | id, plan_id, actor_id, action REVIEWED/REJECTED, note ≤2000 chars, plan_result_hash, created_at; append-only; no inventory trigger |
| `audit_events` or existing equivalent | actor, action, org/resource IDs, source/expected/actual versions, time, safe details; transactionally link mutations/publication/review |
| `presenter_sessions` or existing auth table | hashed opaque token, actor_id, created/expiry/revoked instants, CSRF secret hash; never store plaintext bearer token |

Identity/source UUIDs inside frozen snapshots do not require inventing mutable upstream tables. Enforce their scoped referential integrity during package/scenario validation; FK actual upstream entities only after ownership is established. JSONB shape is validated by versioned Pydantic before insertion and before replay. Immutable DB rows need an update-denial trigger or repository enforcement plus DB role permissions; use a trigger for immutable content columns and test it. Status/attempt rows remain mutable by allowed transitions.

Create a partial unique index on active dedup key for QUEUED/RUNNING jobs. Terminal submissions may be recomputed deliberately with a new key; retries have explicit linked attempt/job history. Application idempotency decisions, not read-then-insert races, are protected by unique constraints and transactions.

Transactions:

1. Package/scenario create: authorize → lock/revalidate current source revision when LIVE/CURRENT → validate/hash → insert input/scenario + request key + audit → commit. In SIMULATED scope use its immutable dataset epoch/revision.
2. Admission: authorize and resolve request key → lock singleton compute-control row → check fresh supervisor and bounded waiting count → insert/reuse durable job/key → commit → return 202. Read-only source validation must not start expensive work.
3. Publication: lock job/attempt/control → require owner+generation+epoch and permitted state/time → insert plan/transfers/check report atomically → update method progress/comparison/job as applicable → audit → commit. Reject late attempts; never expose uncommitted `planning_ready`.
4. Review: authorize → verify exact result hash → append review/audit → commit; assert no stock write or reservation.

Manual retry creates a new job with `retry_of_job_id` and linked history, preserving previous terminal attempts/results; fresh admission limits apply. The attempts table still supports recovery bookkeeping and future explicitly requested attempts, but there is no automatic attempt loop on worker loss.

## 6. Durable supervision and real containment

### 6.1 States and outcomes

```text
QUEUED -> RUNNING -> SUCCEEDED | PARTIAL | FAILED | TIMED_OUT | CANCELLED | INTERRUPTED
QUEUED -> EXPIRED | CANCELLED
```

`PARTIAL` is valid only for a pair with exactly one committed verified result. Keep native status on individual method outcomes separate from job state. A returned INFEASIBLE result has no vector and is a failed method outcome for comparison purposes; distinguish `MODEL_INFEASIBLE` from runtime failure in code. If both methods produce only native infeasibility diagnostics, the comparison ends FAILED with both diagnostic outcomes retained. Status schema is provisional OR-DEC-016 and must be reconciled with any landed shared executor.

For a pair, SUCCEEDED means both methods independently verified/published; PARTIAL means one; FAILED means neither and neither cancellation/timeout/loss requires a different terminal label. If cancelled/timed out/interrupted after a successful first method, the job retains that terminal execution state plus `result_completeness=ONE_OF_TWO`; preserve the valid first result and error details. No final-state precedence hides the causal event.

### 6.2 Scheduler algorithm

- Supervisor owns a random owner UUID and monotonically increasing generation. Persist heartbeat every 5 seconds using DB time (`clock_timestamp()`), not a long transaction's frozen `now()`.
- Availability is healthy only when heartbeat age <15 seconds and ownership is valid; age ≥15 seconds is unavailable. Lease expiry is 20 seconds, renewed every heartbeat. Admission distinguishes healthy-busy from unavailable.
- Hold a short transaction row lock on `compute_control` for queue admission and claiming. At most one RUNNING top-level job and two QUEUED jobs exist globally. Reused active submissions do not consume a new queue slot. Queue-full returns 429 `QUEUE_FULL`; unavailable worker returns 503 `COMPUTE_UNAVAILABLE` before accepting new work. These exact codes are provisional OR-DEC-011.
- Queue deadline is admitted_at+900 seconds; queued records at/after it become EXPIRED and cannot start. Claim oldest eligible `(admitted_at,id)` under the same control lock; start deadline clock at the actual transition to RUNNING.
- A supervisor restart fences old generation; expired running attempts become INTERRUPTED and are not put back on queue. Retain unexpired queued records. Cancel/terminate only a process that can be proven to belong to that supervisor/attempt, not an arbitrary reused PID.
- Spawn one method child with multiprocessing `spawn`, fixed input on a private local file/pipe, and no shared mutable model. Use monotonic deadlines for running work; DB UTC instants for durable state/audit. Rebuild deadlines conservatively after recovery; never extend an interrupted attempt.
- Native search ≤15 seconds; whole method ≤25; sequential pair ≤60; allow 10 seconds total pair orchestration overhead only within the same deadline. Stop native search early enough to extract/check/commit inside method deadline. A 15-second solver parameter alone is insufficient.
- Parent supervises heartbeat independently while child runs. At wall deadline/cancel, terminate then kill the owned process group if needed, reap, clean temporary files and verify slot release. Termination grace is included in the existing deadline; initiate it early enough. DB connectivity/lease loss fences publication and terminates active computation.
- Do not discard a committed first-method result if second fails. A killed/unvalidated second candidate is not publishable. After a child returns, parent rechecks ownership/deadline before any insert.

Accepted effective worker ceilings are configurable 6 CPU equivalents and 8 GiB. v1 solver uses one native worker. Apply process/container resource limits, account for descendants, and verify actual enforcement. On an unsupported host report `RUNTIME_LIMITS_UNVERIFIED` and do not claim runtime acceptance; do not weaken accepted ceilings. Cheap reads, polling, stock operations and probes stay outside the expensive slot.

Forecasting should register with the same executor when its orchestration lands, retaining its own accepted 300/270-second rules. Do not create competing independent “one worker” services. Heavy provider setup remains paused; unregistered provider capability returns explicit unavailable status, not a fake job success.

## 7. API catalog and security

All routes `/api/v1`, JSON error envelope `{error:{code,message,details},request_id}`. Request body maximum for complete packages is provisionally 4 MiB, with cardinality checks below that byte limit; never log payloads. Lists use `limit` 1–100 (default 25) and opaque `(created_at,id)` cursor; org scoping always applies.

| NEW route | Request/response |
|---|---|
| `POST /or/input-packages` | Presenter only; complete `source_kind=SIMULATED` package; persist immutable data, 201; LIVE package construction uses trusted source adapter rather than arbitrary asserted live stock |
| `POST /or/input-packages/from-sources` | Presenter; exact upstream refs/revision; build trusted LIVE package, 201 or explicit unavailable/conflict |
| `GET /or/input-packages/{id}` | Saved synthetic input metadata/approved viewer-safe summary; full operational payload presenter-only |
| `POST /or/policies` | Presenter; validated policy with explicit provisional values; immutable version, 201 |
| `GET /or/policies/{id}` | Safe formulas/parameters/version/decision IDs |
| `POST /scenarios` | Exact scenario request defined above; freeze complete data, 201; no solve |
| `GET /scenarios/{id}` | Saved mode, scope, provenance, window, policy, staleness and projection summaries |
| `POST /scenarios/{id}/plans` | `method`, expected scenario hash, intent; idempotency header; durable 202 `{job_id,state,status_url}` |
| `POST /scenarios/{id}/compare-methods` | Expected scenario hash and intent; exact classical/research pair; durable 202 |
| `GET /jobs/{id}` | Persisted state, each method outcome, timings, result completeness/refs and safe error; no compute |
| `POST /jobs/{id}/cancel` | Presenter; request cancellation idempotently, 202 for pending/running; terminal already-ended result returned without restarting |
| `POST /jobs/{id}/retry` | Presenter; terminal failed/lost/expired/cancelled job, new idempotency key; new linked job, 202; stale CURRENT inputs require new scenario or explicit historical replay |
| `GET /plans/{id}` | Committed verified result or safe failure diagnostic; explicit method/mode/identity |
| `GET /comparisons/{id}` | Saved outcomes, common metric deltas, partial/historical/stale labels |
| `POST /plans/{id}/review` | Presenter; REVIEWED/REJECTED, expected result hash and optional note; 201 append-only event |
| `GET /allocation-methodology` | Versioned formulas, policy/decision registry, units, loading limitation, DOI/adaptation and gates/capabilities |
| `GET /readiness`, `GET /capabilities` | Cheap DB/schema/heartbeat/capability state; no solve/inference; original `/health` unchanged |

Use 400 malformed JSON, 401 missing/expired presenter session, 403 unauthorized org/origin/CSRF, 404 unknown scoped resource, 409 version/idempotency conflict, 413 oversized payload, 422 invalid business/schema/group/numeric input, 429 queue full/rate limit, 503 unavailable compute/source integration and 500 safe internal failure. Separate parser and business error details. Correctness/validation failures are not returned as successful zero plans.

OR-DEC-014 provisional auth: 256-bit opaque session token in HttpOnly cookie, Secure outside explicit localhost development, SameSite=Strict, 8-hour lifetime, revocable server-side hashed token; presenter credentials from environment and approved hash verification, never seed plaintext credentials in source. Login is rate-limited; clear cookie and revoke session at logout. Session startup is not tied to a model worker.

Next.js route handlers forward same-origin intent, cookies/CSRF proof and request IDs; no authoritative calculations or database credentials in client bundles. FastAPI validates session/actor/org and mutation origin/CSRF itself, including direct backend calls. Use an explicit origin allowlist; require configured trusted proxy identity for forwarded origin metadata instead of trusting arbitrary headers. Public visitors may read saved synthetic summaries/results only; fail closed for LIVE payloads. Reuse equivalent landed auth/session/proxy contracts when present; record any reconciliation under OR-DEC-014.

`/demo/reset` integration must use an explicit dedicated demo organization/dataset, lock the same control row, fence org_epoch, cancel its queued jobs and terminate its owned running child before deleting/resetting mutable demo scope. Preserve append-only audit/reset history according to explicit policy; do not touch other organizations. It is not a production data-reset endpoint. No reset may race late result publication.

## 8. Exact scripts to create and commands

The repository already has `npm run check`, `test:api`, `test:config`, `build`, scaffold plus design-lab browser tests, and `apps/api/scripts/evaluate_forecasting.py`. They do not prove OR behavior until actual OR tests are added. PP-30 reports 488 API tests, 17 configuration tests and 6 browser tests at its recorded environment; this document refresh did not rerun them. The committed `evaluation.synthetic-v1.json` remains historical original-source evidence. Reproduce current evaluation with `uv run --frozen --directory apps/api python -m scripts.evaluate_forecasting`. The following are **NEW scripts to implement**, with argparse, deterministic exit codes and no model downloads.

| New script | Required behavior |
|---|---|
| `apps/api/scripts/or_validate_input.py --input PATH --report PATH` | Strict parse/hash/schema/provenance/bounds; 0 valid, 2 invalid input, 1 unexpected failure |
| `apps/api/scripts/or_enumerate.py --fixture NAME --output PATH` | Independent enumeration for tiny math/full scarce fixture; no OR-Tools/model-builder imports; emit all optimum counts, vectors, scores and fingerprints |
| `apps/api/scripts/or_verify.py --snapshot PATH --candidate PATH --report PATH` | Independent full replay/check; 0 verified, 3 candidate invalid, 2 bad source input |
| `apps/api/scripts/or_solve.py --snapshot PATH --method NAME --output PATH` | Offline actual bounded child solve via same service/supervisor containment; 0 verified vector, 4 no verified vector, 2 invalid input. No DB mutation; clearly OFFLINE |
| `apps/api/scripts/or_compare.py --snapshot PATH --output PATH` | Actual sequential bounded pair, verified outcomes; 0 both verified, 5 partial, 4 neither; exact shared hashes |
| `apps/api/scripts/or_seed.py --organization-id UUID --dataset-id UUID --fixture NAME` | Publish SIMULATED package/policy/scenarios through trusted repository path; requires explicit demo scope, no physical ledger effects, idempotent content identity |
| `apps/api/scripts/or_supervisor.py` | Long-running shared compute-supervisor entry; env-based DB/limits, clean shutdown and redacted logs |
| `apps/api/scripts/or_benchmark.py --scenario-id UUID --runs 5 --output PATH` | Real persisted submission/poll/read workflow; measured durations/memory/effective limits; distinguishes saved read and solve |
| `apps/api/scripts/export_openapi.py --output PATH` | Export app schema without model loading/network/solve |
| `scripts/contracts/generate.mjs` / `check.mjs` | Pinned OpenAPI-to-TS generation and no-drift check; genuine generated schema comparisons |
| `scripts/or/check-decision-markers.py` | Validate OR-DEC registry, marker IDs, policy/decision references and required coverage manifest; no no-op existence-only gate |

Example commands from repository root after implementation:

```bash
uv run --frozen --directory apps/api python -m scripts.or_enumerate --fixture six-beneficiary-v1 --output ../../artifacts/or/oracle.json
uv run --frozen --directory apps/api pytest tests/optimization -q
uv run --frozen --directory apps/api pytest tests/integration/test_or_persistence.py tests/integration/test_or_jobs.py -q
uv run --frozen --directory apps/api alembic upgrade head
uv run --frozen --directory apps/api python -m scripts.or_compare --snapshot ../../data/demo/or-v1/snapshot.json --output ../../artifacts/or/comparison.json
npm run contracts:generate
npm run contracts:check
npm run check
npm run test:config
npm run build
npm run test:e2e
```

Add the NEW root `contracts:*` scripts with pinned dependency/lock changes; do not claim they currently exist. Verify command working directories with the actual uv version and script paths. Integration tests require a dedicated disposable PostgreSQL database, never a shared Neon production/demo database. Test upgrade/downgrade/upgrade on isolated data. Artifacts may go under ignored `artifacts/or/`; select small public fixtures/evidence deliberately before committing.

## 9. Tests and fixtures

Fixtures: (1) six-beneficiary unique-optimum case from math §13; (2) AP ablation; (3) RP ablation; (4) surplus pantry that may send in HUB_AND_PANTRY and cannot in HUB_ONLY; (5) same pantry with future demand/reserve preventing donation; (6) early-expiry short-route versus late long-route exception; (7) late arrival unable to cover yesterday; (8) shared product capacity competition; (9) zero inventory/no routes; (10) stale/cancelled/reset/publication-race inputs. Confirm fixture semantics independently before solving.

Test layers:

- Pure unit/property-style deterministic randomized tests for precision, daily rounding, canonicalization, source dedup, packing and projection; independent expectations for lost sales and stock conservation.
- Merged-core compatibility: retain constant-mean, sparse-fallback, genuine-fraction ceiling and held-out-basis regressions, strict training proxy rules and experimental null-expiry behavior. Add source=0.2 with OR multiplier=2: target must be ceil(0.4)=1, not 2 from scaling an already-rounded target.
- Enumerative oracle tests for every tiny feasible y vector: compare CP feasibility to plain simulation checks, and optimum/decomposition to independent Fraction calculations. Include deliberately invalid candidates and twins with same aggregate shipment but different lot feasibility.
- Numerical boundary tests for AP/RP equality, q floor, zero demand/all-zero groups, unsupported singleton, exact/quantized disagreement and activity near 2^60. Test both binary indicator branches, not only objective-preferred flags.
- Model tests for deterministic service (cannot deliberately leave demand unmet with eligible free stock), FEFO exceptions/order limitation, full sublot consumption, donor no-inbound check, no same-batch relay and hard capacity enforcement.
- Status tests using extraction sentinels for UNKNOWN/MODEL_INVALID/INFEASIBLE, FEASIBLE verification, absent/invalid candidate, per-method failures and no research relabeling.
- Real PostgreSQL tests for immutable records, scoped FKs/validation, idempotency concurrency, active dedup, global queue count races, rollback, request-key mismatch, stale ownership/generation/epoch and manual retries.
- Process integration tests with deliberately hung/forking children: real terminate/kill/reap, parent heartbeat during compute, method/pair time ceilings, unavailable/busy distinction, queue expiry and supervisor loss. A mocked future timeout is insufficient.
- HTTP/auth/proxy tests for exact mode requirements, 202 lifecycle, saved GET no work, 401/403/409/413/422/429/503, CSRF/origin forwarding and public synthetic versus private LIVE access.
- Browser journey backed by real app/DB: choose mode → committed source/forecast selection → scenario → comparison → inspect both methods/metrics → change disruption/new scenario → review → isolated reset. Synthetic standalone OR journey and actual merged forecast journey are distinct acceptance claims.

## 10. Decision marking and evidence

Place a concise `OR-DEC-nnn [PROVISIONAL]` comment adjacent to each affected algorithm/config/schema validation and its tests. For JSON fixtures use a `decision_ids` field, not invalid JSON comments. SQL migration comments and methodology output carry the IDs. Maintain registry entries with rationale, alternative, affected symbols/files/tests, schema/policy version, owner/review state, adopted date and revisit trigger. Do not mark every function indiscriminately; attach IDs where the choice changes behavior.

For each acceptance result record V5 acceptance ID, code SHA, source/scenario/policy/settings hashes, decision IDs, dataset scope, environment/resources, exact command, timestamp, outcome PASS/FAIL/UNVERIFIED and artifact path. Distinguish independent enumeration run now from future solver tests. Mathematical proofs and fixture arithmetic are not real model/runtime/database evidence.

Structured logs include request/job/attempt/scenario/plan/method IDs, queue and execution duration, limits, native status, safe error code and expected/actual revision. Never log raw snapshots, tokens, credentials, connection strings or uploaded CSV contents. Durable audit complements but does not replace upstream ledger authority.

## 11. Limits and delivery interpretation

This first draft deliberately limits dispatch schedules, loading order, group structure, domain sizes and unknown-expiry eligibility. It conservatively blocks already-short donors and models protected commitments as quarantined quantities. Those are explicit provisional choices with executable behavior and later review points.

The OR service can deliver its complete durable simulated workflow independently of real Chronos, supplier work or upstream import implementation. The baseline forecasting core is merged; the remaining live boundary is committed persistence/read adapters, complete operational inputs and connected browser journey. An unavailable adapter is not a passing live test.

Preserve `/design-lab`, visible simulated labels, 2D default, accessible selector, reduced motion and 3D fallback tests. ADR 0004 permits Three.js only in that prototype; it does not approve production OR-dashboard 3D or prove solver/API integration. The separate `codex/vercel-prototype-preview` branch has a narrow static-frontend hosting exception and redirect, not backend/model-hosting resumption. Do not copy its root redirect or deploy during OR implementation. Build connected OR UI/proxy against generated contracts and prove it separately. Core OR algorithms are unchanged in this refresh.
