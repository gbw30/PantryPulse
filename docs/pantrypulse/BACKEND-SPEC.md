# PantryPulse Backend Specification — Working Draft

**Date:** October 24, 2026 (America/New_York)

**Status:** Documentation of accepted design, with unresolved requirements. This is not a complete implementation specification or evidence of working domain functionality. Supplier planning and hosting/model setup remain paused.

**Implementation update (2026-10-24):** The [offline forecasting core](forecasting/IMPLEMENTATION.md)
now implements experimental internal contracts, revision-aware preparation, baselines,
evaluation and a pure planning handoff/projection. The inspection paragraph below
records the earlier checkout. Public contracts, migrations, durable jobs, complete
scenario persistence, Chronos qualification and solvers remain gated. No OPEN decision
is resolved by these internal experiment policies.

**Decision record:** [Backend design checkpoint](BACKEND-DESIGN-CHECKPOINT.md), BD-01 through BD-40 and OPEN-01 through OPEN-36. This document explains current requirements; the checkpoint preserves selections, alternatives, progress, and resume instructions.

## 1. Authority and implementation status

[V4](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) remains the source specification. Its authoritative extensions supersede conflicting inherited examples. Explicit interview selections resolve the differences recorded here and in the checkpoint; they do not silently edit the Google Doc.

Accepted decisions are binding design directions. Carried-forward V4 requirements remain required unless explicitly revised. Logical data descriptions and candidate routes below do not freeze unfinished SQL, Pydantic, JSONB, or wire schemas. An OPEN reference identifies work still required; recommendations in older documents are not selected defaults.

Inspection basis: publication checkout at commit `0fe90c2f2ed8442e7acaa1c71ab1016bab7c9ce7`. The [API entrypoint](../../apps/api/app/main.py) has only `GET /api/v1/health`, returning process liveness. Domain routers, models, schemas, and optimization services are scaffolds. The [contracts package](../../packages/contracts/README.md) has no generated domain contracts. Database transactions, domain endpoints, forecasting, allocation, worker readiness, and the complete demo are unverified. No application functionality is added by publishing these documents.

The humanitarian demo requires at least six fictional beneficiaries plus hub(s), two resource categories, daily seven-day forecasts, dated inventory lots, and an allocation window within the forecast horizon. Synthetic operations and vulnerability indicators must be labeled. Older three-site fixtures are supplemental, not proof that the expanded demonstration works.

## 2. Backend responsibilities and boundaries

The backend turns historical observations and current operational records into forecasts, dated shortage projections, and simulated shipping recommendations:

1. Validate historical demand, received donations, current lots, confirmed arrivals, and versioned planning configuration.
2. Create or reuse an identified forecast result with actual provider, cutoff, provenance, and warnings.
3. Freeze the selected inputs and assumptions when creating a scenario.
4. Project eligible stock and need over dates, including local demand and donor protection.
5. Run `CLASSICAL_GP` and/or `EGP_PI_INSPIRED` against the same operational snapshot and independently check the result.
6. Persist plans, per-beneficiary metrics, explanations, and conditional supplier proposals within the agreed supplier scope.
7. Allow a presenter to mark a simulated plan reviewed. Operational updates require their own authorized transactions.

| Boundary | Responsibility | Basis |
|---|---|---|
| Next.js frontend and thin same-origin proxy | Present saved data and job state; forward authenticated requests without duplicating forecasting, allocation, or inventory logic | BD-13, BD-14 |
| Modular FastAPI backend | Domain validation, authorization, forecasting orchestration, projections, allocation, policy, and persistence | V4 §§6, 8, 12 |
| PostgreSQL | Relational operational records/results, immutable JSONB input packages, durable audit and job records | BD-10, BD-11, BD-30 |
| Forecast adapters | Translate application contracts into provider-specific formats and retain actual method metadata | V4 §9; OPEN-12–18 |
| Compute supervisor and controlled execution | Availability heartbeat, serialized expensive work, enforceable deadlines, and failure recording | BD-31, BD-34–38 |
| Pydantic/OpenAPI and generated TypeScript | Define and distribute the eventual public contract after validation | BD-14; OPEN-29, OPEN-36 |

One modular backend is intended. These responsibilities do not select an additional queue product, tracing service, hosting vendor, or model endpoint.

## 3. Data model and mutation rules

### 3.1 Logical records

The following describes required information, not finalized table names, PostgreSQL column types, indexes, or enums. Complete those under OPEN-04–11.

