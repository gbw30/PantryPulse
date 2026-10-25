# PantryPulse OR service Codex execution specification

**Draft 1.1 • repository refresh October 24, 2026 America/New_York • full first-draft build contract**

Refresh scope: main `f3946c7` integrates forecasting and the design lab through PR #51. Reuse that corrected code, preserve its tests and finish the remaining operational/public integration. The OR mathematical formulation and all 20 provisional choices remain unchanged. Companion 01 changes only provenance; companion 02 updates existing-module ownership, adapters and compatibility checks.

## 1. Task and authorized scope

Build PantryPulse's complete first-draft OR service in the existing repository. Implement the agreed input-to-result pipeline, both real OR-Tools allocation objectives, shared physical constraints, independent verification, PostgreSQL persistence, supervised durable jobs, public contracts, presenter controls, scripts, tests and a working simulated demonstration. Connect real upstream sources when their committed contracts exist; report separately whether the live forecasting-to-OR journey actually passes.

This is an implementation assignment, not a request for another high-level plan. Work through the ordered packages below, produce the concrete artifacts, resolve routine implementation details using the provisional decision process, run meaningful checks and finish with evidence. Do not stop after scaffolding, DTOs, mocked solvers, static comparison output or a test count. Never claim a required integration succeeded because a stub reports unavailable.

Read these companion files fully before editing:

1. `01_OR_Mathematical_Specification.md` — exact process, constraints, objectives, all 20 provisional decisions, proofs and expected example optima.
2. `02_OR_Implementation_Design.md` — exact callable contracts, schema fields, SQL records/transactions, worker/API behavior, CLI algorithms and tests.
3. This file — execution order, ownership, gate requirements, acceptance and final handoff.

Put them under `docs/optimization/` in the implementation branch when starting, retain their identity as Draft 1.1, and update factual baseline fields if the actual repository changed. These documents derive from the attached Hackathon spec/V5, main and related branch review; they do not alter the source attachment.

**Authority:** subsequent explicit user instructions → V5 and accepted compatible backend decisions → the user-authorized provisional choices in this package → historical references. Follow applicable repository instructions after reading them. Preserve unrelated local changes. Do not infer permission to merge branches, deploy, order, pay or dispatch from this build assignment. Supplier planning and heavy hosting/model setup remain paused.

The user's explicit direction is to acknowledge unresolved choices, pick feasible concrete implementations, and mark them in code for later discovery. Therefore do not reopen every OPEN topic as a user question. Record selected provisional choices and proceed within released mathematical/data boundaries. Do not overwrite accepted decisions or bypass V5's mandatory pre-complex-solver research gate.

## 2. Baseline and branch review already performed

| Source | Reviewed state | Consequence |
|---|---|---|
| main `f3946c726e53fa546be1400d80ab717fcb2c3468` | PR #51 merged; forecasting, review corrections and design lab integrated | Work from corrected main; preserve merged modules/regressions |
| forecasting `bed08544e3dc9b00499224806d92dd8f437f0644` | Original PR #49 still open; its content already incorporated through #51 | Do not remerge or restore the older branch; PR state alone is misleading here |
| VP `b82f85f2f7b43f05df5ab0ef033c9bf0e8b28b38` | Documentation only, diverged two commits each way | Retain compatible mode/frozen-input/202 ideas; no hidden OR implementation |
| review fixes `62ff71c61a29ccc40dcd1c8b5fb9e26c0601a194` | Incorporated by main merge f3946c7 | Preserve numerical, evaluation and prototype fixes |
| design-lab branch `2a8898d3d3983ca6744b33356e33dab5b7c4e862` | Original PR #50 open; corrected content already incorporated in main | Preserve corrected main rather than replay old UI files |
| preview branch `81387fe8d7ca97774a61425c97d75a982b1ab1be` | Two commits ahead of main: isolated Vercel prototype setup and narrow V5 exception | No backend/schema/OR changes; do not copy root redirect into OR UI or treat preview as connected acceptance |
| be/ready-1-6 `03406d9d2d16168a09dd12fafcdc79e6bf9e9b99` | Ancestor of main | Do not remerge/reimplement it |
| Six individual be feature branches | Compared with main; individual helper diffs, no additional OR pipeline | Use final merged/refactored main rather than old branch copies |

