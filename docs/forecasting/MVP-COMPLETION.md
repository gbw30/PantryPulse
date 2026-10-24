# Work remaining for a complete PantryPulse MVP

Updated: October 24, 2026 (America/New_York).

The next useful milestone is a live baseline forecasting slice: approved history
contracts → PostgreSQL history → durable forecast job → committed results → saved
API reads. Alongside that work, complete the independent mathematical review needed
before implementing either complex allocation method. The dashboard and comparison
workflow depend on those foundations.

This is a completion roadmap, not a declaration that the steps below are authorized
or implemented. Ownership names describe repository responsibilities, not assignments
to newly created agents. Numbered steps are dependency order, not time estimates.

## 1. Resolve dependent contracts and reconcile standards

**Owner:** lead with forecasting, data and solver owners. **Status:** required decisions open.

- Finalize the dependent history, forecast, scenario, job and wire contracts under
  the existing OPEN IDs. Keep required/optional/excluded scope explicit.
- Confirm numeric precision/bounds, site-local dates, coverage-backed donation zeros,
  revision visibility, proxy eligibility, sparse thresholds and buffer policy.
- Define versioned input/output examples, error codes, canonical serialization and
  what makes a result reusable or a plan stale. Retain exact source content/revisions.
- Reconcile `ACCEPTANCE-MATRIX.md`, `DEMO.md`, `RELEASE-CHECKLIST.md`, the delivery board
  and generated-contract workflow with V4 and BD-01–40. Resolve inherited conflicts
  rather than silently following three-site or older model/comparator examples.

**Exit evidence:** recorded decisions in the existing checkpoint/specification,
reviewed payload examples and an updated acceptance ledger. Experimental internal
Pydantic schemas are not sufficient evidence that public contracts are frozen.