| Logical record | Information and meaning | Backend use |
|---|---|---|
| Organization and site | Network ownership, site identity, role, and applicable operational time zone | Scope data and allowed routes; distinguish hubs and beneficiaries |
| Product/resource | Standardized product identity and explicit base unit | Keep quantities compatible; distinguish resource types from physical batches |
| Inventory lot | Site, product, on-hand quantity, reservations/commitments where applicable, receipt/expiry information, eligibility, and provenance | Determine available and transferable stock by date |
| Demand observation revision | Site/product/local day, requested units when observed, fulfilled units, unmet units when observed, source/version, and provenance | Build the requested-demand series; preserve what was actually recorded |
| Donation receipt and lines | Separate donor and receiving-site identities, received date, products and received quantities, source, and posting linkage | Preserve individual receipts and aggregate received donations by receiving site/product/local day |
| Inventory ledger event | Identified stock change, actor, time, reason, version context, and linked source event | Audit physical stock changes and prevent duplicate posting |
| Expected supply | Receiving site/product, quantity, arrival, source kind, confirmation/receipt state, and inventory linkage | Separate confirmed arrivals from uncertain expectations and received goods |
| Forecast run and per-series result | Requested strategy, actual model/version, inputs/cutoff/horizon, outcome, timestamps, cache/fallback metadata, warnings, and measured evaluation where available | Explain and reproduce predictions |
| Forecast point | Series identity, target date, central estimate and available quantiles with interval method | Feed projections and charts without inventing uncertainty |
| Scenario and frozen snapshot | Selected scope, exact source versions, input content, assumptions, schema version, hash, and provenance | Reproduce and compare planning against immutable data |
| Policy and vulnerability version | Prepared scores, source/raw information, coefficients, methodology, and versions | Apply disclosed priorities and evaluate research metrics |
| Plan, transfers, and metrics | Method, snapshot reference, actual solver status/settings, lot-level assignments, projections, and objective/diagnostic results | Save reviewable recommendations and comparable outcomes |
| Supplier offers and draft proposals | Manually entered/seeded offers, conditional basket, assumptions, alternatives, and uncovered need | Produce simulated replenishment recommendations; exact contracts remain paused |
| Job, attempt, review, and audit records | Execution history, relationships to saved inputs/results, actor/time/version, and outcome | Support polling, manual retry, review, and traceability |

Products have explicit base units, while lots identify batches. No implicit unit conversion, product substitution, or combined bottle-and-meal inventory total is permitted (BD-02, BD-19). Shared capacity needs explicit handling coefficients; their values remain OPEN-22.

### 3.2 History, receipts, and corrections

Daily demand totals and individual donation receipts are retained (BD-03). Requested demand differs from distributed/fulfilled volume: stockouts can suppress fulfillment. When requested demand is unknown, a fulfilled-demand proxy needs explicit opt-in, target-basis metadata, and visible warnings through forecasts and plans (BD-06). Missing values remain distinct from zero.

The donation forecasting target is actual received quantity aggregated by receiving site, product, and local day. Offered, pledged, accepted, or forecast quantities do not by themselves establish receipt. Donor identity must remain distinct from the receiving site.

Historical imports do not alter current physical stock. Posting a new donation receipt is an explicit, exactly-once operation linking the receipt to lot and ledger changes atomically (BD-04). Corrected history appends revisions, preserves originals, and leaves saved snapshots pointing to their exact source revisions (BD-05). Correcting already-posted stock needs a linked audited adjustment.

Partial imports accept valid demand rows individually and accept or reject each donation receipt together with all its lines (BD-26). Report precise errors and accepted/rejected counts; do not silently overwrite duplicates. Revision selection, duplicate identity, receipt cancellation/reversal, locking, idempotency-key reuse, and consumed-stock corrections remain OPEN-07–09.

At receipt posting, the operator explicitly declares lot eligibility and records actor, time, and reason. Unknown status remains held/unavailable. Later changes are audited and affect relevant plan validity (BD-25). Dates and status labels do not establish food safety.

### 3.3 Supply and stock boundaries

Baseline planning uses eligible current stock and qualifying confirmed arrivals (BD-07). Received goods must not also remain counted as a future arrival. Forecast donations and unapproved supplier proposals remain separate from on-hand stock and confirmed supply.

Stock-changing transactions must preserve nonnegative balances, unit compatibility, expected-version checks, and durable audit linkage. Inventory updates and ledger/audit evidence must be consistent. The exact ledger authority, lock/version scope, and rollback/idempotency behavior remain OPEN-09; this draft does not claim those mechanics are implemented.

Expiry is an eligibility rule, not deletion of historical lots. Reservations and other commitments must be accounted for once. Site-local cutoff, missing-expiration policy, dated event ordering, and reconciliation rules remain OPEN-06, OPEN-10, and OPEN-21.

## 4. Forecasting and application contracts

### 4.1 Inputs and outputs