Main retains V5 authority, BE-01–06, the strict method/mode types, topology filter, daily Decimal ceiling, Fraction floor at S=10000, native-status read gate and history alignment. It now also contains offline forecasting preparation, baseline/fallback, evaluation, immutable handoff and a one-series lot projection. Only process health is exposed as public API; full domain ORM/Alembic schema, publication, shared executor, operational scenarios, network OR engine and generated domain TS remain absent. PP-30 reports 488 API/17 configuration/6 browser tests at its recorded worktree/environment; this update is source review, not a fresh execution of those tests. Earlier 437-test and original forecast-evaluation artifacts remain dated evidence.

The merged forecasting contracts remain experimental and do not supply committed DB `planning_ready`, full operational snapshots, network constraints, real Chronos inference or durable execution. VP's topology reference BD-30 maps to BD-41, preserving main's observability BD-30. Do not change topology or adopt experimental defaults merely because the core is merged.

### 2.1 Repository update notes and document impact

| Observed change since ca5909b | Effect on the OR build |
|---|---|
| Merge PR #51 at f3946c7, containing integration commit 62ff71c | Remove forecast-merge dependency; inventory/forecast modules are existing main code to extend |
| Internal forecast schemas/handoff now on main, byte-identical to reviewed bed0854 versions | Reuse models/validators; no newly finalized public fields or SQL contracts. OR schema and publication work still required |
| Moving-average now computes exact decimal-representation Fraction sum/mean before final float conversion | Preserve regression where constant29 stays29 and genuine above-integer values still ceil upward; no epsilon repair |
| Held-out truth preparation allows mixed basis solely to account for mismatch | Do not relax training proxy authorization or score incompatible target bases; preserve new evaluation tests |
| Existing project_daily and ProjectionLot moved onto main | Refactor/extend compatibly, preserving experimental null-expiry wrapper while applying OR's stricter explicit policy separately |
| Static /design-lab and isolated Three.js exception added; lockfile/UI/Playwright changed | Preserve prototype and existing tests; connected OR UI, proxy/auth and real metrics still need implementation |
| Backend spec/V5 add integration-candidate notes; V5 retains old consolidation/unmerged wording | Treat old implementation-status prose as dated history; actual main/merge state controls what code exists. Requirements/gates still apply |
| Backend checkpoint and BE helpers unchanged; no domain migration or OR implementation | Keep Draft 1 mathematical choices and planned public/persistence contracts; no accepted objective change to reconcile |
| Separate preview branch narrows frontend-hosting pause for a synthetic Vercel preview | Scope exception only; backend/model setup and supplier pauses remain. No deployment or secrets work for this assignment |

Files changed in this package: 01 provenance only; 02 integration design and compatibility tests; 03 build prerequisites, update notes, source links and evidence. Equations, objective defaults, independent oracle expectations and OR-DEC IDs remain unchanged.

### 2.2 Concrete merged-schema handoff

Use existing main `SeriesKey`, `SeriesScope`, `ForecastInput`, `ForecastOutput`, `ForecastSeriesResult`, `ForecastPoint`, `DemandChoice`, `PlanningSeries`, `PlanningDay` and `ForecastHandoff` as the upstream internal vocabulary. `ForecastOutput.ready_for_publication` is not committed publication; result status AVAILABLE, actual provider, required scope, exclusions and nullable quantiles must be retained. Validate imported handoffs with `verify_handoff`; preserve original forecast content hash separately from the new operational hash.

Do not treat `PlanningDay.unrounded_units` float as a newly exact source. OR's decimal boundary records source literal/conversion. Do not multiply already-ceiled `PlanningDay.units` for scenario overrides: recompute from original forecast/choice, apply modifiers, then BE-03 ceiling once into a separate OR target schema. Retain existing handoff reconstruction validation rather than mutating its derived fields. Preserve `project_daily` compatibility; null-expiry inclusion remains its experimental policy while the OR adapter excludes it under OR-DEC-001.

