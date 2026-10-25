> OR ownership correction (October 24, 2026, explicit user direction): the OR assignment owns only the research-centered computation and necessary Python schemas. Next.js is frontend only; no Next API routes/proxies. Frontend, FastAPI routes/auth, data persistence and shared runtime belong to their developers. [Current scope and reversible handoff](../optimization/SCOPE-CORRECTION.md) supersede earlier broad OR task assignments; historical project requirements below do not transfer their ownership.

# PantryPulse Backend Specification — Working Draft

> **Current authority:** [Project specification V5](SPEC-V5.md). This checkpoint preserves accepted decision history and pauses. V5 adds BD-41 reconciliation, current code/branch evidence and the consolidated OPEN register; historical resume/status text below does not override it.

**Date:** October 24, 2026 (America/New_York)

**Status:** Design interview in progress. This checkpoint records 40 accepted decisions and the 36-topic tracker. OPEN-01 is resolved; OPEN-02 and OPEN-03 remain explicitly deferred; OPEN-26–28 are paused. OPEN-33–36 have accepted directions and remaining details. It is not a finalized implementation specification or evidence that the proposed features work.

**Planning-session fidelity review:** October 24, 2026. Reconciled the interview through BD-40, including the supplier-scope correction, the later topology selection, revised observability choice, and supplier-planning pause. This is documentation of selections, not validation of application behavior.

## Purpose and authority

Preserve the backend and API planning progress so the discussion can continue after a restart without losing selections, reopening settled questions, or mistaking recommendations for accepted defaults. The companion [backend specification](BACKEND-SPEC.md) explains the covered architecture, logical data model, contracts, processing rules, operations, and verification requirements. This checkpoint retains the decision history, remaining topics, explicit alternatives, and resume instructions (BD-40).

The accepted decisions below record the human user's selections. Earlier assistant recommendations that were not selected do not override them. In particular, scenarios are fully frozen, and draft supplier proposals are included. The temporary selection to omit supplier proposals was explicitly superseded by the user.

V4 remains the source specification, supported by its shared/domain task guides. This checkpoint records the agreed resolutions and additions that must be reconciled into those documents later; it does not silently rewrite the original specification. The user-provided Google Docs URL targets the Completion Log, not the V4 requirements tab.

Decision identifiers `BD-01` through `BD-40` belong to this checkpoint. They are distinct from historical `D01`, `D02`, and other identifiers in PROJECT-CONTRACT.md. Tracker identifiers `OPEN-01` through `OPEN-36` identify remaining topics, not additional accepted decisions.

## Design baseline and implementation status

The intended architecture is a modular Python FastAPI backend, PostgreSQL persistence, and a Next.js frontend. Pydantic/OpenAPI defines public API contracts, with generated TypeScript consumed by the frontend. The selected browser access path adds a thin Next.js proxy; domain logic remains in FastAPI.

The existing V4 baseline calls for a simulated humanitarian network with at least six beneficiary institutions plus hub(s), two resource categories, seven-day daily forecasts, a bounded allocation window, lot-aware expiry/FEFO, and a paired `CLASSICAL_GP` versus `EGP_PI_INSPIRED` comparison. These are carried-forward source requirements, not additional choices made in the interview. BD-32 resolves transfer topology to hubs and eligible beneficiaries supplying beneficiaries; detailed donor and transport rules remain OPEN-21–22.

The inspected [API entrypoint](../../apps/api/app/main.py) implements `GET /api/v1/health` as process liveness. It does not establish database, forecasting, or solver readiness. This checkpoint does not certify the domain database, job system, allocation engines, or end-to-end demonstration as implemented. Saving this document adds no application functionality.

Forecasts and recommendations remain projections. Current stock, confirmed future supply, uncertain predictions, and conditional proposals must remain distinguishable. No real purchasing, payment, or dispatch is authorized by this design checkpoint.

## Accepted decisions

All rows below are accepted directions. Their exact fields, algorithms, and edge cases may still require specification under the remaining-topic tracker. The recorded-choice column retains the selected option's letter and a shortened label; original “Recommended” annotations are omitted because recommendation status is not evidence of selection. Option letters are local to each question.