ForecastInput, ForecastOutput, DailyObservation, and ForecastPoint describe application service contracts. They are not the native Chronos interface. Provider-specific DataFrames and checkpoint handling stay inside the adapter.

| Contract | Required logical information | Still to finalize |
|---|---|---|
| DailyObservation | Local day, observed target/available component quantities, missingness, provenance, and exact source version | Field names, nullability, consistency validation, and revision representation |
| ForecastInput | Site/product/target identity; ordered observations; cutoff; horizon; strategy; allow_fallback; provenance; preprocessing configuration; any permitted future covariates | Exact types, provider options, minimum history, grouping, and bounds |
| ForecastOutput | Series identity; actual model/version; generation time/cutoff; outcome; fallback flag/reason; warnings; dated points; reuse/provenance information | Per-series and aggregate outcome enums, required fields, and partial-result policy |
| ForecastPoint | Date; central prediction; available p10/p50/p90 information; interval method | Central-estimate versus median semantics and validation/postprocessing policy |

Daily series are keyed by site, product, and target type: DEMAND or DONATION. Forecast seven future local dates for each usable required series. Missing required series cannot silently become zero or disappear from a supposedly complete scope (OPEN-12–15).

Preserve historical gaps and flags; do not create replacement historical observations through backend imputation (BD-27). Use supported provider handling or a labeled fallback, otherwise report insufficient inputs. The fulfilled-demand proxy is a separate explicit choice, not a missing-date repair.

Future covariates must be known for the relevant horizon or explicitly forecast with provenance; held-out future observations cannot leak into fitting, preprocessing, or selection. Exact allowed covariates and inference settings remain OPEN-15.

Available quantiles must be identified honestly. Point-only methods retain absent interval bounds; they do not manufacture p10/p90 values. Validate dates and numerical outputs, including nonfinite/negative values and crossed quantiles, under a finalized OPEN-14 policy. This draft does not select a silent repair rule.

### 4.2 Provider qualification and fallback

Seasonal-naive forecasting and the permitted fallback path are mandatory for the core workflow (BD-33). Chronos-2 remains the preferred primary integration when installation, inference, and latency are feasible. Separately qualify the actual pinned model; mocks, fixtures, or health responses do not establish live inference.

This follows [V4 §§2.4, 9, 12.3 and 16.6](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) and the [Forecasting and ML guide](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.4q4ahys8aav9). A setup pause establishes unverified status, not demonstrated infeasibility. Do not report Chronos as working until supported by actual inference evidence.

Record the requested strategy separately from the actual provider/checkpoint and fallback reason. If fallback is disallowed or unusable, retain an explicit failed outcome and existing successful data. Choosing a fallback within an attempt is different from automatically retrying an interrupted job.

The seasonal reference, minimum history, simpler sparse-data method, and exact provider-selection rules remain OPEN-13. Chronological evaluation against the baseline remains required; a separate qualification track is not permission to invent accuracy results or omit evaluation.

### 4.3 Reuse and conservative planning

Reuse exactly matching immutable forecast results by default, with explicit presenter-requested forced recomputation (BD-29). Preserve original timestamps and actual provider/fallback provenance. Identity must cover relevant observations/revisions, scope, cutoff/horizon, preprocessing, covariates, strategy, model/checkpoint, and inference/grouping settings. Exact cache keys, fallback reuse, and concurrent-submission deduplication remain OPEN-17.

Conservative planning may use available upper quantiles. Where they are absent, a presenter must explicitly select a buffer, recorded in the scenario (BD-28). Preserve null quantiles and label mixed quantile/buffer series. Buffer defaults/ranges and application granularity remain OPEN-16. A buffer or sum of daily upper quantiles is not a calibrated joint stockout probability.

## 5. Frozen scenarios and dated projections

Scenarios are fully frozen at creation (BD-09). Pin the selected forecast, inventory, supplies, routes/capacities, attributes, policies, scope, and assumptions. Planning with newer operational inputs requires a new scenario; rerunning an older scenario must not silently refresh it.

Store a validated JSONB input package with a schema version, content hash, exact source references, and provenance (BD-10). Store model identity/version references rather than model weights. Exact JSON layout, canonical serialization, hash algorithm, validation, and migrations remain OPEN-19.

Explicitly reduced scopes are allowed (BD-08). Record excluded sites/products and use the frozen included scope for target and group denominators. Missing inputs cannot silently remove need. A partial scenario does not replace the required full research demo.

Derive allocation targets from forecasts plus frozen assumptions. Round each daily scenario demand upward before aggregation and retain original forecast values (BD-17). Future authoritative-request overrides are not selected. This resolves the recorded V4 difference between forecast-derived need and older recorded-request wording.