At execution, use current remote refs, not these SHAs as an instruction to reset. Fetch/read without merging; record new main/forecast/VP heads, PR merge status, merge-base, changed schemas/modules and package locks. Reread changed V5/checkpoint content. If equivalent working code landed, integrate and test it rather than duplicate. Produce `docs/optimization/BASELINE-RECONCILIATION.md` listing retained, replaced and adapted components with reasons. Do not silently copy an older branch `BACKEND-SPEC.md` over main.

## 3. Required resulting behavior

The full pipeline is:

1. Obtain a committed complete normalized input package with explicit simulated/live provenance.
2. Freeze seven dated forecast inputs and operational resources/constraints into an immutable scenario with explicit mode, policy, H and source revisions.
3. Calculate the no-new-transfer baseline, dated need and source eligibility.
4. Build one physical feasible region with deterministic loading and local FEFO, donor protection, arrival/expiry, no relay, integer lot conservation and joint handling capacity.
5. Run CLASSICAL_GP and EGP_PI_INSPIRED sequentially with identical operational data, mode and settings.
6. Independently replay, verify and evaluate each method before publishing any vector.
7. Persist method-specific outcomes and a complete/partial comparison; expose saved reads and supported explanations.
8. Create a new scenario after disruption/policy/mode change; preserve old results and label current staleness or historical replay.
9. Record plan review with actor/time/result version and no inventory effect; reset only isolated demo data under a fenced protocol.

Full demo: six beneficiaries plus one or two hubs, two products, seven forecast dates, both explicit modes and both allocation methods. Full first-draft OR functionality must work through actual API/DB/jobs using synthetic complete packages. The baseline core is merged; a separate committed forecast/stock-source journey still needs persistence/read adapters and operational contracts. Label the exact missing capability instead of calling it an unmerged-code blocker.

## 4. Nonnegotiable mathematical requirements

- Never equate shipment or arrival quantity with fulfilled demand. `f` is deterministic dated consumption within W; a late arrival cannot serve yesterday and unmet lost demand is counted once.
- Enforce source-lot debit, destination sublot credit and transit identity; no duplication by receipt, lot, reservation, commitment or expected arrival. Only original free on-hand stock is exportable in the batch. Reject unsupported overlap between quarantined commitments and included local service rather than inventing unmet demand or subtracting stock twice.
- Require each new received sublot to be consumed by H and not expire unused. Incoming totals are bounded by no-action unmet demand within W.
- Hard FEFO is deterministic loading/service min equations, not sorted display or a small cost penalty. Freeze route loading order and explain its feasible-set restriction.
- Sending beneficiaries cover seven-day own need and explicit daily reserves in a separate no-proposed-inbound simulation. Protect hub operational demand/reserves too. Scarcity alone is not infeasibility.
- Demand targets ceil each final scenario date once, then sum. Donation predictions never fund confirmed baseline inventory.
- Keep mode independent from method with no default mode; prove all four combinations.
- Research uses weighted deficit, per-goal W sum, max Z, and active strict AP/RP excess terms; classical has no vulnerability/AP/RP optimization terms.
- RP group mean depends on the current candidate and frozen same-product positive-target membership. Reify true and false branches. Zero targets do not enter denominators; reject unsupported singleton groups.
- Exact fixed-point floor S=10000 affects computation. Store original/exact values, prove all emitted integer activity bounds, and reject unsafe instances before solving.
- Do not introduce a shortage-first pre-objective, substitute a heuristic for research, infer a universal winner from different native objectives, or relabel classical after research failure.

Use the exact equations and provisional values in companion 01, including the excess aggregation and normalizations. No hidden coefficient changes to force the demo. If a counterexample shows a flaw, repair the formulation, document the changed OR-DEC choice, bump affected versions and regenerate independent expected results before proceeding.

## 5. Decision documentation and markers

Create `docs/optimization/DECISION-REGISTER.md` with OR-DEC-001…020 from companion 01. Each entry contains status SELECTED_FOR_DRAFT_1, original OPEN IDs, choice, alternatives, rationale, limitations, affected code/tests/config/migrations, policy/schema version and revisit trigger. Record additional routine decisions as OR-DEC-021 onward without changing old meanings. Do not label old OPEN topics RESOLVED merely because this draft made a provisional choice; use an explicit draft-selected status in documentation.