| ID | Topic | Recorded user choice | Agreed specification |
|---|---|---|---|
| **BD-01** | Plan review | A — Review only | Use a recorded “Mark reviewed” action identifying the plan/version, actor, and time. Review does not reserve inventory, move stock, or dispatch goods. Reservation and fulfillment are later extensions. |
| **BD-02** | Product identity | A — Standard resource | Products represent standardized resource types with explicit base units. Lots distinguish batches and expiration. No implicit package conversions or substitutions. |
| **BD-03** | Historical detail | B — Detailed donation receipts | Store daily demand totals and individual donation receipts. Aggregate actual received donations by receiving site/product/site-local day for forecasting. Offered or pledged quantities are not received quantities. |
| **BD-04** | Receipt posting | B — Explicit stock posting | Historical imports never change current physical stock. New donation receipts support a deliberate, exactly-once posting operation linked atomically to lot and ledger changes. This is separate from review-only allocation plans. |
| **BD-05** | Corrections | A — New revisions | Append corrected revisions and preserve originals. Snapshots retain the exact revisions used. Correcting posted stock requires a linked, audited adjustment; it cannot silently rewrite the inventory ledger. |
| **BD-06** | Unknown requested demand | B — Allow explicit proxy | Permit fulfilled-demand proxies only through explicit opt-in. Preserve target-basis metadata and visible warnings through forecasts and plans. Missing values remain distinct from zero. |
| **BD-07** | Supply baseline | A — Confirmed only | Default planning uses eligible current stock and qualifying confirmed arrivals. Forecast donations remain available in charts and explicitly conditional scenarios. Predictions do not become physical on-hand stock. |
| **BD-08** | Partial plans | B — Explicit partial plans | Permit deliberately reduced planning scopes. Identify excluded sites/products and calculate denominators and comparison groups from the frozen scope. Missing inputs cannot silently remove need. The primary research demonstration still needs its required full population. |
| **BD-09** | Scenario lifecycle | A — Fully frozen scenario | Fully freeze scenarios: pin the selected forecast, inventory, supplies, and other planning inputs at creation. Using newer operational inputs requires a new scenario. The alternative of reusing assumptions with separate immutable per-run snapshots was not selected. |
| **BD-10** | Snapshot storage | A — JSONB package | Store frozen planning inputs in a validated PostgreSQL JSONB package with a schema version, content hash, and provenance/source references. Operational records and results remain relational. Store model identity/version references, not model weights, in the package. |
| **BD-11** | Expensive operations | A — All jobs | Forecasting, allocation, and paired method comparison use background jobs with persisted status. Return `202 Accepted` and expose committed results through reads. Acceptance is not successful completion or proof of a valid plan. |
| **BD-12** | Interrupted jobs | A — Manual retry | Retain queued work. Expose computations whose running worker was lost as interrupted/failed, and require manual retry against saved inputs with linked attempt history. Do not automatically retry these interrupted jobs. This decision is separate from forecast-provider fallback; exact job-state enum values remain OPEN-30. |
| **BD-13** | Demo access | A — Presenter only | Visitors may inspect synthetic saved data and results. Presenter authentication controls changes, scenario creation, job submission, plan reviews, receipt posting, and reset. Public isolated visitor experiments are not selected. |
| **BD-14** | Browser/API connection | A — Next.js proxy | Browser requests go through a thin same-origin Next.js proxy. FastAPI retains domain validation, authorization, integrity checks, and persistence. Reconcile older direct-browser-access setup guidance during integration. |
| **BD-15** | Fairness period | A — Planning window | Define one fairness goal per beneficiary/product over the allocation window. Retain daily stock, service, and shortage projections and arrival/expiration constraints. Late arrivals cannot satisfy already missed demand. |
| **BD-16** | Relative-deprivation groups | A — Same-product scope | Compare all included positive-demand beneficiaries separately for each product. Freeze membership with scenario scope and calculate the group average from the allocation being evaluated. Meaningful RP groups require at least two positive-demand members. |
| **BD-17** | Allocation targets | A — Forecasts | Derive targets from the selected forecast plus frozen scenario assumptions, using documented per-day upward rounding before aggregation. Both allocation methods receive identical targets. A future authoritative-request override workflow is not selected for the first release. |
| **BD-18** | Vulnerability attributes | A — Prepared scores | Import prepared, documented 0–1 institution-level scores with source/raw values, preparation notes, provenance, and versions. The backend validates scores and applies the declared proxy-weight formula; it does not implement a raw-measurement normalization service. Demo attributes remain labeled simulated. |
| **BD-19** | Shared product capacity | A — Joint optimization | Optimize products jointly under shared handling/transport capacity. Keep product-specific inventory, demand, units, and metrics. Document handling coefficients rather than treating meals and bottles as interchangeable stock. |
| **BD-20** | Summed-shortfall aggregation | A — Per goal | Retain V4's per-goal sum of weighted deficits, `W = sum(z)`. Products with more included positive-demand goals contribute more terms. Equalized per-product averages are not selected. |
| **BD-21** | Integer precision | A — Fixed point | Use the proposed fixed-point scale of 10,000, rounding weighted deficits down for the computational representation used by the objective and AP/RP comparisons, not merely for display. Retain original counts and ratio information. Version, disclose, and test near-threshold effects; independent validation and integer-bound checks remain required. |
| **BD-22** | Supplier proposal scope | B — Draft proposals, explicit correction | Include draft supplier replenishment proposals using seeded or manually entered offers. No outgoing supplier orders or payments. Keep unapproved proposals out of physical inventory and the confirmed-resource primary comparison. This supersedes the earlier temporary internal-allocation-only selection. |
| **BD-23** | Supplier coverage period | B — After-arrival cover | Size proposals for a defined period after the supplier's estimated arrival, accounting for projected stock, confirmed arrivals, and the selected transfer plan. Stay within available forecast dates; later deliveries cannot repair earlier lost demand. |
| **BD-24** | Supplier budget coordination | B — Coordinated basket | Produce a selected proposal basket that respects the frozen shared simulated budget and per-order limits. Preserve alternatives and explain uncovered need. Classical/research baskets are alternatives evaluated against the same budget, not two actual purchases charged together. |
| **BD-25** | New-lot eligibility | A — Declare on posting | Operators explicitly declare lot eligibility during receipt posting. Unknown status remains held/unavailable. Record actor, time, and reason; audit later changes and invalidate affected plans. Status labels and dates do not independently establish food safety. |
| **BD-26** | Import atomicity | A — Partial import | Permit partial imports: accept valid demand rows and complete valid donation receipts. A receipt and its lines are accepted or rejected together. Report precise errors and accepted/rejected counts; duplicates are not silently overwritten. |
| **BD-27** | Missing historical days | A — Preserve gaps | Preserve missing values and flags; do not generate replacement historical observations through backend imputation. Use supported missing-data handling or labeled fallback; report insufficient inputs explicitly. This does not remove the separate opted-in proxy policy. |
| **BD-28** | Conservative planning | B — Explicit buffer | Where upper quantiles are unavailable, allow an explicit presenter-selected buffer recorded in the scenario. Missing quantiles stay null. Label mixed quantile/buffer inputs per series and never present the buffer as a calibrated probability or fabricated `p90`. |
| **BD-29** | Forecast reuse | A — Reuse + refresh | Reuse exactly matching immutable forecast results by default, with an explicit presenter-requested forced recomputation option. Cache identity must include relevant inputs/settings. Preserve original generation timestamps and actual model/fallback provenance; reuse is not new inference. |
| **BD-30** | Observability approach | Latest revision — Logs and audit | Use correlated structured JSON logs and durable PostgreSQL audit/job records with lightweight readiness/capability checks. The later logs-and-audit selection supersedes the earlier tracing selection. Distributed tracing is deferred; no OTLP destination, tracing vendor, or additional service was selected. |
| **BD-31** | Compute unavailable | A — Reject promptly | When API/database access works but compute is unavailable, reject new computation promptly with structured `503`. Preserve saved reads and existing queued work. A healthy busy worker follows the bounded queue policy; stock operations do not depend on forecasting availability. |
| **BD-32** | Transfer topology | B — Hubs and beneficiaries | Resolve OPEN-01: eligible hubs and beneficiaries may supply other beneficiaries along allowed routes. Protect local beneficiary demand/reserves, enforce compatible eligible lots/ETA/capacity and no self-transfer, and prohibit forwarding incoming stock within the same batch. Both allocation methods use the same network and constraints; detailed rules remain OPEN-21–22. |
| **BD-33** | Forecast qualification gate | A — Separately qualify | Require the mandatory core workflow to pass with live baseline forecasting, real PostgreSQL/API and both solver integrations, plus tested provider failure/fallback. Separately qualify actual pinned Chronos inference and evaluation. Chronos remains preferred when installation/inference/runtime permit; untested capability is unverified, and the setup pause is not evidence of infeasibility. The research gate remains mandatory. |
| **BD-34** | Expensive-work concurrency | A — One at a time | Serialize expensive forecasting/allocation operations. Treat a comparison as one top-level operation with its two methods sequential on the same snapshot and equivalent solver settings. Keep HTTP reads/polling outside the compute slot responsive. |
| **BD-35** | Runtime profile | B — Longer computation | Allow one active operation and at most two waiting; maximum queue wait 15 minutes (900 seconds). Forecast wall limit 300 seconds; native solver search 15 seconds per method; whole method wall limit 25 seconds; whole paired comparison wall limit 60 seconds. Enforce actual termination/containment and truthful outcomes. These are initial ceilings, not measured performance promises. |
| **BD-36** | Local resource profile | A — Local demo profile | Adopt configurable local compute-worker ceilings of 6 CPU equivalents and 8 GiB RAM. These do not reserve resources, include API/database needs, or prove Chronos fits. Verify effective limits and measure later; no model/hosting setup is resumed. |
| **BD-37** | Compute availability detection | A — Heartbeat | Persist a compute-supervisor heartbeat in PostgreSQL every 5 seconds; after 15 seconds without an update, treat compute as unavailable for new jobs. The supervisor must report while expensive work runs. A heartbeat is not model qualification, inference, or proof that a future job will succeed. Exact ownership/readiness wire details remain OPEN-30/33. |
| **BD-38** | Forecast fallback deadline | A — Reserve time | When fallback is allowed, stop the primary attempt by 270 seconds and reserve up to the remaining 30 seconds for stopping that work, baseline fallback, validation, and persistence within the same 300-second operation limit. An early failure may fall back earlier. No extra 300-second allowance or guarantee of fallback success is implied. |
| **BD-39** | Responsiveness acceptance | A — Disclose misses | Measure the 1-second saved-read and 5-second per-method solve targets on the expanded demo. Missing a responsiveness target alone need not block release if correctness, integrity, hard limits, and failure handling pass. Disclose misses as unmet targets/performance limitations; this does not relax the research gate or establish performance proof. |
| **BD-40** | Documentation organization | A — Separate spec | Put detailed current requirements in BACKEND-SPEC.md. Keep this checkpoint for decisions, open/deferred/paused topics, source links, and resumption. Cross-link the files and distinguish agreed design from implemented and verified behavior. |