Daily projections must distinguish eligible current stock, confirmed future arrivals, scenario-assumed donations, selected transfers, demand served, unmet/lost demand, and expiry. A delivery cannot satisfy already missed demand. Do not sum overlapping cumulative deficits as though they were independent daily shortages.

Operational changes may make saved recommendations stale for current use without rewriting their historical inputs/results. Exact invalidation triggers, visibility, replay behavior, donor reserves, event ordering, and FEFO exclusions remain OPEN-20–22.

## 6. Allocation and output behavior

### 6.1 Transfer network and constraints

OPEN-01 is resolved by BD-32: hubs and eligible beneficiaries may supply other beneficiaries along allowed routes. Protect a source beneficiary's own demand and reserves before calling stock transferable. No self-transfer or forwarding of newly incoming stock within the same batch is allowed. This is not a commitment to make every possible route available.

Both methods receive the same frozen network and operational constraints: compatible product units, eligible lots, stock conservation, commitments, donor protection, arrival/use/expiry feasibility, receiving/handling capacity, and hard FEFO enforcement. Display sorting alone does not enforce FEFO.

Optimize products jointly under shared capacities while preserving product-specific stock, demand, units, and metrics (BD-19). Shipment quantity is not automatically fulfilled demand. Independently recompute feasible service and dated inventory effects before publishing recommendations.

### 6.2 Objectives and mathematical boundary

Define one fairness goal per beneficiary/product over the planning window while retaining daily projections (BD-15). Relative-deprivation groups contain included positive-demand beneficiaries of the same product, with at least two meaningful members; freeze membership and compute the comparison mean from the allocation being evaluated (BD-16).

Use prepared normalized institutional scores in [0,1], retaining raw/source information, preparation notes, provenance, and versions (BD-18). The backend validates the prepared scores and applies a declared proxy-weight formula. It does not implement a new raw-data normalization service or the paper's endogenous weighting model.

The accepted aggregation is `W = sum(z)` across included goals; products with more goals contribute more terms (BD-20). A maximum-deviation component and active AP/RP goal terms distinguish the research-inspired objective from the conventional comparator. The complete formulas, coefficients, allowed ranges, and excess-share aggregation remain OPEN-23 and must not be copied from illustrative defaults as accepted policy.

BD-21 selects fixed-point scale 10,000 with downward rounding of weighted deficits for the computational objective and AP/RP comparisons. Retain original counts and exact ratio information. This affects computation, not merely display. Prove numerical bounds and independently test near-threshold/equality behavior before treating the formulation as verified (OPEN-24).