See [decision dependencies](DECISIONS-AND-ENHANCEMENTS.md#decisions-required-before-dependent-work).

## 2. Implement PostgreSQL history and operational integrity

**Owner:** data/backend. **Depends on:** the relevant step 1 schema/transaction decisions.

- Add scoped organizations, sites, products, versioned demand, complete donation
  receipts/lines and reporting coverage. Database constraints must enforce ownership,
  uniqueness, units and quantity consistency alongside application validation.
- Implement CSV/history imports with precise row errors and counts. Accept valid
  demand rows individually and each complete valid receipt atomically. Historical
  imports must never post current stock.
- Add versioned lots, eligible/held/unknown states, confirmed arrivals, inventory
  adjustments, ledger and audit records. Explicit receipt posting must create linked
  stock/ledger/audit changes exactly once.
- Append corrections. Correcting posted stock needs a separate linked audited
  adjustment; saved forecast/scenario history must remain unchanged.
- Seed the expanded fictional network with operational lots, routes, capacities,
  prepared vulnerability attributes and policies. The current forecasting fixture
  supplies histories, not a complete allocation/demo dataset.

**Exit evidence:** isolated PostgreSQL upgrade/downgrade and integrity tests;
rollback, duplicate-posting, competing-update and stale-version tests; scoped reset
preserves non-demo data; source revisions reproduce the core's prepared inputs.
SQLite or mocked transactions do not satisfy this gate. Relevant targets: F-04–06.

## 3. Add durable computation and atomic forecast publication

**Owner:** backend/runtime with forecasting. **Depends on:** history, snapshot, job and lease contracts.

- Persist input snapshots, jobs and attempts before returning acceptance. Call the
  existing pure forecasting service inside controlled execution. Retain per-series
  diagnostics, actual provider/checkpoint, fallback, warnings and original timestamps.
- Atomically commit outcomes/points and the final readiness state. The current
  `ready_for_publication` field is only a computational completeness check. Required
  unavailable series must block persisted planning readiness.
- Implement exact-result reuse and explicit forced refresh. Enforce concurrent
  admission/deduplication in PostgreSQL; a pure hash comparison is not race protection.
- Reject stale-attempt publication. Lost running workers leave interrupted/failed
  attempts; manual retry links a new attempt to the saved inputs. Preserve queued work
  subject to the defined expiry policy. Provider fallback is distinct from job retry.
- Keep saved reads and polling responsive while expensive computation runs.

The accepted runtime requirements are mandatory:

| Rule | Acceptance check |
|---|---|
| One active expensive operation; at most two waiting | Concurrent forecasting/allocation submissions share one slot and bounded durable queue |
| Queue wait at most 900 seconds | Expiry is persisted and enforced, including after downtime |
| Heartbeat every 5 seconds; unavailable after 15 seconds | Distinguish healthy busy from unavailable; new work receives structured 503 when unavailable |
| Forecast operation at most 300 seconds | One budget across preparation, every series/provider, cleanup, validation and publication |
| Stop primary by 270 seconds when fallback is allowed | Actually terminate it and use only the remaining shared budget; no extra inference allowance |
| Configurable worker ceilings: 6 CPU equivalents and 8 GiB RAM | Record effective process/container limits and resource measurements |
| Solver search/method/comparison limits: 15/25/60 seconds | Sequential paired methods share one comparison operation and retain truthful outcomes |

**Exit evidence:** real PostgreSQL/API job, reuse/refresh, publication rollback,
stale-worker, queue-full/expiry, interrupted-job/manual-retry and actual termination
tests. Cancelling a future or changing a DB status alone does not stop computation.
Relevant targets: F-08, F-13–14, F-19–22.

## 4. Expose authorized APIs and connect saved reads

**Owner:** backend/frontend. **Depends on:** approved public contracts and persisted results.

- Add presenter-authorized mutation/submission routes and public synthetic saved-data
  reads. Finalize authentication/session expiry, CSRF and proxy credential forwarding.
  FastAPI must enforce authorization even behind the thin same-origin Next.js proxy.
- Provide forecast submission/status/points, site/lot/shortage reads, history import,
  scenario creation, allocation/comparison, review and reset according to the finalized
  route catalog. Candidate route names remain proposals until OPEN-29 is resolved.
- Generate OpenAPI/TypeScript from validated Python schemas and add a drift check.
  The browser must not duplicate forecasts, projections, objectives or inventory logic.
- Use the structured error envelope and defined status distinctions. Return `202`
  for durable acceptance, never as proof of a successful forecast or plan.
- Separate process liveness, API/database readiness, compute availability and provider
  qualification. Probes/GET requests must not load models, forecast, solve or create jobs.
- Add correlated, redacted logs and transactional audit events for mutations,
  reviews and reset. Diagnostic logs cannot replace the stock ledger.

**Exit evidence:** backend authorization/CSRF/proxy tests, generated-contract checks,
saved reads during compute failure, no-inference-on-GET tests and redaction tests.
Relevant targets: F-18, F-22 and backend specification §§8–9.

## 5. Freeze complete scenarios and integrate dated projection

**Owner:** data/inventory/forecasting. **Depends on:** persisted forecasts and operational records.

- Extend the existing forecast-only handoff into a complete immutable, versioned JSONB
  scenario package. Pin selected forecasts, eligible lot versions, confirmed supply,
  routes/capacities, scope, attributes, policies, assumptions and source references.
- New operational inputs require a new scenario. Define staleness/conflict behavior;
  replay must not silently read current inventory or the latest forecast.
- Integrate daily projection with the agreed event order, expiry/missing-expiry rules,
  confirmed/received reconciliation and donor protection. Later arrivals cannot repair
  earlier lost demand. Exclude unknown eligibility and double-counted receipts/arrivals.
- Preserve per-day ceiling, units, source basis/proxy warnings, explicit conservative
  quantile/buffer choices and declared partial scope. Recalculate comparison groups
  and denominators from that same scope.
- Keep donation forecasts charted and uncertain. Any conditional supply scenario needs
  explicit eligibility, arrival, shelf-life and event-reconciliation assumptions;
  do not adopt automatic forecast-minus-confirmed subtraction.

**Exit evidence:** replay after source changes, identical forecast/operational hashes,
lot/expiry/arrival conservation, no duplicated supply, explicit partial-plan tests and
unchanged old scenarios. Relevant targets: F-15–17 and INV-06–09/15/19/21.

## 6. Pass the research gate and implement both real allocation methods

**Owner:** solver/research plus an independent verifier. **Prerequisite before complex
solver code:** the mathematical gate in [ADR 0001](../architecture/0001-v4-research-first.md).
This review can progress alongside the baseline integration above.

- Map the full paper to PantryPulse's bounded adaptation. Finalize objective,
  category/group, weight, penalty and numerical policies under OPEN-21–25.
- Validate hand calculations and independent exhaustive tiny-instance oracles.
  Prove int64 bounds and near-threshold effects for the accepted 10,000 fixed-point scale.
- Implement a shared feasible region: lot/FEFO, expiry/ETA/use, product units,
  donor local demand/reserves, receiving/shared capacity, no self-transfer,
  no overdelivery and no same-batch forwarding of inbound stock.
- Implement `CLASSICAL_GP` and `EGP_PI_INSPIRED` with active AP/RP reification,
  soft excess-share penalties and W/Z objective decomposition. Include only
  positive-demand beneficiaries in same-product RP groups; preserve zero-target semantics.
- Independently verify vectors and metrics. Both methods consume identical frozen
  targets/constraints/settings. Respect native statuses, objective bounds/gaps and
  method failures; never substitute classical output under the research label.

**Exit evidence:** TEST-EGP-01–07, threshold/equality/group cases, AP/RP ablations,
FEFO/conservation checks, independent feasibility for both methods, and an
interpretable changed allocation on the expanded seed. A working classical solver
alone does not complete the MVP's primary comparison. Relevant targets: F-23–24.

## 7. Build the actual presenter and visitor workflow

**Owner:** frontend/product, using the existing Tailwind/shadcn/Radix, Recharts,
Motion and Lucide stack. **Depends on:** stable saved-result APIs and actual computed data.

- Replace the development landing page with the network/site inventory view,
  product selector, demand/donation forecasts, first projected deficit and methodology.
- Add import/correction feedback, explicit proxy/scope/buffer choices, durable job
  status, manual retry and presenter-only mutation controls.
- Show paired method results: transfers, residual unmet demand, per-beneficiary
  fulfillment/deprivation, attributes/thresholds, constraints and objective explanation.
  Keep units, window and input identity comparable.
- Support disruption → new frozen scenario → recomputation, preserve the earlier
  comparison and prevent stale responses from overwriting newer user intent.
- Implement “Mark reviewed — simulation” and protected scoped reset. Review must
  never reserve, dispatch, approve a purchase or change physical stock.
- Cover loading, empty, insufficient-data, provider-fallback, unavailable-method,
  error and stale states. Show actual providers, original generation times and
  simulation/proxy labels. Do not animate a successful allocation before one exists.
- Verify keyboard/focus, chart alternatives, contrast, reduced motion and responsive
  layouts against the documented art direction and human visual acceptance.

**Exit evidence:** live desktop/mobile/reduced-motion screenshots and browser tests
asserting changed forecasts/shortages/plans, rather than headings alone. Use at least
six beneficiaries plus hub(s), two products and meaningful research comparison groups.

## 8. Close paused scope and qualify optional-provider claims

**Supplier proposals are accepted scope with planning paused**, not an optional
feature silently removed from the MVP. Complete accepted-scope delivery needs either
explicit resumption/decisions and implementation, or an explicit scope amendment.
Resolve OPEN-03/26–28 before dependent basket logic. Then implement seeded/manual
offers, arrival-aware coverage, coordinated simulated budget, alternatives and uncovered
need; proposed goods stay outside confirmed resources and stock. No real order/payment.

**Chronos qualification is a separate gate.** After setup is explicitly resumed,
verify the pinned package/checkpoint/revision, native gap handling, stable series/date
mapping, actual quantiles, real inference/failure boundaries and comparative evaluation.
Measure cold load, warm inference and resources separately from saved-result reuse.
BD-33 permits the live baseline/core demonstration with unverified Chronos disclosed;
it does not turn the unavailable adapter or mocks into successful Chronos evidence.

**Hosting setup remains paused.** Document local release operation now; resume hosting
and prepare a concrete reviewable release before any separately authorized deployment.
This documentation request does not resume any paused work.

## 9. Make release gates executable and demonstrate completion

**Owner:** lead/verifier with all workstreams. **Depends on:** the integrated candidate above.

Current concrete gaps include `test:unit` and `contracts:check` referenced by the full
gate but absent from `apps/web/package.json`, the missing PostgreSQL migration test
referenced by that gate, a CI workflow stored as a `.template`, and Playwright coverage
limited to the scaffold landing page. Implement the checks before claiming a green
full/release gate. Keep required failures blocking; do not replace them with no-ops.
Reconcile the CI template's older Node version, nested lockfile/install paths and
browser/API environment wiring with the current pinned root workspace and proxy design.

- Run frozen installation and relevant runtime checks, quick/full/E2E suites, real
  isolated PostgreSQL integrity/concurrency tests and independent research verification.
- Record source/config/input identities, environment/package versions, exact commands,
  timestamps, PASS/FAIL/UNVERIFIED, artifact locations and independent review.
- Measure saved-read <1-second and seeded per-method <5-second responsiveness targets
  on the expanded scope. BD-39 allows a disclosed target miss only when correctness,
  hard limits, failure handling and the research gate pass; the missed target stays unmet.
- Run the complete journey: import/saved history → durable baseline forecast → frozen
  shortage → both allocations → disruption → new scenario/replan → review → reset.
  Include a provider-failure/fallback case and a method-unavailable/interruption case.
- Complete five clean reset-to-finish rehearsals, including a cold/failure case,
  and verify local fallback/backup recording. After hosting resumes, smoke-test the
  actual authorized release URLs and record the deployed version.
- Update README, acceptance ledger, limits, provenance, licenses/attribution and demo
  instructions. Verify organizer requirements before preparing/submitting event assets.

**Completion means:** every required core/research/integrity workflow has recorded
live evidence; accepted paused scope is implemented or explicitly amended; provider
claims match qualification; and the presenter can repeat the full flow without hidden
intervention. Offline forecast tests and a polished static dashboard cannot establish
that result.