### Fidelity guardrails

- A choice is accepted because the user selected it, not because the assistant recommended it. The fully frozen scenario choice in BD-09 is an important example: the recommended alternative was not chosen.
- For BD-22, the latest explicit correction controls. The user said: “lets continue from where we left off but for the supplier replenishment, choose option B.” The preceding internal-only selection is historical, not active.
- The later logs-and-audit revision in BD-30 supersedes the earlier tracing selection. No tracing destination was selected. BD-35 records option B (longer computation), while BD-36–40 record the later option A selections.
- Supplier planning is paused; the assistant's recommendation of one offer per need was not selected. Do not infer it as a default.
- Plan review and donation receipt posting are different operations. BD-01 leaves plan review without stock effects; BD-04 explicitly permits stock changes when posting new receipts.
- The JSONB choice does not settle the exact snapshot schema. BD-35–38 now settle the stated runtime/resource/fallback limits; job enums, retry/cancellation contracts, ownership, and other OPEN-30 details remain unresolved. An accepted direction is not approval of unspecified implementation details.
- The 36 tracker topics are the assistant's planning inventory requested by the user. They are not 36 additional accepted features, parameter defaults, or claims that previously discussed behavior is unimplemented.
- Any earlier illustrative number or example is not a selected default unless the decision expressly adopts it. The scale of 10,000 was selected in BD-21; runtime/resource/heartbeat/fallback limits were subsequently selected in BD-34–38. Supplier coverage days, capacity coefficients, buffer percentages, and other unresolved values still require specification.