Use the name `EGP_PI_INSPIRED` for the bounded adaptation. The [study](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.70252), DOI 10.1111/itor.70252, was first published September 11, 2026; [institutional publication evidence](https://researchportal.port.ac.uk/en/publications/an-extended-goal-programming-framework-incorporating-poverty-meas/) supports that provenance. Chronos and OR-Tools are supporting tools.

Pantry-to-pantry transfers, forecast-derived targets, and this fixed-weight implementation are project design choices; do not describe them as a validated reproduction of the paper's application. Full equation mapping, independent oracles, and the research gate remain incomplete. No observed poverty reduction, real-world fairness gain, or calibrated stockout probability is established.

### 6.3 Saved results and review

| Output | Required meaning |
|---|---|
| Transfer recommendation | Source/destination, product and exact lot, quantity with unit, expected arrival, and supported cost information |
| Site/product projection | Before/after service, remaining unmet demand, dated shortages, and relevant supply/expiry assumptions |
| Research evaluation | Declared groups, vulnerability provenance, deprivation indicators, and objective decomposition under the fixed evaluation policy |
| Execution diagnostics | Snapshot/method/version, limits, native solver status, measured duration, warnings, and failure details appropriate to the viewer |
| Review record | Identified plan/version, actor, time, and review action, without a stock effect |

These are logical output requirements; canonical field names and date/cost representations remain OPEN-29. Numeric per-transfer `expected_benefit` is unresolved under OPEN-02. Preserve the alternatives of aggregate plan/site impact with rationale versus a remove-one-transfer fixed-plan counterfactual; neither is selected.

Report native solver status honestly. `FEASIBLE` is not proof of optimality. Do not extract a shipment vector from `UNKNOWN` or `MODEL_INVALID`, invent results after a timeout, or present shortage alone as contradictory hard-constraint infeasibility. Publish only independently validated successful vectors.

Method failures remain explicit and independent in a paired comparison. Never substitute a classical result under the research method's label. Exact partial-comparison lifecycle/publication behavior remains OPEN-30.

Marking a plan reviewed records actor/time/version and does not reserve stock, move goods, spend money, or dispatch a shipment (BD-01). Actual fulfillment and operational reservation workflows are later extensions.

## 7. Supplier replenishment — planning paused

Draft supplier proposals are included (BD-22); the user's later option B selection superseded the temporary internal-allocation-only choice. Use seeded or manually entered offers. No external supplier order, payment, or dispatch is authorized.

Size a proposal for a defined period after its estimated arrival, using projected stock, confirmed arrivals, and the selected transfer plan (BD-23). Stay within forecast dates. Preserve earlier unmet demand; a later delivery cannot repair it.

Produce a coordinated basket respecting a shared frozen simulated budget and per-order limits, with alternatives and uncovered need (BD-24). The classical and research baskets are alternative hypothetical outcomes against the same budget, not simultaneous purchases. Unapproved proposed goods do not enter on-hand stock or the confirmed-resource primary comparison.

OPEN-03 remains deferred: urgency-first versus vulnerability-first beneficiary budget priority. Neither is a hidden default or a promise to implement a toggle. A dependent basket implementation needs a later explicit selection.

OPEN-26–28 are paused at the user's request. Valid offer fields, destination/arrival rules, finite availability, minimum quantities, expiry assumptions, price validity, ranking, coverage/budget defaults, currency representation, and draft lifecycle details remain unresolved.

The last unanswered question was whether a basket may combine supplier offers for one beneficiary/product:

| Unselected alternative | Meaning | Tradeoff |
|---|---|---|
| A. One offer per need | At most one selected offer per beneficiary/product, with other offers retained as alternatives | Simpler but may leave need uncovered despite combined supplier availability |
| B. Combine offers | Multiple offers may contribute to the same need, each subject to its terms and the shared budget | May cover more need but adds quantity, delivery, minimum-order, and fee interactions |

The assistant recommended A; the user selected neither option and paused this topic. Resume this question only after the user resumes supplier planning. Do not select coverage days, currencies, minimum quantities, statuses, or priorities while saving the documentation.

## 8. API, access, and job behavior

### 8.1 Contract boundary

Use versioned FastAPI routes under `/api/v1`, with Pydantic/OpenAPI as the public contract authority and generated TypeScript for the frontend. The thin same-origin Next.js proxy forwards requests; backend authorization and validation remain mandatory (BD-14).

| Interface family | Intended behavior | Contract status |
|---|---|---|
| `GET /api/v1/health` | Cheap process liveness | Implemented scaffold only; not DB/model/solver readiness |
| Sites and site inventory reads | Return scoped sites and dated lot availability | Proposed; exact filters, pagination, and schemas OPEN-29 |
| Forecast-run submission and reads | Accept expensive work with `202`; expose saved outcome and points | BD-11; exact wire/lifecycle details OPEN-12, OPEN-29–30 |
| Scenario creation and retrieval | Persist fully frozen inputs and expose their linked results | BD-09; exact schema OPEN-19, OPEN-29 |
| Plan and paired-method submissions | Queue computation against the specified frozen scenario | BD-11; no synchronous success claim from job acceptance |
| Saved plans, shortages, policy, and methodology reads | Expose identified results, assumptions, versions, and research limits | Proposed; complete route catalog OPEN-29 |
| Receipt posting, corrections, review, and reset | Presenter-controlled changes with required integrity/audit behavior | Exact transaction and access details remain OPEN-08–09, OPEN-31–32 |

Previously illustrated route names, including a separate plan-transfers endpoint, are candidates until OPEN-29 is completed. No route listed as proposed is implemented by this document.

Read requests do not initiate inference or silently create plans. `202 Accepted` means durable acceptance, not completed computation; results must be committed before reporting them ready for planning. Full request/response fields, HTTP mappings, and generated contracts remain OPEN-29–30.

Retain V4's structured error envelope: `{error:{code,message,details},request_id}`. Preserve its unknown-resource, stale-version, invalid-input, and unavailable-provider distinctions. New computation with unavailable compute returns structured `503` (BD-31). Queue-full and queue-expiry reason codes and exact status mappings remain OPEN-29–30; do not silently conflate these with per-user rate limiting.

Visitors may inspect synthetic saved data/results. Presenter authentication controls mutations, scenario creation, submissions, reviews, receipt posting, and reset (BD-13). Sessions, expiry, proxy credential forwarding, CSRF, and rate limits remain OPEN-31. Restrict reset to the dedicated demo scope and preserve non-demo data; reset and retention details remain OPEN-32.

### 8.2 Execution and interruption

Forecasts, allocations, and comparisons use persisted background jobs (BD-11). One paired comparison is one top-level operation; its methods execute sequentially with identical solver search/wall settings and the same operational inputs.

When a healthy worker is busy, use the bounded queue. When compute is unavailable, reject new computation promptly and retain existing queued records (BD-31). Saved reads remain available when API/database access is usable. Stock operations do not acquire a forecasting dependency merely because a model worker is unavailable.

After loss of a running worker, expose the computation as interrupted/failed and require manual retry against saved inputs with linked attempt history (BD-12). Retain queued work. Do not automatically retry interrupted jobs, silently extend deadlines, or relabel a stale attempt as successful. Exact ownership, cancellation, reconciliation, enums, and attempt endpoints remain OPEN-30.

## 9. Observability and readiness

Use correlated structured JSON logs plus durable PostgreSQL audit/job records (BD-30). Distributed tracing is deferred. The earlier tracing selection was superseded; no OpenTelemetry/OTLP destination, Grafana/Jaeger service, or tracing vendor was selected.

Diagnostic information must identify request/job/run/scenario/plan context where applicable; requested and actual provider/model version; fallback/cache outcome; queue and execution durations; native solver status and configured limits; inventory version conflicts; and structured failure reasons. Preserve original generation time when reusing results.

Keep audit evidence durable and linked to the relevant mutation, actor, time, source, and version. Diagnostic logs do not replace the inventory ledger or required transactional audit linkage. Do not log credentials, tokens, connection strings, raw CSV rows, or complete request/snapshot payloads. Exact log fields, sinks, retention, redaction tests, and detailed audit contracts remain OPEN-33 with OPEN-09/32 dependencies.

Distinguish process liveness, core API/database readiness, compute availability, and provider qualification. Readiness should check database connectivity/schema compatibility without downloading/loading a model, running inference/solves, or creating a job. Exact readiness/capability endpoints and response schemas remain OPEN-29 and OPEN-33.

BD-37 selects a compute-supervisor heartbeat persisted in PostgreSQL every 5 seconds. After 15 seconds without an update, treat compute as unavailable for new work. The supervisor must remain able to report availability while expensive work runs; healthy busy is different from unavailable. Heartbeat freshness does not prove that a future job will succeed or that Chronos is qualified, warm, or accurate.

Heartbeat ownership/startup/race handling and database-time boundary tests still need specification with OPEN-30/33. A worker can fail between admission and execution; preserve the persisted job/attempt failure rules rather than promising instant detection.

## 10. Runtime and performance

### 10.1 Accepted initial profile

| Setting | Accepted value | Decision |
|---|---|---|
| Active expensive top-level operations | 1 | BD-34 |
| Waiting top-level operations | At most 2 | BD-35 |
| Queue-wait limit | 15 minutes (900 seconds) | BD-35 |
| Forecast-operation wall-clock limit | 300 seconds | BD-35 |
| Primary attempt when fallback is allowed | Stop by 270 seconds | BD-38 |
| Remaining fallback/completion allowance | Up to 30 seconds within the same 300-second deadline | BD-38 |
| Native solver search budget | 15 seconds per method | BD-35 |
| Whole method wall-clock limit | 25 seconds | BD-35 |
| Whole paired-comparison wall-clock limit | 60 seconds; methods run sequentially | BD-35 |
| Local compute-worker CPU ceiling | 6 CPU equivalents, configurable | BD-36 |
| Local compute-worker RAM ceiling | 8 GiB, configurable | BD-36 |
| Supervisor heartbeat | Every 5 seconds; unavailable after 15 seconds without an update | BD-37 |

These are ceilings, not expected runtimes, benchmarks, or guarantees that a model fits. They do not reserve CPU/RAM or include the API/database's additional resource needs. The CPU ceiling is not a promise of six dedicated physical cores. Configuration overrides must be explicit; do not silently grow resource or time allowances.

Keep API reads and polling responsive outside the expensive compute slot. The initial local runtime serializes forecasting and allocation work, including both methods of a comparison. Thread counts, API process settings, effective container limits, resource measurement, and deployment-specific supervision remain OPEN-35.

### 10.2 Deadline and fallback semantics

The forecast limit bounds the whole forecast operation, not a fresh allowance for each series/provider attempt. Queue waiting has its separate limit. With fallback allowed, stop the primary attempt by 270 seconds and use the remaining allowance for termination, baseline fallback, validation, and persistence (BD-38). An earlier primary failure may trigger fallback earlier; it does not need to wait until 270 seconds.

Fallback does not receive another 300 seconds. Reserving 30 seconds improves its opportunity to complete but does not guarantee usable inputs, successful fallback, or publication by the deadline. If fallback is disallowed, the reserved-fallback policy does not apply; the operation still has the same overall ceiling.

Enforce deadlines by containing/terminating actual computation; abandoning a future, cancelling an HTTP request, or merely changing the job state is insufficient. Solver search time differs from method wall time, which also covers construction, checking, and completion work. Parent comparison time also bounds orchestration of its sequential methods.

Expired or failed work retains an explicit outcome and reason, with manual retry where appropriate. Do not invent an incumbent after timeout or call a native `FEASIBLE` solution optimal. Detailed cleanup, cancellation, and independent child-result publication rules remain OPEN-30/35.

### 10.3 Performance acceptance

V4 §13.1 targets cached dashboard reads under 1 second and seeded solves under 5 seconds; the inherited solver example uses three sites. For the expanded six-beneficiary demonstration, measure and disclose actual responsiveness and resource use under the recorded configuration.

BD-39 allows release with a documented responsiveness-target miss when correctness, integrity, enforceable hard limits, and failure handling pass. A missed target remains unmet; do not describe all performance targets as passed. This explicitly relaxes target misses as release blockers, not correctness or the research gate.

Chronos qualification requires actual pinned-model evidence. Distinguish download, cold load, warm inference, cached reuse, and fixture replay; none proves the others. Record the full required data scope, including donation series, and do not shrink it silently to fit a runtime claim. Exact benchmark protocol and evidence remain OPEN-18/35.

## 11. Required acceptance evidence and research gate

These are implementation/release requirements and test targets, not checks executed by this documentation publication. Domain acceptance evidence remains NOT RUN/UNVERIFIED unless an actual recorded result establishes otherwise.

| Area | Required evidence | Dependencies |
|---|---|---|
| Database and migrations | Fresh isolated PostgreSQL migration, integrity constraints, and transaction rollback checks | OPEN-04, OPEN-09, OPEN-36 |
| Receipt and inventory concurrency | Historical import leaves stock unchanged; duplicate posting cannot duplicate movement; competing changes preserve versions/nonnegative balances and linked audit | BD-04–05, BD-25–26; OPEN-08–09 |
| Forecasting | Correct dated demand/donation outputs; preserved gaps/proxy labels; cutoff leakage checks; actual-provider metadata; usable permitted fallback and explicit failure without it | OPEN-12–18; BD-33, BD-38 |
| Scenario integrity | Source/snapshot inputs remain frozen; newer data needs a new scenario; explicit partial scope and exact reuse/refresh identity | BD-08–10, BD-29; OPEN-17, OPEN-19–20 |
| Transfer feasibility | Independent checks for lots, hard FEFO, expiry/ETA/use, conservation, donor demand/reserves, capacity, no self-transfer and no same-batch relay | BD-19, BD-32; OPEN-21–22 |
| Research mathematics | Full-paper mapping; hand/exhaustive independent oracles; AP/RP equality/near-boundary/group cases; active reified flags and nonzero penalties; W/Z decomposition; integer overflow/quantization checks | OPEN-23–25; BD-15–21 |
| Paired-method validity | Same operational snapshot/constraints/settings; independent feasibility of each result; AP/RP ablations and an interpretable changed allocation on the six-beneficiary seed | V4 TEST-EGP-01–07; BD-32–35 |
| Jobs and runtime | Enforced single operation/two waiters; queue expiry; stale heartbeat; healthy-busy distinction; real computation termination; 270/300-second fallback boundary; method/comparison limits; interrupted-job manual retry | BD-11–12, BD-31, BD-34–38; OPEN-30, OPEN-35 |
| API/access and audit | Saved reads do not compute; authorization at backend; structured errors; stale versions; `202` is not completion; committed results; redacted correlated logs and durable mutation audit | OPEN-29–33 |
| Supplier proposals | Conditional goods never become confirmed/on-hand; baskets respect selected budget/coverage rules; alternatives/uncovered need and paused choices remain explicit | BD-22–24; OPEN-03, OPEN-26–28 |
| Demonstration journey | Saved inputs → baseline forecast → shortage → paired allocation → disruption → new frozen scenario/replan → review/reset, preserving prior versions and simulated labels | V4 §§15–16; OPEN-32, OPEN-34 |

Before complex solver implementation, retain the [architecture research gate](../architecture/0001-v4-research-first.md): equation mapping, independent enumeration, fixed policy/scaling/category definitions, hard FEFO encoding, identical-feasibility verification, AP/RP ablations, and deterministic fixtures. The selected 10,000 scale is not evidence that this gate passed.

Verify the full mandatory core workflow with live baseline forecasting, real PostgreSQL/API integration, both real solver methods, and tested provider-failure/fallback paths (BD-33). Separately verify Chronos inference/evaluation. A baseline-only demonstration must disclose unverified Chronos; a failed research method must remain method-unavailable and cannot support a claim that the research implementation is complete.

Record acceptance ID, source/config/input identity, environment/dataset version, exact command, timestamp, PASS/FAIL/UNVERIFIED status, and evidence location. A fixture, mock, skipped test, timeout, or documentation review does not establish an unexecuted capability. The [acceptance matrix](ACCEPTANCE-MATRIX.md) still needs reconciliation with this expanded scope and the finalized contracts.

## 12. Documentation, integration, and unresolved work

BD-40 selects this separate detailed specification. The [checkpoint](BACKEND-DESIGN-CHECKPOINT.md) remains the decision history, 36-topic tracker, explicit alternatives, and resume guide. Keep their decision IDs and status consistent.

| Specification area | Accepted decisions | Main open dependencies |
|---|---|---|
| Architecture, access, and proxy | BD-13, BD-14 | OPEN-29, OPEN-31 |
| Products, history, receipts, and stock | BD-02, BD-03, BD-04, BD-05, BD-25, BD-26 | OPEN-04–11 |
| Forecast basis, gaps, uncertainty, and reuse | BD-06, BD-07, BD-27, BD-28, BD-29 | OPEN-12–18 |
| Frozen scenario and partial scope | BD-08, BD-09, BD-10 | OPEN-19–20 |
| Allocation targets, groups, weights, and numbers | BD-15, BD-16, BD-17, BD-18, BD-19, BD-20, BD-21 | OPEN-21–25 |
| Review and transfer network | BD-01, BD-32 | OPEN-02, OPEN-21–22 |
| Conditional supplier proposals | BD-22, BD-23, BD-24 | OPEN-03, OPEN-26–28 (paused) |
| Jobs, compute availability, and logs | BD-11, BD-12, BD-30, BD-31, BD-37 | OPEN-29–33 |
| Qualification and release evidence | BD-33, BD-39 | OPEN-18, OPEN-24, OPEN-34–35 |
| Runtime limits and resource profile | BD-34, BD-35, BD-36, BD-38 | OPEN-30, OPEN-35 |
| Documentation structure | BD-40 | OPEN-36 |

OPEN-33–36 are partially defined. Remaining work includes readiness/capability wire contracts, finalized audit/log schemas, full test fixtures/evidence, process/thread and termination details, measurement procedure, migrations, generated-contract workflow, and integration-guide reconciliation. Cross-topic dependencies remain open; this publication does not authorize choosing their unresolved values.

Integration follow-up must reconcile older guides that use direct browser-to-FastAPI access, synchronous plan creation, three-site scope, reusable mutable scenario assumptions, or unqualified provider readiness. Preserve the explicit selections instead: proxy access, background-job acceptance, the required expanded demo, fully frozen scenarios, and truthful capability reporting.

Use controlled Alembic migration and Pydantic/OpenAPI generation workflows once their contracts are finalized. Do not create speculative domain migrations, hand-written generated TypeScript, credentials, model downloads, or hosting changes in this documentation task.

Hosting/model setup remains paused after the user's reported step 2. Identify the relevant setup guide and verify state before any later authorized resumption. Do not start containers, download checkpoints, build heavy images, or benchmark inference while completing or publishing this draft.

### Source and companion documents

| Reference | Role |
|---|---|
| [V4 requirements](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) | Requirements, authoritative extensions, research priority, forecasting, and acceptance |
| [Shared Architecture and Contracts](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.2k9g9tk2rpug) | Cross-module conventions and V4 conflict interpretation |
| [Mathematical Research and Policy](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.o9ae2hmuri6j) | Adaptation limits and mathematical validation |
| [Optimization Engine](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.gj9xg6oi8r9j) | Shared feasibility and paired methods |
| [Forecasting and ML](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.4q4ahys8aav9) | Targets, adapters, fallback, and evaluation |
| [Inventory and Persistence](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.5jrs75ee9j2m) | Lots, ledger, projection, and persistence |
| [Backend API and Orchestration](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.8bsgg7gkb2fi) | API and execution behavior |
| [V4 text snapshot](SPEC-V4.snapshot.txt) | Recorded local extraction; inspect its tab/revision metadata |
| [Architecture/research gate](../architecture/0001-v4-research-first.md) | Proposed formulation and required independent validation |
| [Implementation plan](IMPLEMENTATION-PLAN.md), [invariants](INVARIANTS.md), [earlier project contract](PROJECT-CONTRACT.md) | Prior planning context; reconcile conflicts using explicit accepted decisions |
| [Acceptance matrix](ACCEPTANCE-MATRIX.md), [deployment guide](DEPLOYMENT.md), [contract boundary](../../packages/contracts/README.md) | Existing integration targets, not evidence that new behavior works |

Local-only supporting paths `LOCAL-COMPUTE-EVALUATION.md`, `FORECASTING-PROPOSAL-EVALUATION.md`, and `../setup/SETUP-PROGRESS.md` are not part of this publication. This draft and the checkpoint preserve the accepted requirements and pauses without requiring those files. No Google Doc content is changed by this commit.