Adjacent implementation comment example:

```python
# OR-DEC-004 [PROVISIONAL]: load longer-ETA routes first, then FEFO lots.
# See docs/optimization/DECISION-REGISTER.md#or-dec-004.
```

Use equivalent TS/SQL comments, test references and JSON `decision_ids` metadata. Link decision markers to behavioral tests. Add a marker coverage manifest listing affected symbols/files and implement a real check. Ensure serialized scenarios, policies, methodology and results include relevant IDs. Versioned updates create new scenarios and never change old semantics.

## 6. Execution packages and gates

### OR-BUILD-00 Baseline and contracts

Read repository instructions and current V5/backend checkpoint/architecture, ADR 0003/0004, PP-30 and merged forecasting tests. Inventory actual schemas, locks, scripts, DB migrations and shared executor/auth. Inspect current refs without merging/replaying #49/#50. Establish read ports and the explicit SIMULATED input path; resolve source locks for LIVE packages. Preserve integrated forecast numerical/basis regressions and design-lab tests before adding OR behavior.

Deliver: baseline reconciliation; exact internal schema examples; expected errors; OR-DEC register; read-port matrix; retained main helper tests. Record external missing capability as a live integration limitation, not a reason to replace it with guessed SQL or a mock labeled live.

### OR-BUILD-01 Mathematical gate before complex solver code

Create `RESEARCH-MAPPING.md`, `NUMERICAL-PROOF.md`, independent enumerator and exact fixtures. Read actual paper source and check section/equation mappings; list deliberate local deviations. Do not fabricate equation fidelity if source retrieval fails. Prove loading/FEFO, deterministic service, linkage, donor protection, zero/group/equality behavior, coefficient scaling and integer bounds.

Reproduce companion 01's AP and RP ablations and unique six-beneficiary optima with independent enumeration. The planning-task enumeration is useful expected evidence, not the codebase's checker or a CP-SAT result. Test physical interpretations by hand before building the optimizer. Complete V5-A10's local mapping/oracle/encoding prerequisites; if an actual gate cannot be completed, record the precise missing evidence and continue independent schema/persistence work while holding dependent complex solving. Do not call a missing gate passed or reopen already authorized provisional choices as a permission loop.

### OR-BUILD-02 Source adapter, snapshots and policies

Implement strict normalized package/policy/scenario contracts, source checks, precision, canonical hash and replay. Adapt the existing corrected main forecasting core; no branch merge is required. Keep forecast/handoff and operational identities separate. Reuse BE-03, preserve valid unmodified handoff targets, and recompute only from original sources for OR overrides. Test constant29, genuine fraction above29, sparse fallback and source0.2×multiplier2→ceil0.4=1. Preserve scope/coverage/provider/basis/missingness and central/quantile/buffer interpretation. Never generate forecasts implicitly during reads/solves.

Deliver package/scenario validation, exact source fingerprinting, seven dates, explicit mode/H/reserves/capacities, policy version/decision IDs, duplicate/source-unit/cross-org errors and snapshot tamper/replay tests.

### OR-BUILD-03 Independent simulation and verification

Implement solver-free loading, dated lost-sales/FEFO projection, transit/free/blocked reconciliation, donor no-inbound trajectory, capacities and metrics. Extend/refactor main's existing projection through a compatibility wrapper or shared kernel, preserving original tests and explicit old-policy behavior; do not keep two authoritative recurrences or globally prohibit null expiry in the experimental wrapper. Add OR's explicit policy separately. Hand-check cases/conservation and service-withholding manipulation.

Deliver complete checker before candidate publication exists. Make `verify.py` depend on accepted data and pure replay, not CP builder/attachment modules. Independent oracle must still be separate from both. Include allocation linkage and comparison under both modes.

### OR-BUILD-04 Shared physical model and CLASSICAL_GP