## Resolved choice: OPEN-01 — Transfer topology

**History:** The user initially deferred this topic. That deferral was superseded by: “additionally, for the OPEN-01 transfer topology, we will go with option B: hubs and beneficiaries”. BD-32 records the accepted selection. The alternatives remain below for history; only B is active.

| Alternative | Technical meaning | Simple meaning | Main tradeoff |
|---|---|---|---|
| **A. Hubs only — not selected** | Candidate transfers originate at hubs and end at beneficiaries. Beneficiary stock still reduces local need. | Hubs supply pantries; pantries do not send supplies to each other. | Smaller feasible network and simpler validation, but fewer redistribution opportunities. |
| **B. Hubs and beneficiaries — selected** | Eligible beneficiaries may also supply surplus along allowed routes after local-demand/reserve protection. Incoming stock cannot be forwarded within the same batch. | A pantry with enough spare stock can help another pantry. | More flexible sharing, with additional donor-protection, route, and independent-verification cases. |

Option B is an extension to the published food-bank-to-institution flow inspected during the discussion. It is not established as a published or validated lateral-transfer feature. Both allocation methods must receive the same selected network and constraints.

Illustrative compute discussion: one hub and six beneficiaries have six hub-to-beneficiary connections. Adding all directed beneficiary-to-beneficiary connections gives `6 + 6 * 5 = 36`. This does not imply six times the runtime or memory. Solver difficulty depends on eligible lots, constraints, and competing choices. Extra hardware is not inherently required at the proposed demo size, but performance is unmeasured. Forecasting does not automatically need a larger model merely because transfers have more possible origins.

## Explicitly deferred alternatives

Only OPEN-02 and OPEN-03 remain explicitly deferred. The user requested that both alternatives in each remain documented for a later specification version. No active option is inferred from recommendations. Retaining alternatives does not commit the team to implementing both, a runtime toggle, or a hidden fallback. A dependent implementation needs a later recorded selection.

### OPEN-02 — Transfer-benefit attribution

**User's deferral:** “keep both options as potential options and the decision for this one will be made later.”

| Alternative | Technical meaning | Simple meaning | Main tradeoff |
|---|---|---|---|
| **A. Plan/site impacts and transfer rationale** | Compute full-plan and beneficiary/product before/after outcomes. Link each transfer to its goal and verified eligibility/timing rationale without a standalone numerical benefit claim. | Explain how each shipment contributes to a plan whose overall effects are shown. | Smaller and clearer attribution scope, but no per-shipment reduction number. |
| **B. Add marginal transfer estimates** | Remove one transfer from the otherwise fixed plan, recompute projections without reoptimizing, and label the difference with an explicit attribution method. | Show what would change if this shipment were absent and everything else stayed the same. | More detailed inspection, with extra calculations and non-additivity cautions, especially for threshold-based metrics. |

The image's generic `expected_benefit` field is not a finalized API field. If numerical attribution is selected, define its quantity, horizon, unit, and counterfactual precisely. Neither alternative measures observed real-world impact.

### OPEN-03 — Supplier-budget priority

**User's deferral:** “defer this choice to a later spec, pick both for now and present them as options”.

| Alternative | Technical meaning | Simple meaning | Main tradeoff |
|---|---|---|---|
| **A. Earliest actionable shortage** | Prioritize the earliest shortage that a timely supplier delivery can address; break ties by unmet-demand proportion and stable identifiers. | Help the pantry that is about to run short first. | Clear urgency-based behavior, but a less vulnerable site can precede a more vulnerable one. |
| **B. Vulnerability first** | Prioritize higher frozen vulnerability weights among eligible needs; break ties by actionable shortage date, unmet-demand proportion, and stable identifiers. | Give higher-priority institutions the limited purchase budget first. | Extends declared vulnerability priorities, but may leave earlier shortages elsewhere uncovered. |

These were proposed as transparent procurement heuristics, applied consistently after either allocation method. They are not substitutes for the AP/RP research objective and do not establish a globally optimal purchase basket. The active supplier-budget priority remains unselected despite the acceptance of coordinated baskets in BD-24.

## Remaining-topic tracker

An unchecked item means its full specification is not frozen. It does not mean its accepted direction should be reopened. Some topics need another human choice; others require technical elaboration from existing decisions. There are 36 tracked topics, including resolved OPEN-01, explicitly deferred OPEN-02/03, and paused OPEN-26–28, not necessarily 36 further questions. OPEN-33–36 remain unchecked because accepted directions do not settle all their details.

### Topology and deferred choices

- [x] **OPEN-01 — Transfer topology.** Resolved by BD-32: option B, hubs and eligible beneficiaries. Detailed donor/projection/route constraints remain OPEN-21–22.
- [ ] **OPEN-02 — Transfer-benefit attribution.** Deferred: preserve aggregate-impact/rationale and marginal-counterfactual alternatives.
- [ ] **OPEN-03 — Supplier-budget priority.** Deferred: preserve urgency-first and vulnerability-first alternatives.

### Data model and inventory

- [ ] **OPEN-04 — Concrete database schemas.** Finalize tables, columns, PostgreSQL types, identifiers, foreign keys, uniqueness rules, indexes, and canonical names.
- [ ] **OPEN-05 — Network and resource definitions.** Specify organization/site roles, donor relationships, standardized product definitions, base units, and ownership boundaries.
- [ ] **OPEN-06 — Time and expiration semantics.** Define operational dates, time zones, cutoff times, arrival timing, expiration boundaries, and missing-expiration handling.
- [ ] **OPEN-07 — Historical revision selection.** Define supersession, active-revision selection, source identifiers, duplicate detection, and exact snapshot references.
- [ ] **OPEN-08 — Donation receipt lifecycle.** Specify headers/lines, lot creation/linkage, posting, cancellation, correction, reversal, and already-consumed-stock cases.
- [ ] **OPEN-09 — Inventory transactions and concurrency.** Define ledger authority, balance updates, locking, version scope, idempotency-key reuse, and rollback behavior.
- [ ] **OPEN-10 — Expected-supply lifecycle.** Define confirmation, receipt, cancellation, inventory linkage, and reconciliation preventing double counting, including conditional donation assumptions.
- [ ] **OPEN-11 — Counts and discrepancies.** Decide first-release coverage for physical counts, discrepancy review, and controlled stock corrections.

### Forecasting

- [ ] **OPEN-12 — Exact forecasting contracts.** Define DailyObservation, service inputs/outputs, forecast points, per-series metadata, availability, warnings, and errors. Keep provider-native formats inside adapters.
- [ ] **OPEN-13 — Baseline and fallback rules.** Freeze minimum-history requirements, seasonal references, sparse-history behavior, strategy selection, fallback eligibility, and proxy application rules.
- [ ] **OPEN-14 — Forecast-output validation.** Define central estimates versus quantiles, nonfinite/negative outputs, crossed quantiles, and any permitted postprocessing.
- [ ] **OPEN-15 — Covariates and provider configuration.** Specify allowed features, future-known information, checkpoint/version pinning, series grouping, and relevant inference settings.
- [ ] **OPEN-16 — Conservative-mode parameters.** Define buffer defaults/ranges, application granularity, and per-series mixed quantile/buffer labeling without changing stored quantiles.
- [ ] **OPEN-17 — Cache and duplicate submissions.** Specify exact identity, forced refresh, concurrent-request deduplication, fallback-result reuse, and original generation timestamps.
- [ ] **OPEN-18 — Forecast evaluation.** Define chronological windows, sample requirements, MAE/WAPE/bias conventions, uncertainty evaluation, and provider-selection evidence.