After gate prerequisites, build bounded y variables, source-residual packing chains, derived destination sublots, exact daily min/max recurrence, donor protection and shared capacities. Attach classical objective with exact integer coefficient compiler. Validate model, bound search, use status gate, extract safely and verify independently.

Deliver real classical solve; compare tiny feasible sets and optimum to enumeration, test no routes/stock/zero capacity, expiry/ETA/source reuse/protection and distinct invalid hard constraints. Never return a fake success after UNKNOWN or model failure.

### OR-BUILD-05 EGP_PI_INSPIRED

Attach exact weighted floor variables, W/Z, strict two-way AP/RP flags, exact count excess numerators, product aggregation and shared cost/waste terms. Preserve default/diagnostic-ablation distinction. Verify actual auxiliaries/objective against independent evaluation.

Deliver real research solver; threshold/equality/overflow tests, AP/RP decision-changing ablations, six-beneficiary unique solution and common feasibility evidence. The full fixture must pass both modes where input topology permits; add pantry-surplus and harmful-donor cases to distinguish modes.

### OR-BUILD-06 Paired service and explanation

Run both methods sequentially with the same frozen scenario, model constraints, references, package version, settings and limits. Store physical constraint/candidate fingerprints to prove identity. Only objective attachments differ. Compare common evaluation metrics; expose honest trade-offs, worst deficits and distribution as well as totals. Implement OR-DEC-013 plan/site effects and transfer rationale; no numerical per-transfer benefit.

Deliver both-verified, first-failed, second-failed, both-failed, FEASIBLE and zero-transfer cases without substitution; immutable previous outcomes; explicit historical/stale labels. Test real before/after recalculation, not fixed numbers.

### OR-BUILD-07 PostgreSQL persistence and schema

Use actual PostgreSQL with isolated migrations. Implement companion 02's records/transactions or reconcile equivalent landed canonical records. Do not create a live inventory ledger or duplicate shared queue. Enforce immutable payloads/content hashes, org scope, unique idempotency keys, active-job dedup and result/check atomicity. Parent-owned publication only; no child database writes.

Deliver Alembic upgrade/downgrade/upgrade tests, invalid insert/immutability tests, rollback, concurrency, expected revision mismatch, request-key conflict, persisted replay and append-only review with no stock effects. Provide fixture seeding and fenced isolated reset. Never point destructive tests at shared data.

### OR-BUILD-08 Durable execution and failure containment

Implement shared compute control, persisted jobs/attempts, queue admission/expiry, supervisor heartbeat, owner/generation/epoch fencing, terminable method child and manual linked retry. Reuse shared executor/auth if it has landed. Enforce one active/two waiting across registered expensive kinds; 900-second queue wait; 15-second search/25-second method/60-second pair; heartbeat every 5 seconds and unavailable at age≥15; effective resource ceiling 6 CPU equivalents/8 GiB.

Deliver real hung-process/child cleanup tests, DB/lease loss, stale heartbeat, healthy-busy admission, cancel/timeout/worker interruption, partial result retention and late publication rejection. Updating a database timeout row or canceling a Python future alone fails acceptance. Never automatically retry a lost running job. Preserve queued work subject to expiry and explicit reset rules.

### OR-BUILD-09 API, generated contracts and proxy

Implement companion 02's catalog and error semantics: strict mode requests, immutable scenario/policy/package creation, durable 202 submissions, saved job/plan/comparison reads, review, safe methodology and cheap readiness. Complete presenter sessions, backend authorization, origin/CSRF and Next.js proxy where absent. Visitors read only saved synthetic-safe results. Generate OpenAPI/TS and make drift detectable with a real command.

Deliver HTTP lifecycle/security/status tests, no work on GET/probes, idempotency and stale-source handling, generated type compilation and UI client integration. Keep process-health contract unchanged. Mark new route/schema contracts provisional with IDs rather than treating their names as previously implemented.

### OR-BUILD-10 Scripts, journey and final review