### Scenarios, projections, and optimization

- [ ] **OPEN-19 — Snapshot construction.** Define the full JSONB schema, immutable source references, canonical serialization, hashing, schema versioning, and explicit partial-scope representation.
- [ ] **OPEN-20 — Staleness and historical replay.** Specify invalidating changes, replacement scenarios, archived-result visibility, and historical reruns versus current recommendations.
- [ ] **OPEN-21 — Dated stock projection and donor protection.** Finalize event ordering, daily consumption/lost-demand calculations, reserves, hard FEFO enforcement, and exclusion reasons.
- [ ] **OPEN-22 — Transport and capacity definitions.** Specify allowed routes, ETA assumptions, capacity units, product handling coefficients, receiving limits, and modeled costs.
- [ ] **OPEN-23 — Complete objective policy.** Freeze classical/research formulas, coefficients, AP/RP excess aggregation, cost/waste normalization, defaults, and permitted parameter ranges.
- [ ] **OPEN-24 — Numerical and boundary behavior.** Finalize fixed-point encoding, overflow limits, strict comparisons, zero-demand cases, invalid groups, and independent verification.
- [ ] **OPEN-25 — Policy and attribute management.** Define immutable versions, editing/creation permissions, validation, methodology output, and how changes create new frozen scenarios.

### Supplier replenishment

- [ ] **OPEN-26 — Supplier offer selection.** PAUSED. Define valid offers, arrival requirements, minimum/available quantities, expiration assumptions, price validity, and selection/tie-breaking rules. The last unanswered question is one offer per beneficiary/product versus combining offers; neither option was selected.
- [ ] **OPEN-27 — Coverage and budget parameters.** PAUSED. Choose days-of-cover defaults, horizon limits, partial coverage, currency representation, budget periods, and per-order limits. Preserve after-arrival coverage and coordinated budgets (BD-23–24).
- [ ] **OPEN-28 — Proposal lifecycle and conditional outcomes.** PAUSED. Define draft statuses, regeneration/cancellation, alternatives, explanations, and conditional projections without creating confirmed supply or actual spending.

OPEN-03 remains the separate deferred choice about which needs receive priority within the coordinated basket.

### API, execution, and access

- [ ] **OPEN-29 — Endpoint and wire-contract catalog.** Finalize routes, request/response fields, filtering, pagination, validation, errors, HTTP statuses, and generated TypeScript contracts.
- [ ] **OPEN-30 — Job orchestration.** Define states, worker ownership, queue limits, cancellation, actual computation timeouts, manual retries, publication, and independent comparison-method failures.
- [ ] **OPEN-31 — Presenter authentication and proxy security.** Specify sessions, login/logout, expiry, credential forwarding, backend verification, CSRF protection, and request limits.
- [ ] **OPEN-32 — Demo isolation and retention.** Define reset boundaries, audit preservation, snapshot/job retention, cache cleanup, and historical-result access.

### Verification, operations, and documentation

- [ ] **OPEN-33 — Observability and readiness.** PARTIALLY DEFINED by BD-30/31/37: JSON logs plus durable audit/job records, tracing deferred, prompt unavailable-compute rejection, and a 5-second heartbeat stale after 15 seconds. Still specify exact log/audit and readiness/capability schemas, ownership/races, sinks/retention, probe bounds, and redaction tests; see the [backend specification](BACKEND-SPEC.md#9-observability-and-readiness).
- [ ] **OPEN-34 — Acceptance tests and research gate.** PARTIALLY DEFINED by BD-33/39 and the [required evidence matrix](BACKEND-SPEC.md#11-required-acceptance-evidence-and-research-gate): core baseline/fallback workflow, separate Chronos qualification, real DB/API/solver checks, independent mathematical oracles, paired-input/ablations, and demo journey. Finalize dependent fixtures/test contracts and record actual evidence; this save runs no application acceptance tests.
- [ ] **OPEN-35 — Runtime and performance limits.** PARTIALLY DEFINED by BD-34–39: accepted serialization, longer queue/time limits, configurable 6-CPU/8-GiB worker profile, heartbeat/fallback deadlines, and disclosure of responsiveness misses. Remaining process/thread settings, actual termination/cancellation mechanics, effective limit verification, and measurement protocol depend on OPEN-30 and later authorized setup; see the [runtime specification](BACKEND-SPEC.md#10-runtime-and-performance).
- [ ] **OPEN-36 — Documentation and integration.** PARTIALLY DEFINED by BD-40: the separate [backend specification](BACKEND-SPEC.md) and this checkpoint now have distinct roles, cross-links, and decision traceability. Migration/contract-generation procedures, setup-guide reconciliation, and integration details remain open.

## Supplier planning pause

The user said: “we will continue with supplier replenishment later. i will provide instructions for this pause after this prompt”. The next instruction authorized saving and publishing the covered requirements, not selecting another supplier option.

Preserve the last unanswered OPEN-26 question for a later user-directed resumption:

| Unselected option | Meaning | Tradeoff |
|---|---|---|
| A. One offer per need | Select at most one offer per beneficiary/product in a proposal basket, keeping other offers as alternatives | Simpler but may leave need uncovered even when combined availability could cover it |
| B. Combine offers | Multiple supplier offers may contribute to the same beneficiary/product need, each subject to its terms and the shared budget | More coverage potential with additional quantity, delivery, minimum-order, and fee interactions |

The assistant recommended A. The user selected neither option. OPEN-26–28 stay paused; OPEN-03's budget-priority alternatives remain separately deferred. Saving this checkpoint does not reopen the interview or resume supplier implementation.

## Research and proposal clarifications to preserve

The inspected portions of Rampazo et al.'s study describe donation collection, food-bank inventory management, and allocation to institutions. Its case-study demand is estimated using families served and food-kit composition. Neither pantry-to-pantry transfers, our Chronos forecasting pipeline, nor a submitted-request override workflow is established as a direct reproduction of that application. See the [published study, especially sections 3–4 and Appendix C](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.70252).

Continue to use `EGP_PI_INSPIRED` for the bounded adaptation. Prepared proxy weights do not reproduce the full endogenous vulnerability-weight mechanism. The equation-level mapping and research-validation gate remain incomplete; the precision choice in BD-21 is not proof that the implementation is mathematically verified. Do not claim observed fairness, poverty reduction, calibrated stockout probabilities, or an exact research reproduction.

Both allocation methods must use identical operational inputs and constraints, with their stated objectives and actual solver statuses. A failed research method remains visibly failed; a classical result cannot be relabeled as research output.

The original forecasting proposal correctly separated historical observations, execution metadata, and forecast points. Its ForecastInput/ForecastOutput objects are application service contracts, not the native Chronos interface. Preserve separate donor and receiving-site identities, a clear received-donation target, and per-series actual model/fallback/outcome metadata when completing the schema. These are design requirements to specify, not finished SQL or Pydantic definitions.

### Known documentation reconciliations

- V4 section 9 projects against forecast requests, while section 11.7 calls the target recorded requested units. BD-17 explicitly selects forecast-derived targets for this release.
- Earlier plan-creation examples return 201 after synchronous solving. BD-11 selects 202 job acceptance for expensive work; final lifecycle/wire details remain OPEN-29 and OPEN-30.
- Existing setup examples show browser-to-FastAPI calls. BD-14 selects the thin Next.js proxy instead; integration documentation must be updated later.
- BD-09 selects fully frozen scenarios, not the earlier recommended reusable-assumptions/per-run-input alternative.
- BD-22 includes draft supplier proposals. The user's later option B selection supersedes the temporary option A selection to omit them.
- The images' “approve simulated plan” becomes review-only under BD-01. Their `expected_benefit` field remains unresolved under OPEN-02.
- BD-32 resolves the earlier topology deferral to hubs and beneficiaries. Do not carry the obsolete three-deferred-choice count into later documents.
- BD-33 follows V4 §§2.4, 9, 12.3 and 16.6: mandatory baseline/fallback, with preferred Chronos subject to demonstrated feasibility and separate qualification. The setup pause does not establish infeasibility.
- BD-39 permits disclosed responsiveness-target misses without relaxing correctness, hard limits, or research validation. The original 5-second solver example used three sites; the expanded required demo must be measured honestly.
- BD-30 supersedes tracing with logs/audit; BD-35 adopts the longer limits; BD-38 reserves fallback time within the same forecast deadline.
- Forecast donations are uncertain numerical estimates; confirmation status belongs to operational supply records. These must not be conflated in snapshots or projections.

## Source references and local context

The Google Docs tabs below were inspected during the planning discussion. These links identify the source material; this checkpoint does not update the Google Doc or assert that every future source revision has been reconciled.

| Source | Purpose |
|---|---|
| [V4 requirements](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.951hp1xdarlq) | Authoritative requirements tab identified by the shared guides. |
| [Completion Log](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.2hj0gr7gof5a) | The tab in the user's supplied URL; implementation/setup history rather than the primary requirements. |
| [00 Shared Architecture and Contracts](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.2k9g9tk2rpug) | Cross-module vocabulary, scope, contracts, and unresolved integration choices. |
| [01 Mathematical Research and Policy](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.o9ae2hmuri6j) | Adaptation limits, policy definitions, and research validation. |
| [02 Optimization Engine](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.gj9xg6oi8r9j) | Shared constraints, model results, status handling, and independent checking. |
| [03 Forecasting and ML](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.4q4ahys8aav9) | Targets, preparation, adapters, fallback, and evaluation. |
| [04 Inventory and Persistence](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.5jrs75ee9j2m) | Ledger, lots, projection, transactions, and snapshots. |
| [05 Backend API and Orchestration](https://docs.google.com/document/d/1WcsV69YCE1mqW2pI7IyEFQBSuwQB_hMhVQKfU20ZFk8/edit?tab=t.8bsgg7gkb2fi) | API conventions, jobs, lifecycle, and method comparison. |

Three supporting files below remain local-only. They are listed as code paths rather than links and are not included in this documentation publication. This checkpoint and the backend specification preserve the accepted requirements, unresolved alternatives, and pauses without requiring those files.

| Local document | Use when resuming |
|---|---|
| [Backend specification](BACKEND-SPEC.md) | Detailed covered requirements, runtime profile, required evidence, unresolved dependencies, and source references. |
| [Architecture and research gate](../architecture/0001-v4-research-first.md) | Current local architecture, proposed formulas, constraints, and validation gate. |
| [V4 text snapshot](SPEC-V4.snapshot.txt) | Source extraction with its recorded tab/revision identity; inherited examples need conflict resolution. |
| [Project contract](PROJECT-CONTRACT.md) | Prior contracts and historical decisions; reconcile explicit selections in this checkpoint. |
| [Implementation plan](IMPLEMENTATION-PLAN.md) | Research-first priorities and the distinction between scaffold and completed platform. |
| [Invariants](INVARIANTS.md) | Conservation, timing, provenance, version, and accounting checks. |
| Forecasting proposal evaluation — `FORECASTING-PROPOSAL-EVALUATION.md` | Local-only supporting file: earlier correct/reject/improve analysis that motivated the design discussion. |
| [Detailed backend explanation](BACKEND-DATA-FLOW.md) | Earlier explanatory document; not updated by this checkpoint save. |
| [Simple backend explanation](BACKEND-DATA-FLOW-SIMPLE.md) | Plain-language companion; not updated by this checkpoint save. |
| [Generated-contract boundary](../../packages/contracts/README.md) | Pydantic/OpenAPI authority and generated TypeScript expectations. |
| Local compute evaluation — `LOCAL-COMPUTE-EVALUATION.md` | Local-only supporting file: proposed resource/caching strategy and measurement limits; not performance proof. |
| Hosting/model setup pause — `../setup/SETUP-PROGRESS.md` | Local-only supporting file: user's pause on hosting/model preparation; the pause is also preserved in the resume instructions below. |

## Resume instructions

1. Read this checkpoint, the [backend specification](BACKEND-SPEC.md), and relevant source material. Preserve accepted decisions BD-01 through BD-40 unless the user explicitly revises them.
2. **Supplier planning OPEN-26–28 is paused.** Wait for the user's direction before resuming it. When resumed, return to the unanswered OPEN-26 split-sourcing question above; neither option was selected. The last accepted design decision was BD-40, separate specification/checkpoint roles.
3. Ask one material design question at a time. For every option, provide a technical explanation, a simple-language explanation, and advantages/tradeoffs. Then wait for the user's selection.
4. OPEN-01 is resolved to option B by BD-32. Keep OPEN-02 and OPEN-03 deferred until a later explicit selection. Preserve the unanswered split-sourcing alternatives separately; recommendations do not select an option.
5. Add subsequent accepted decisions after BD-40 and update both documents consistently. Keep identifiers stable. OPEN-33–36 remain partially defined; mark topics complete only when their full specification is settled, not merely because a direction has been chosen.
6. Preserve the distinction between documentation, implementation, and verification. Do not report unimplemented endpoints, schemas, provider integrations, or solver behavior as working features.
7. Keep hosting/model setup paused. The user previously reported stopping after step 2; identify the relevant guide and verify state before resuming that separate work. Do not start containers, download checkpoints, perform heavy builds, or benchmark inference without a new instruction resuming it. Continuing this design interview does not resume hosting setup.
8. Preserve unrelated modified/untracked files. No real vendor order, payment, or dispatch is authorized. Future implementation-dependent decisions and the research gate must be resolved before treating this working draft as implementation-ready.

This documentation checkpoint preserves planning progress and the remaining-topic tracker. Publication of these two documents does not create a recurring task, resume the supplier interview or hosting/model setup, implement application behavior, or replace the original source documents.