Create companion 02's NEW OR scripts with documented arguments/exit codes, reusing actual logic/containment. Preserve the existing `scripts.evaluate_forecasting` entry point and use module-mode CLI invocation. Reproduce corrected evaluation when using it as current evidence; the old committed JSON is historical. Add real contracts/marker checks and fixture outputs. Exercise persisted OR HTTP/UI and separately the committed forecast-source journey. Preserve the simulated design-lab/3D exception without connecting illustrative values to solver-result claims or turning its static preview into live acceptance.

Run relevant quick/full/build/e2e checks, migration/contracts/decision checks, benchmark and independent review. Correct actual failures; do not replace missing gates with no-ops or count skipped tests as passing. Perform isolated repeatable reset-to-finish rehearsals when the connected journey exists; V5's five-rehearsal release requirement is not satisfied by five pure function calls. Record honest partial capability if upstream/paused wider scope prevents whole-product completion.

## 7. Concrete mathematical acceptance values

The fixture files must encode physical source/route/lot data consistent with these mathematical examples; use explicit synthetic provenance.

| Acceptance fixture | Expected result |
|---|---|
| AP isolated oracle: r=(2,3), v=(1.5,1.5), supply=1, default research except ancillary coefficients 0 | Full research unique f=(1,0), J=19/8; AP-removed diagnostic unique f=(0,1), J=2 |
| RP isolated oracle: r=(2,2), v=(1.5,2), supply=1, same isolated settings | Full research unique f=(0,1), J=11/4; RP-removed diagnostic unique f=(1,0), J=21/8 |
| Six-beneficiary/two-product full fixture in companion 01 | Classical both product vectors (1,1,1,1,1,1), J=163/50; research both vectors (2,2,1,1,0,0), J=1393/300; each unique under its own objective |
| Daily lost demand | Initial free stock40, dated demand50 then40, no supply: unmet10 then40, total50 |
| Exact q floor | 1/3→3333, 1/20000→0, 10001/10000→10001 |
| AP equality | q=A unflagged; q=A+1 flagged |
| RP equality | Nq−sum(q)=NT unflagged; NT+1 flagged |
| Forbidden native status | INFEASIBLE/UNKNOWN/MODEL_INVALID: no vector access, no invented plan |
| Worker deadline | Actual child stopped/reaped and publication fenced within whole method/pair boundary; no native-timeout-only pass |

Cost/normalization references, quantized ratios and every source/window/capacity value must match the companion fixture definitions. Do not assert exact vector equality for arbitrary tied optima; verify objective/feasibility equivalence unless uniqueness is independently established.

## 8. Acceptance matrix

| ID | Required evidence | V5 mapping |
|---|---|---|
| OR-A01 | Baseline reconciliation, preserved helpers, explicit actual source capability | A01/A02/A04/A07 |
| OR-A02 | Strict versioned schemas, daily rounding, canonical hash, tamper/replay, current/historical distinctions and scope | A07/A08 |
| OR-A03 | Independent lot/transit/conservation/lost-sales/expiry/FEFO/donor/capacity checks in both modes | A09 |
| OR-A04 | Checked research mapping, bounds/proofs, independent enumeration and decision-changing AP/RP ablations | A10 |
| OR-A05 | Both real methods, identical operational model fingerprints, full scarce fixture and common trade-off metrics | A11/A16 |
| OR-A06 | Native status extraction guard, invalid candidate rejection, atomic result publication and independent method failures | A07/A11 |
| OR-A07 | Actual PostgreSQL integrity/migrations/rollback/idempotency/races and no stock effects | A03/A07/A08 |
| OR-A08 | Real queue/heartbeat/lease/cancel/termination/loss/retry/partial-state behavior under accepted ceilings | A12 |
| OR-A09 | Authorized API/proxy/session/CSRF, complete errors, generated types/drift, no compute on GET, saved reads during outage | A13 |
| OR-A10 | Executable CLI contracts, searchable decision comments/config/test coverage, reproducible evidence | A10/A12/A18 |
| OR-A11 | Persisted synthetic full OR journey, new-scenario disruption, review, safe reset, measured timings | A15/A17/A18, bounded OR scope |
| OR-A12 | Actual committed baseline forecasting/stock source → scenario → paired OR journey | A04/A07–A09/A15; separate upstream integration gate |

Every row ends PASS, FAIL or UNVERIFIED with exact code/input/policy/settings/environment and artifact reference. An unavailable adapter can pass an explicit failure-path test but cannot pass OR-A12. Forecast fallback evidence does not qualify Chronos. OR functionality does not complete supplier scope or whole-product release.

## 9. Commands and operational proof

Preserve existing `npm run check`, `npm run test:api`, `npm run test:config`, `npm run build` and `npm run test:e2e`, adding relevant coverage. Implement and run real new commands from companion 02: strict input validation, enumerative oracle, full independent verification, actual bounded solve/pair, simulated seeding, shared supervisor, benchmark, OpenAPI generation/drift and decision-marker checks.

Do not broaden heavy hosted/model setup. Use the repository's locked Python 3.12 environment and OR-Tools dependency; current pyproject permits `ortools>=9.12,<10`, while the actual lock selects the reproducible version. Verify used Python API methods against that lock. Add no unnecessary solver, queue vendor or second backend. Use PostgreSQL tests for PostgreSQL claims, actual child processes for containment claims and the real app/database for browser claims.

Performance targets remain saved reads under one second and seeded per-method solves under five seconds. Accepted hard deadlines apply even when targets are missed. Log a disclosed miss with hardware/scope/run-count/median/maximum; do not silently reduce the required population or weaken correctness. Effective resource controls need measured evidence, not configuration text alone.

## 10. Documentation maintenance and handoff

Update V5's implementation/evidence tables and relevant OPEN states accurately, preserving explicit pauses. Update backend spec/checkpoint with selected provisional contracts and IDs, research ADR/mapping/proof, architecture projection ownership, board/task packets, invariants/acceptance matrix, migration and generated-contract instructions, and actual demo/release workflow. Keep old records historical rather than rewriting evidence. Do not create competing copies of authoritative source requirements.

The final implementation handoff must state:

- What actually runs, including both methods/modes, input provenance and persistence/API/job capabilities.
- Exact SHAs, test commands and outcomes, independent mathematical/physical evidence and fixture optimum counts.
- Real runtime measurements and termination/queue/concurrency evidence.
- Which provisional choices were implemented, where their comments/registry/tests live and what limits they impose.
- Whether actual forecast/stock adapters and the live user journey passed; name precise missing upstream contracts/capabilities if not.
- Remaining paused supplier/model work, unsupported scope and release criteria without describing them as completed.

Do not claim whole-product V5 completion for a standalone OR demonstration. Forecasting core is integrated; the pending work is committed source/publication adapters and operational integration. Do not stop independent OR work because Chronos is paused or those live contracts remain absent. Complete the explicit real simulated workflow and record the remaining live boundary precisely.

## 11. Reviewed source links

- [V5 at refreshed main](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/pantrypulse/SPEC-V5.md)
- [Backend specification](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/pantrypulse/BACKEND-SPEC.md)
- [Backend checkpoint](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/pantrypulse/BACKEND-DESIGN-CHECKPOINT.md)
- [Research architecture](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/architecture/0001-v4-research-first.md)
- [Merged integration PR #51](https://github.com/gbw30/PantryPulse/pull/51)
- [Current merged forecasting handoff](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/apps/api/app/services/forecasting/handoff.py)
- [PP-30 fixes and recorded evidence](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/pantrypulse/tasks/PP-30-pr-review-fixes.md)
- [Design-lab prototype exception](https://github.com/gbw30/PantryPulse/blob/f3946c726e53fa546be1400d80ab717fcb2c3468/docs/architecture/0004-design-lab-3d-exception.md)
- [VP versus refreshed main](https://github.com/gbw30/PantryPulse/compare/f3946c726e53fa546be1400d80ab717fcb2c3468...b82f85f2f7b43f05df5ab0ef033c9bf0e8b28b38)
- [Separate prototype-preview V5 exception](https://github.com/gbw30/PantryPulse/blob/81387fe8d7ca97774a61425c97d75a982b1ab1be/docs/pantrypulse/SPEC-V5.md)

These are review provenance, not an instruction to reset to old refs. Fetch and reconcile again before applying code changes.
