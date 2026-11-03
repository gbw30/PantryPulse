# Parallel development backlog — PantryPulse V5

## Current audit and status — October 24, 2026

Use the [branch/issue audit](BRANCH-STATUS-AUDIT-2026-10-24.md) for current readiness and implementation. The package catalog below preserves its original scope and dependency history; its original “ready/blocked” descriptions are not a claim that delivered code is still missing.

- **Delivered on main:** #13–18 and #20 are closed; existing #1–6 remain closed.
- **Implemented on unmerged branches:** VP #8/#19/#21/#23 and OR #10/#24–28/#31/#33 remain open for review/integration.
- **New integration blockers:** [#67](https://github.com/gbw30/PantryPulse/issues/67) converges database/audit/worker histories; [#68](https://github.com/gbw30/PantryPulse/issues/68) reconciles expiry/lot/event semantics.
- **Next bounded UI work:** existing #59–61, then #62. Do not create duplicate explanation/mobile tickets.
- **Committed-source work:** #22/#29/#64–66 remains blocked; VP storage does not supply OR read adapters or committed forecast publication.
- **Incomplete quality wiring:** #41/#63 must repair committed full-gate references and activate an actual workflow.
- **Deferred roadmap coverage:** #69 operations/reservations/completion; #70 calibrated/evaluated forecast improvements; #71 roles; #72 research extensions; #73 richer routing. No P1 work is resumed by tracking it.
- **Paused:** supplier #45 and actual Chronos #46 retain their pauses.

All 59 pre-existing issues were reviewed against committed code. Fifty-three received current status/evidence blocks; seven new issues extend the backlog to 66 issues (13 closed, 53 open). Fresh focused verification passed 1,072 cases; browser/process/hosted acceptance is separately bounded in the report.

## Original package catalog and dependency history

Prepared October 24, 2026 (America/New_York). Source checkout: `04df41ced650896bd4f4a4cd10de1354b406d216`. V5 is authoritative. The newer local Worker and Job Queue Build Specification v0.1 is a technical proposal; it does not silently resolve OPEN decisions. Existing GitHub issues #1–6 are closed and their helpers are reused, not duplicated. This backlog creates work items, not implementation-completion claims or permission to resume paused work.

## Issue index and development prerequisites

GitHub tracking issue: [#48](https://github.com/gbw30/PantryPulse/issues/48). The original planning pass created 40 work issues with scope, acceptance criteria, source and dependency links. The later audit updated issue status and added #67–73; use the audit matrix for current state.

| Item | Development prerequisites | Additional integration/acceptance dependencies |
|---|---|---|
| [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8) — Freeze operational identity, history, receipt and ledger contracts | None | See item acceptance |
| [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9) — Review forecasting branch and freeze forecast, fallback and reuse contracts | None | See item acceptance |
| [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10) — Pass independent mathematical specification and enumeration gate | None | See item acceptance |
| [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11) — Freeze operational scenario, FEFO and shared feasibility contracts | [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8) | See item acceptance |
| [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12) — Specify presenter access, public API conventions and job integration contracts | None | [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11) |
| [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13) — Implement pure job state, admission, deadline and handler contracts | None | See item acceptance |
| [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14) — Build durable queue schema and transactional admission repository | [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13) | See item acceptance |
| [WQ-03 #16](https://github.com/gbw30/PantryPulse/issues/16) — Implement supervisor ownership, heartbeat, claiming and crash recovery | [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13) | [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14), [WQ-04 #15](https://github.com/gbw30/PantryPulse/issues/15) |
| [WQ-04 #15](https://github.com/gbw30/PantryPulse/issues/15) — Build controlled process driver with actual deadline and descendant cleanup | [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13) | See item acceptance |
| [WQ-05 #17](https://github.com/gbw30/PantryPulse/issues/17) — Implement fenced atomic result publication and uncertain-commit recovery | [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14) | See item acceptance |
| [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18) — Verify durable worker vertical slice on isolated PostgreSQL | [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14), [WQ-03 #16](https://github.com/gbw30/PantryPulse/issues/16), [WQ-04 #15](https://github.com/gbw30/PantryPulse/issues/15), [WQ-05 #17](https://github.com/gbw30/PantryPulse/issues/17) | See item acceptance |
| [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19) — Implement operational database models and initial history/ledger migrations | [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8) | See item acceptance |
| [PP-36 #20](https://github.com/gbw30/PantryPulse/issues/20) — Integrate reviewed baseline forecasting core and safe fallback boundary | [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9) | See item acceptance |
| [PP-37 #21](https://github.com/gbw30/PantryPulse/issues/21) — Implement audited stock posting, adjustments and confirmed-supply reconciliation | [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19) | See item acceptance |
| [PP-38 #22](https://github.com/gbw30/PantryPulse/issues/22) — Implement revision-aware demand and donation history imports | [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9) | See item acceptance |
| [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23) — Implement dated FEFO inventory and shortage projection | [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11) | See item acceptance |
| [PP-40 #24](https://github.com/gbw30/PantryPulse/issues/24) — Implement common lot-aware feasible region for both allocation methods | [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11) | See item acceptance |
| [PP-41 #25](https://github.com/gbw30/PantryPulse/issues/25) — Build independent allocation feasibility and replay verifier | [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11) | See item acceptance |
| [PP-42 #26](https://github.com/gbw30/PantryPulse/issues/26) — Implement immutable research policy and independent AP/RP metrics | [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10) | See item acceptance |
| [PP-43 #27](https://github.com/gbw30/PantryPulse/issues/27) — Implement CLASSICAL_GP with the shared operational constraints | [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-40 #24](https://github.com/gbw30/PantryPulse/issues/24) | See item acceptance |
| [PP-44 #28](https://github.com/gbw30/PantryPulse/issues/28) — Implement EGP_PI_INSPIRED with active AP/RP goals and ablations | [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-40 #24](https://github.com/gbw30/PantryPulse/issues/24), [PP-42 #26](https://github.com/gbw30/PantryPulse/issues/26) | See item acceptance |
| [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29) — Persist forecasts and integrate bounded forecast worker/publication | [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-36 #20](https://github.com/gbw30/PantryPulse/issues/20), [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12) | See item acceptance |
| [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30) — Persist frozen operational scenarios, policies and per-method results | [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10) | [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29) |
| [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31) — Integrate sequential allocation/comparison jobs and checked publication | [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-41 #25](https://github.com/gbw30/PantryPulse/issues/25), [PP-42 #26](https://github.com/gbw30/PantryPulse/issues/26), [PP-43 #27](https://github.com/gbw30/PantryPulse/issues/27), [PP-44 #28](https://github.com/gbw30/PantryPulse/issues/28), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12) | See item acceptance |
| [PP-48 #32](https://github.com/gbw30/PantryPulse/issues/32) — Expose saved domain reads and generated API/TypeScript contracts | [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12), [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31) | See item acceptance |
| [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33) — Implement presenter authorization and thin same-origin Next.js proxy | [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12) | See item acceptance |
| [PP-50 #34](https://github.com/gbw30/PantryPulse/issues/34) — Expose authorized submissions, scenario changes and job controls | [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31) | See item acceptance |
| [PP-51 #39](https://github.com/gbw30/PantryPulse/issues/39) — Build deterministic V5 demo seed and protected isolated reset | [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-37 #21](https://github.com/gbw30/PantryPulse/issues/21), [PP-38 #22](https://github.com/gbw30/PantryPulse/issues/22), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-55 #38](https://github.com/gbw30/PantryPulse/issues/38) | See item acceptance |
| [PP-52 #35](https://github.com/gbw30/PantryPulse/issues/35) — Build accessible product shell and explicit fixture-based UI states | None | See item acceptance |
| [PP-53 #36](https://github.com/gbw30/PantryPulse/issues/36) — Connect overview, site detail and forecast/shortage explorer | [PP-48 #32](https://github.com/gbw30/PantryPulse/issues/32), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-52 #35](https://github.com/gbw30/PantryPulse/issues/35) | See item acceptance |
| [PP-54 #37](https://github.com/gbw30/PantryPulse/issues/37) — Connect paired comparison, scenario editing, explanations and review | [PP-48 #32](https://github.com/gbw30/PantryPulse/issues/32), [PP-50 #34](https://github.com/gbw30/PantryPulse/issues/34), [PP-52 #35](https://github.com/gbw30/PantryPulse/issues/35) | See item acceptance |
| [PP-55 #38](https://github.com/gbw30/PantryPulse/issues/38) — Qualify dataset sources and design representative deterministic fixtures | None | See item acceptance |
| [PP-56 #40](https://github.com/gbw30/PantryPulse/issues/40) — Implement chronological forecast evaluation and representative benchmark reports | [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-36 #20](https://github.com/gbw30/PantryPulse/issues/20), [PP-55 #38](https://github.com/gbw30/PantryPulse/issues/38) | See item acceptance |
| [PP-57 #41](https://github.com/gbw30/PantryPulse/issues/41) — Activate meaningful CI and complete migration/contract/test gates | None | See item acceptance |
| [PP-58 #42](https://github.com/gbw30/PantryPulse/issues/42) — Verify real judge journey, research comparison and adversarial failures | [PP-51 #39](https://github.com/gbw30/PantryPulse/issues/39), [PP-53 #36](https://github.com/gbw30/PantryPulse/issues/36), [PP-54 #37](https://github.com/gbw30/PantryPulse/issues/37), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31), [PP-57 #41](https://github.com/gbw30/PantryPulse/issues/41) | See item acceptance |
| [PP-59 #43](https://github.com/gbw30/PantryPulse/issues/43) — Complete rendered accessibility, responsive and visual acceptance | [PP-53 #36](https://github.com/gbw30/PantryPulse/issues/36), [PP-54 #37](https://github.com/gbw30/PantryPulse/issues/37) | See item acceptance |
| [PP-60 #44](https://github.com/gbw30/PantryPulse/issues/44) — Verify worker readiness, redacted observability and effective resource limits | [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12) | See item acceptance |
| [PP-61 #45](https://github.com/gbw30/PantryPulse/issues/45) — Resolve and implement simulated supplier proposal scope when resumed | [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33) | See item acceptance |
| [PP-62 #46](https://github.com/gbw30/PantryPulse/issues/46) — Separately qualify actual pinned Chronos inference when resumed | [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-56 #40](https://github.com/gbw30/PantryPulse/issues/40), [PP-60 #44](https://github.com/gbw30/PantryPulse/issues/44) | See item acceptance |
| [PP-63 #47](https://github.com/gbw30/PantryPulse/issues/47) — Prepare release evidence, authorized hosting and five demo rehearsals | [PP-58 #42](https://github.com/gbw30/PantryPulse/issues/42), [PP-59 #43](https://github.com/gbw30/PantryPulse/issues/43), [PP-60 #44](https://github.com/gbw30/PantryPulse/issues/44), [PP-56 #40](https://github.com/gbw30/PantryPulse/issues/40), [PP-61 #45](https://github.com/gbw30/PantryPulse/issues/45) | See item acceptance |

## Start in parallel

- **PP-30: Freeze operational identity, history, receipt and ledger contracts.** Lane: Lead / domain contracts.
- **PP-31: Review forecasting branch and freeze forecast, fallback and reuse contracts.** Lane: Forecast / lead integration.
- **PP-32: Pass independent mathematical specification and enumeration gate.** Lane: Research / mathematics.
- **PP-34: Specify presenter access, public API conventions and job integration contracts.** Lane: Lead / API security. Design now; acceptance also needs PP-30, PP-31, PP-32, PP-33.
- **WQ-01: Implement pure job state, admission, deadline and handler contracts.** Lane: Worker / pure core.
- **PP-52: Build accessible product shell and explicit fixture-based UI states.** Lane: Frontend / design system.
- **PP-55: Qualify dataset sources and design representative deterministic fixtures.** Lane: Data / research.
- **PP-57: Activate meaningful CI and complete migration/contract/test gates.** Lane: Lead / quality infrastructure.

## Coordination

Use four writing lanes at most: lead/API/persistence, worker/forecast, solver/research, frontend. Data qualification and independent reviews can run separately if people are available. Ready items are independent candidates, not an instruction to start eight writers. Lead serializes migrations, generated contracts, shared schemas/config and lockfiles. Existing worktrees must be checked for current ownership before assignment; this task does not modify them. Produce bounded task packets at assignment with exact base SHA, allowed paths, accepted contract versions and acceptance commands.

Development prerequisites mean the reviewed artifact must exist before dependent production implementation starts. Explicit integration dependencies permit earlier isolated tests/fakes only; they must pass before the issue is complete. Referenced decisions require review, not invented defaults. Follow linked issue acceptance rather than treating a closed checkbox as proof of integration.

Supplier work, actual Chronos setup and hosting remain conditional/paused as recorded in their issues. Baseline core readiness and actual Chronos qualification are separate; supplier scope still needs completion or an explicit amendment before full accepted-scope release.

## Itemized work packages

# [PP-30] Freeze operational identity, history, receipt and ledger contracts

GitHub issue: [#8](https://github.com/gbw30/PantryPulse/issues/8).

Suggested lane: Lead / domain contracts

Development prerequisites: None.

## Work

- Resolve OPEN-04–11: site/product/donor ownership, base units, quantity bounds, operational timezone/day boundaries, expiry/null-expiry, authoritative revisions and donation-reporting coverage.
- Specify complete receipt revisions, exactly-once posting/correction/reversal, consumed-stock cases, ledger/version/idempotency rules and expected-supply reconciliation. Explicitly decide first-release physical-count scope.
- Publish reviewed schemas, worked valid/invalid examples and transaction sequences; propose unresolved values for review rather than adopting historical examples.

## Acceptance

- [ ] Requested = fulfilled + unmet when all observed; missing/null/zero remain distinct; a donor differs from a receiving site.
- [ ] Historical import cannot post stock; receipt posting cannot count supply as both inbound and on-hand.
- [ ] Record accepted decisions, unresolved blockers and the exact schema version before downstream persistence.

Sources: V5 §§5,19; OPEN-04–11; V5-A02/A03.

---

# [PP-31] Review forecasting branch and freeze forecast, fallback and reuse contracts

GitHub issue: [#9](https://github.com/gbw30/PantryPulse/issues/9).

Suggested lane: Forecast / lead integration

Development prerequisites: None.

## Work

- Review origin/forecasting at bed08544e3dc9b00499224806d92dd8f437f0644 against current main; inventory reusable modules, package compatibility and tests without an automatic merge.
- Resolve OPEN-12–18: required series, numerical bridge to exact quantities, minimum history/sparse behavior, proxy opt-ins, invalid-output rules, conservative buffer, reuse/deduplication and representative evaluation policy.
- Freeze immutable forecast input/output and publication semantics; distinguish computational completeness from committed planning readiness. Preserve unsupported Chronos as unavailable.

## Acceptance

- [ ] Record reviewed diff/base and which experimental rules were accepted, rejected or remain open.
- [ ] Cover seven local forecast dates, all required demand/donation series, missingness, classified fallback, point/mean/median and null quantiles.
- [ ] Neither branch code nor the seasonally favorable synthetic results count as merged/live or real-world qualification.

Sources: V5 §§3.2,6–7,17; OPEN-12–18/36; V5-A04–07.

---

# [PP-32] Pass independent mathematical specification and enumeration gate

GitHub issue: [#10](https://github.com/gbw30/PantryPulse/issues/10).

Suggested lane: Research / mathematics

Development prerequisites: None.

## Work

- Map the paper to the bounded EGP_PI_INSPIRED adaptation; record full-text equation evidence and explicit departures. If full text is unavailable, keep that gate unverified.
- Freeze conventional and research objectives, AP/RP thresholds/groups/excess aggregation, W/Z blend, cost/waste normalization, coefficient bounds and immutable policy schema.
- Independently hand-calculate and enumerate tiny instances, including AP-only/RP-only ablations, both flag directions, equality, zero-target and singleton-group behavior.
- Prove fixed-point scale 10,000 bounds for all products/sums and CP-SAT int64 limits; distinguish exact ratios from quantized decisions.

## Acceptance

- [ ] TEST-EGP-01–05 have independently derived expected values and traceable evidence before complex solver implementation.
- [ ] At least two documented simulated institution attributes in [0,1]; normalized nonnegative coefficients and no unreviewed defaults.
- [ ] Demonstrate AP and RP can change an optimum without mistaking alternative optimal ties for a policy effect.

Sources: V5 §10; OPEN-23–25; V5-A10; ADR 0001 research gate.

---

# [PP-33] Freeze operational scenario, FEFO and shared feasibility contracts

GitHub issue: [#11](https://github.com/gbw30/PantryPulse/issues/11).

Suggested lane: Inventory / solver contracts

Development prerequisites: [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8).

## Work

- Finalize OPEN-19–22: fully frozen scenario package/hash, exclusions, staleness/replay, event order, dispatch/use/expiry dates, planning window and donor protection.
- Specify hard FEFO among interchangeable eligible lots, documented exclusions, route ETA/cost, receiving/shared handling capacities and product coefficients.
- Require explicit HUB_ONLY or HUB_AND_PANTRY without a default; no relay of inbound stock; separate physical units from handling units.

## Acceptance

- [ ] Provide small feasible/infeasible examples for both modes, expiry equality, late arrival, protected local service, exact capacity and no-relay.
- [ ] Resolve numerical/canonical serialization and source-version identity sufficiently for independent implementations.
- [ ] Changing inventory, policy, assumptions or mode creates a new scenario; replay must never read latest mutable records.

Sources: V5 §§8–9; OPEN-19–22; V5-A08/A09.

---

# [PP-34] Specify presenter access, public API conventions and job integration contracts

GitHub issue: [#12](https://github.com/gbw30/PantryPulse/issues/12).

Suggested lane: Lead / API security

Development prerequisites: None.

Integration/acceptance dependencies: [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11). Early isolated work must not be described as integrated completion.

Gate: Design work can start now; domain-specific schema sections cannot be marked final until their owning contract issues are accepted.

## Work

- Resolve infrastructure portions of OPEN-29–33/36: presenter session lifecycle, backend authorization, thin same-origin proxy, CSRF, credential forwarding, safe errors and request limits.
- Define endpoint catalog, pagination/filter conventions, job status/retry/cancel behavior, read-only visitor scope and generated-contract workflow. Domain payloads must reference reviewed domain schemas rather than invent parallel DTOs.
- Specify partial-comparison outcomes, reset/retention policy and capability/readiness semantics as integration contracts; record any outstanding domain-specific blockers.

## Acceptance

- [ ] Reviewed examples distinguish 202 durable acceptance, queue-full, unavailable 503, stale 409 and validation errors.
- [ ] Job lifecycle, native solver status and method failure are separate; no method substitution or compute on GET/probes.
- [ ] Contracts can be drafted immediately; final domain payload binding remains gated by PP-30/31/32/33 and must be recorded before dependent endpoint implementation.

Sources: V5 §§12–13,19; OPEN-29–33/36; WQ §§12–13.

---

# [WQ-01] Implement pure job state, admission, deadline and handler contracts

GitHub issue: [#13](https://github.com/gbw30/PantryPulse/issues/13).

Suggested lane: Worker / pure core

Development prerequisites: None.

## Work

- Review and freeze internal WQ technical proposals; implement job/attempt/context types, allowlisted registry interfaces and pure transition/admission/freshness/deadline policies.
- Preserve one active operation, at most two queued globally, 900-second queue wait, 5-second heartbeat and unavailable at 15 seconds. Proposed exact equality rules require recorded review.
- Enforce 300-second forecast with primary stopped by 270 when fallback is allowed; 15-second native search, 25-second method and 60-second sequential comparison ceilings.
- Reject arbitrary executable/import paths and require explicit bounded typed fixture input/output.

## Acceptance

- [ ] WQ-T01–04 and T23 with injected clocks, terminal immutability, retry identity and invalid transition tests.
- [ ] No database, model download, domain API or supplier logic; preserve health and existing helpers.
- [ ] Separate accepted V5 limits from proposed internal enums/defaults; no public enum adoption by accident.

Sources: Local WORKER-JOB-QUEUE-SPEC v0.1 §§2,4–5,9,14–15; WQ-01; V5-A12.

---

# [WQ-02] Build durable queue schema and transactional admission repository

GitHub issue: [#14](https://github.com/gbw30/PantryPulse/issues/14).

Suggested lane: Lead migrations / worker repository

Development prerequisites: [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13).

Gate: Lead owns Alembic/version/config files; serialize migration changes with PP-35 and later domain migrations.

## Work

- Review/freeze jobs-only schema, control-row lock order, generation/current-attempt ownership and command idempotency before coding.
- Implement compute control/jobs/attempts/commands, constraints/indexes and repository admission/claim/cancel/retry transactions with UTC database time.
- Serialize global capacity; immutable jobs and linked manual attempts, FIFO including tie ordering, original queue deadlines and duplicate command replay.
- Use trusted internal actor/scope for foundation tests; public authorization and organization FK integration remain separate.

## Acceptance

- [ ] Real isolated PostgreSQL migration upgrade/downgrade and independent-connection barrier tests: WQ-T05–10/T21/T27.
- [ ] Concurrent requests cannot create a third queued or second active attempt; same key/payload replays and changed payload conflicts.
- [ ] Rollback cannot leave an accepted command; never hold a DB transaction during child work.

Sources: Local WQ §§6–7,14–15; WQ-02; V5-A12.

---

# [WQ-04] Build controlled process driver with actual deadline and descendant cleanup

GitHub issue: [#15](https://github.com/gbw30/PantryPulse/issues/15).

Suggested lane: Worker process boundary

Development prerequisites: [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13).

## Work

- Implement start/nonblocking poll/request-stop/force-stop/confirm-empty for exact owned child boundaries, including descendants and IPC disposal.
- Use fixed non-ML test handlers; supervise independently of blocking compute and prohibit primary/fallback overlap.
- Demonstrate cancellation and actual stop within remaining operation budget; distinguish signal delivery from confirmed termination.
- Record tested OS/runtime capability; do not install models, start heavy image builds or claim untested Windows/Linux equivalence.

## Acceptance

- [ ] WQ-T11/12/14/15/17/22/23 with real child/descendant processes, trusted runtime/start identity and explicit small test budgets.
- [ ] Policy tests assert production 270/300/15/25/60 limits; shortened runtime tests are labeled infrastructure evidence.
- [ ] Uncertain cleanup quarantines instead of freeing a slot. Actual Linux orphan-containment evidence is required before advertising runtime readiness.

Sources: Local WQ §§9,11,14–15; WQ-04; V5-A12.

---

# [WQ-03] Implement supervisor ownership, heartbeat, claiming and crash recovery

GitHub issue: [#16](https://github.com/gbw30/PantryPulse/issues/16).

Suggested lane: Worker supervisor

Development prerequisites: [WQ-01 #13](https://github.com/gbw30/PantryPulse/issues/13).

Integration/acceptance dependencies: [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14), [WQ-04 #15](https://github.com/gbw30/PantryPulse/issues/15). Early isolated work must not be described as integrated completion.

Gate: Early development uses fakes; completion/integration also requires WQ-02 and WQ-04.

## Work

- Build the supervisor against the reviewed repository protocol/fakes; wire durable repository once WQ-02 is accepted.
- Maintain heartbeat while a child is busy; fence old supervisor generations, atomically claim FIFO work and preserve queued attempts across restarts.
- On worker loss revoke publication, confirm owned child cleanup and record interruption; quarantine uncertain orphan identity without releasing the slot or automatically recomputing.
- Implement drain/immediate/crash behavior with manual retry and no broad PID/name-based termination.

## Acceptance

- [ ] WQ-T08–14/T22: two-owner contention, stale heartbeats, live busy heartbeat, no automatic retry and unrelated processes untouched.
- [ ] Unit/fake work may start after WQ-01; durable acceptance requires WQ-02 and actual process integration requires WQ-04.
- [ ] API restart and worker loss have different tested outcomes; unconfirmed cleanup retains occupied capacity.

Sources: Local WQ §§8,11,14–15; WQ-03; V5-A12.

---

# [WQ-05] Implement fenced atomic result publication and uncertain-commit recovery

GitHub issue: [#17](https://github.com/gbw30/PantryPulse/issues/17).

Suggested lane: Worker / persistence

Development prerequisites: [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14).

## Work

- Create bounded typed fixture publisher and transaction-owned publication interface; child output is staged, never self-published.
- Require current job/attempt/supervisor generation/token, RUNNING state, valid input hash, remaining time and confirmed cleanup before publication.
- Commit result manifest, success/audit and slot release atomically; stale or cancelled execution cannot publish.
- Reconcile lost COMMIT acknowledgements by identity without rerunning work or blindly duplicating results.

## Acceptance

- [ ] WQ-T18–21: stale-token rejection, invalid output, rollback, cancel/publication race and both committed/rolled-back uncertainty outcomes.
- [ ] Fixture result remains labeled test infrastructure; no planning-ready forecast/allocation claim.
- [ ] Publisher cannot create an independent transaction that breaks repository atomicity.

Sources: Local WQ §10,14–15; WQ-05; V5-A07/A12.

---

# [WQ-06] Verify durable worker vertical slice on isolated PostgreSQL

GitHub issue: [#18](https://github.com/gbw30/PantryPulse/issues/18).

Suggested lane: Worker integration / verification

Development prerequisites: [WQ-02 #14](https://github.com/gbw30/PantryPulse/issues/14), [WQ-03 #16](https://github.com/gbw30/PantryPulse/issues/16), [WQ-04 #15](https://github.com/gbw30/PantryPulse/issues/15), [WQ-05 #17](https://github.com/gbw30/PantryPulse/issues/17).

## Work

- Connect queue, supervisor, process driver and fixture publisher with fixed typed handlers on an identified isolated test database.
- Exercise durable acceptance → claim → execute → validated fenced commit; continue heartbeat/read responsiveness during execution.
- Exercise restarts, concurrent admission, expiration, cancellation, real timeout, worker loss, uncertain cleanup/commit and deliberate linked manual retry.

## Acceptance

- [ ] Run the applicable WQ-T01–27 suite with real PostgreSQL/process evidence, exact commit/config/commands and honest NOT RUN outcomes.
- [ ] Verify one active/two waiting globally; never release uncertain capacity or recompute interrupted work automatically.
- [ ] Existing health and helpers still pass; completion proves worker infrastructure only, not forecasting/solver/domain readiness.

Sources: Local WQ §§15–16; WQ-06; V5-A12 foundation.

---

# [PP-35] Implement operational database models and initial history/ledger migrations

GitHub issue: [#19](https://github.com/gbw30/PantryPulse/issues/19).

Suggested lane: Lead / database

Development prerequisites: [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8).

## Work

- Implement reviewed organization/site/product/donor, lot, demand/receipt revision, coverage, ledger/audit and confirmed-supply records.
- Apply ownership, nonnegative/unit, revision/duplicate, uniqueness/FK and version constraints with appropriate query indexes.
- Provide transaction/repository primitives for import and stock posting; leave forecast/job/scenario tables to their owning reviewed slices.

## Acceptance

- [ ] Fresh isolated PostgreSQL upgrade, integrity and rollback/downgrade evidence.
- [ ] Cross-organization references, malformed quantities and duplicate logical revisions fail appropriately.
- [ ] No SQLite-only evidence; coordinate Alembic ordering with WQ-02 and subsequent schema tasks.

Sources: V5 §§5,16–17; OPEN-04–11; V5-A02/A03.

---

# [PP-36] Integrate reviewed baseline forecasting core and safe fallback boundary

GitHub issue: [#20](https://github.com/gbw30/PantryPulse/issues/20).

Suggested lane: Forecast

Development prerequisites: [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9).

## Work

- Port/reconcile only reviewed forecasting modules from the immutable branch; preserve existing main history and numerical primitives.
- Implement requested/proxy demand and received-donation preparation, complete revision/coverage selection, seven dated outputs, weekly baseline and reviewed sparse fallback.
- Retain provenance, exact input identity and classified provider outcomes. Unsupported Chronos returns unavailable and can fall back only when permitted.
- Keep pure forecast/handoff logic independent of HTTP, ORM and worker scheduling.

## Acceptance

- [ ] Meaningful calendar, zero/null/gap, receipt aggregation, correction leakage, proxy opt-in and per-series completeness tests.
- [ ] POINT/MEAN/MEDIAN and raw quantiles are truthful; no invented intervals, clipping/imputation or hidden programming-error fallback.
- [ ] Run existing and ported focused suites on the combined tree; do not count branch-only tests as integrated evidence.

Sources: V5 §§6–7; V5-A02/A04/A05; completed helpers #3/#6.

---

# [PP-37] Implement audited stock posting, adjustments and confirmed-supply reconciliation

GitHub issue: [#21](https://github.com/gbw30/PantryPulse/issues/21).

Suggested lane: Inventory transactions

Development prerequisites: [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19).

## Work

- Implement exactly-once receipt → lot/ledger/version/audit posting and controlled adjustments with expected versions.
- Implement reviewed correction/reversal and consumed-stock handling; require explicit eligibility and keep unknown stock unavailable.
- Reconcile confirmed arrivals to received/on-hand once, invalidate affected current recommendations and preserve historical snapshots.
- Keep simulated plan review separate from reservations, purchasing or physical transfer completion.

## Acceptance

- [ ] Real PostgreSQL rollback, duplicate command, competing-version, nonnegative balance and cross-organization tests.
- [ ] Historical imports do not change stock; receipt posting changes it once; repeated/corrected receipts never double-count.
- [ ] Actor/time/reason and source links survive audit; stale writes produce the reviewed conflict outcome.

Sources: V5 §5; V5-A03; OPEN-08–11.

---

# [PP-38] Implement revision-aware demand and donation history imports

GitHub issue: [#22](https://github.com/gbw30/PantryPulse/issues/22).

Suggested lane: History / imports

Development prerequisites: [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9).

## Work

- Implement bounded CSV/import validation using final schemas, precise row/field errors and partial acceptance.
- Accept valid demand rows and complete donation receipts atomically per receipt; append revisions rather than silently overwriting.
- Preserve source classification, requested/fulfilled/unmet basis, complete reporting coverage and event-versus-receiving-site identity.
- Keep historical ingestion separate from the stock-posting command; do not backfill missing days or invent demand.

## Acceptance

- [ ] Duplicate rows/events, incomplete receipt lines, explicit null, true zero, inconsistent demand arithmetic and rejected-unit cases.
- [ ] Late correction/knowledge-cutoff tests and import replay preserve historical snapshots.
- [ ] Verify stock is byte/value unchanged by every historical import path.

Sources: V5 §§5–6; BD-26/27; V5-A02/A03.

---

# [PP-39] Implement dated FEFO inventory and shortage projection

GitHub issue: [#23](https://github.com/gbw30/PantryPulse/issues/23).

Suggested lane: Inventory projection

Development prerequisites: [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11).

## Work

- Build pure projection from reviewed lot/arrival/commitment/demand contracts; reuse branch code only after reconciling its experimental policies.
- Apply final event ordering and hard eligible-lot FEFO; retain excluded-lot reasons and confirmed-versus-forecast supply distinctions.
- Return dated service/unmet/end-stock/expiry/first-deficit with per-product units and provenance.
- Use lost sales; a late arrival cannot repair yesterday, and negative stock/invalid commitments are rejected.

## Acceptance

- [ ] Golden 40 stock with demands 50 then 40 gives unmet 50; no repeated cumulative-negative summation.
- [ ] Expiry equality, timezones, null expiry, held/unknown eligibility, zero demand, duplicate arrivals and per-day rounding cases.
- [ ] Compare independent expectations and preserve input immutability; no database mutation or optimizer call.

Sources: V5 §9; V5-A09; existing daily-rounding helper #3.

---

# [PP-40] Implement common lot-aware feasible region for both allocation methods

GitHub issue: [#24](https://github.com/gbw30/PantryPulse/issues/24).

Suggested lane: Solver / constraints

Development prerequisites: [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11).

## Work

- Construct a shared immutable feasible-region input from reviewed routes, lots, capacities and dated donor protection.
- Enforce conservation, nonnegative integer units, no overdelivery/self-transfer/relay, arrival/use/expiry, receiving/shared handling limits and hard FEFO.
- Support explicit HUB_ONLY and HUB_AND_PANTRY using the existing route-permission helper as only one component of feasibility.
- Keep objectives and institutional vulnerability out of the shared operational constraints; preserve explicit unmet slack.

## Acceptance

- [ ] Bounded zero-resource/zero-capacity/no-route examples remain useful feasible shortage outcomes unless hard constraints contradict.
- [ ] Exact-bound/bound+1 cases, eligible earlier-lot ordering and documented non-interchangeable exclusions.
- [ ] Both methods consume the same candidate/constraint identity; no favorable hidden feasible-region differences.

Sources: V5 §§8–10; V5-A09/A11; completed types/routes #1/#2.

---

# [PP-41] Build independent allocation feasibility and replay verifier

GitHub issue: [#25](https://github.com/gbw30/PantryPulse/issues/25).

Suggested lane: Independent verification

Development prerequisites: [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11).

## Work

- Implement a verifier from the frozen contract independently of solver constraint-construction code.
- Recompute lot conservation, dated service, donor protection, FEFO, route/mode, capacity and no-relay checks from candidate transfers.
- Define structured violations and reject invalid candidates before any publisher can mark a result valid.
- Use hand-authored and tiny enumerated cases; development need not wait for a working solver.

## Acceptance

- [ ] Deliberately invalid transfer vectors fail for each invariant, including cross-unit movement and late arrivals.
- [ ] Verifier is not merely the solver builder/projection implementation called again as its sole oracle.
- [ ] Compare equivalent tied solutions by feasibility/objective evidence rather than arbitrary identical vectors.

Sources: V5 §§9,16.2; V5-A09/A11; INV-03–09/19.

---

# [PP-42] Implement immutable research policy and independent AP/RP metrics

GitHub issue: [#26](https://github.com/gbw30/PantryPulse/issues/26).

Suggested lane: Research / policy and metrics

Development prerequisites: [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10).

## Work

- Implement reviewed policy/attribute validation, versioning, normalized coefficients, groups and exact/quantized representations.
- Compute service ratios, weighted shortfall, W/Z, AP/RP flags/excess and decomposed evaluation terms independently of solver encoding.
- Evaluate classical and research outputs under the same disclosed policy while preventing vulnerability/AP/RP from influencing the classical objective.
- Keep unit-specific quantities separate; zero-target ratios are null and excluded from relevant denominators.

## Acceptance

- [ ] Match PP-32 hand/enumeration oracles, equality/near-threshold, zero/singleton groups and integer overflow tests.
- [ ] Changing prepared attributes/policy creates a new immutable version and scenario identity.
- [ ] Display/replay retains both original rational information and declared scale/rounding effects.

Sources: V5 §10; OPEN-23–25; V5-A10/A11; fixed-point helper #4.

---

# [PP-43] Implement CLASSICAL_GP with the shared operational constraints

GitHub issue: [#27](https://github.com/gbw30/PantryPulse/issues/27).

Suggested lane: Solver / classical

Development prerequisites: [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-40 #24](https://github.com/gbw30/PantryPulse/issues/24).

## Work

- Implement the reviewed conventional goal-programming objective on PP-40 constraints, without research vulnerability/AP/RP terms.
- Apply deliberate solver settings, 15-second native search ceiling and native status gate before candidate access.
- Return candidate/objective/bounds/settings and method identity for independent verification; no publication shortcut.
- Preserve shortage slack and avoid replacing goal programming with an unapproved lexicographic objective.

## Acceptance

- [ ] Independent tiny-instance enumeration matches feasible objective optimum; cover zero resources and tied optima.
- [ ] OPTIMAL versus FEASIBLE are retained; UNKNOWN/MODEL_INVALID/INFEASIBLE do not invent vectors.
- [ ] Run in the supported existing solver runtime; mocked solves do not establish real solver integration.

Sources: V5 §§9–10,13; V5-A10/A11; status helper #5.

---

# [PP-44] Implement EGP_PI_INSPIRED with active AP/RP goals and ablations

GitHub issue: [#28](https://github.com/gbw30/PantryPulse/issues/28).

Suggested lane: Solver / research

Development prerequisites: [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10), [PP-40 #24](https://github.com/gbw30/PantryPulse/issues/24), [PP-42 #26](https://github.com/gbw30/PantryPulse/issues/26).

## Work

- Implement reviewed W/Z blend and nonzero AP/RP excess penalties plus declared normalized ancillary terms on PP-40 constraints.
- Reify both directions of strict threshold flags and current-allocation group means using the accepted fixed-point numerical policy.
- Preserve exact method identity, solver status/settings/decomposition and approximation disclosure.
- Provide AP-disabled and RP-disabled experiments against the same inputs; never substitute a classical vector when research fails.

## Acceptance

- [ ] PP-32 independent enumeration and PP-42 metrics agree, including equality and near-threshold cases.
- [ ] Demonstrate an interpretable changed allocation caused by active policy terms and meaningful groups, with costs/unmet tradeoffs disclosed.
- [ ] Check all int64 intermediate bounds and validate real native statuses/candidates through the independent gate.

Sources: V5 §10; TEST-EGP-01–07; V5-A10/A11.

---

# [PP-45] Persist forecasts and integrate bounded forecast worker/publication

GitHub issue: [#29](https://github.com/gbw30/PantryPulse/issues/29).

Suggested lane: Forecast / jobs integration

Development prerequisites: [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-36 #20](https://github.com/gbw30/PantryPulse/issues/20), [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12).

## Work

- Add reviewed forecast runs/series/points/input identity and evaluation/provenance storage with lead-owned migrations.
- Implement WQ-07 typed forecast handler and fenced transactional publisher, including exact-result reuse, concurrent deduplication and forced new execution.
- Enforce whole-operation 300 seconds, primary stopped by 270 when fallback is allowed, no overlapping children and original-deadline publication.
- Only committed complete results may become planning-ready; preserve original timestamps/provider/fallback on reuse.

## Acceptance

- [ ] Real PostgreSQL duplicate submission, rollback, stale attempt, invalid-output and incomplete-series publication tests.
- [ ] Classified primary failure, usable/unusable fallback and whole-operation timeout preserve truthful series outcomes.
- [ ] Baseline live integration passes; unavailable Chronos/fake provider is not actual model qualification.

Sources: V5 §§6,12–13; V5-A04/A05/A07/A12; WQ-07.

---

# [PP-46] Persist frozen operational scenarios, policies and per-method results

GitHub issue: [#30](https://github.com/gbw30/PantryPulse/issues/30).

Suggested lane: Scenario / persistence

Development prerequisites: [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11), [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-32 #10](https://github.com/gbw30/PantryPulse/issues/10).

Integration/acceptance dependencies: [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29). Early isolated work must not be described as integrated completion.

## Work

- Add reviewed immutable policy/scenario/result storage, schema version/canonical hash and exact operational source references.
- Freeze forecast result identity, lots/commitments/confirmed supply, demand assumptions, scope, routes/capacities, mode and policy.
- Implement archived access, replay and current-recommendation staleness without changing historical results.
- Provide transactional plan/method result repository interfaces for the comparison publisher; do not require a solver to develop fixture-backed storage.

## Acceptance

- [ ] Round-trip/hash consistency, explicit required mode, mixed organization/unit rejection and source mutation replay tests.
- [ ] Changing mode/input/policy creates a new snapshot; comparisons cannot select different operational snapshots.
- [ ] Forecast-record reference integration must be tested with PP-45 before live scenario creation is exposed.

Sources: V5 §§8,10,12; OPEN-19/20/25; V5-A08.

---

# [PP-47] Integrate sequential allocation/comparison jobs and checked publication

GitHub issue: [#31](https://github.com/gbw30/PantryPulse/issues/31).

Suggested lane: Solver / worker integration

Development prerequisites: [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-41 #25](https://github.com/gbw30/PantryPulse/issues/25), [PP-42 #26](https://github.com/gbw30/PantryPulse/issues/26), [PP-43 #27](https://github.com/gbw30/PantryPulse/issues/27), [PP-44 #28](https://github.com/gbw30/PantryPulse/issues/28), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12).

## Work

- Implement WQ-08 typed allocation/comparison handlers and atomic domain publishers using reviewed result/partial-comparison contracts.
- Run both methods sequentially within one slot against the same frozen snapshot and equivalent settings: 15s native/25s whole-method/60s whole-pair ceilings.
- Gate candidate reads by native status, independently verify feasibility, reproject actual service and compute shared evaluation metrics before publication.
- Preserve method-specific failure/NOT_RUN outcomes; no missing vector becomes zero transfers and no method result is relabeled.

## Acceptance

- [ ] Real solver + PostgreSQL paired integration for all four method/mode combinations, with identical pair input identity.
- [ ] One-method failure, parent/method deadline, stale generation, publisher rollback and cancel races stay truthful.
- [ ] Shipments are not automatically fulfillment; recomputed service/unmet/cost/waste and AP/RP match independent expectations.

Sources: V5 §§8–10,13,16; V5-A09–12; WQ-08.

---

# [PP-48] Expose saved domain reads and generated API/TypeScript contracts

GitHub issue: [#32](https://github.com/gbw30/PantryPulse/issues/32).

Suggested lane: Lead / read API contracts

Development prerequisites: [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12), [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31).

## Work

- Implement scoped saved reads for sites/lots/history, forecasts/shortages, snapshots/plans/comparisons, policy/methodology and safe provenance.
- Bind reviewed Pydantic/OpenAPI schemas to committed records; generate TypeScript and realistic state fixtures with drift checking.
- Keep saved reads/polling outside compute admission; expose incomplete/failure/provider/native-status information without raw secrets.
- Implement reviewed filters/pagination and precise per-category/unit/date quantities; do not add mixed-unit aggregate KPIs.

## Acceptance

- [ ] Real API/database responses match generated types and scope boundaries; visitor access follows reviewed rules.
- [ ] Compute unavailable/busy leaves saved reads usable while database health is reported honestly.
- [ ] GET/probes do not import/load models, mutate state, expire queues or initiate work.

Sources: V5 §§12–14,16; OPEN-29/36; V5-A13/A15.

---

# [PP-49] Implement presenter authorization and thin same-origin Next.js proxy

GitHub issue: [#33](https://github.com/gbw30/PantryPulse/issues/33).

Suggested lane: Lead / authentication and proxy

Development prerequisites: [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12).

## Work

- Implement reviewed presenter session/expiry/logout, backend authorization and server-only credential forwarding.
- Add thin same-origin Next.js proxy and CSRF/rate-limit/origin protections appropriate to the accepted contract.
- Keep visitor saved reads and presenter mutations distinct; client-supplied actor/presenter flags cannot authorize actions.
- Build against strict fixture endpoints while domain modules progress; do not place forecast/inventory/objective calculations in the proxy.

## Acceptance

- [ ] Direct backend bypass, missing/expired sessions, CSRF, cross-organization references and credential-leak tests.
- [ ] Tokens/secrets are absent from browser bundles, status responses and logs.
- [ ] Session/proxy behavior works in the actual browser/API boundary; mocks alone do not establish integrated authorization.

Sources: V5 §12.2–3; BD-13/14; OPEN-31; V5-A13.

---

# [PP-50] Expose authorized submissions, scenario changes and job controls

GitHub issue: [#34](https://github.com/gbw30/PantryPulse/issues/34).

Suggested lane: API / mutation integration

Development prerequisites: [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31).

## Work

- Expose reviewed forecast submission/reuse/refresh, scenario creation, allocation/comparison submission, status/history and manual retry/cancel.
- Wire WQ-09 to backend authorization, immutable inputs, durable admission and generated types; return 202 only after commit.
- Implement reviewed simulated review action with no stock/reservation/dispatch effect.
- Provide precise unavailable/full/expired/interrupted/stale/validation outcomes; scenario changes create new snapshots.

## Acceptance

- [ ] Actual HTTP tests cover duplicate keys, payload conflict, concurrent admission, one active/two queued and authorized retries/cancel.
- [ ] Cancellation-requested is not claimed stopped; retry preserves input and links attempts; old results remain inspectable.
- [ ] Client receives actual provider/method/status, and denied actions leave database state unchanged.

Sources: V5 §§8,12–14; V5-A08/A12/A13/A15; WQ-09.

---

# [PP-52] Build accessible product shell and explicit fixture-based UI states

GitHub issue: [#35](https://github.com/gbw30/PantryPulse/issues/35).

Suggested lane: Frontend / design system

Development prerequisites: None.

## Work

- Build responsive app shell, site/category/scenario navigation, shared visual tokens and domain display primitives using accepted UI stack.
- Design for six beneficiaries plus hub(s); reconcile older three-site examples without treating proposed style as accepted branding.
- Use clearly labeled fixtures for queued/failure/insufficient/stale/partial/native-status/provider states while the public contract is finalized.
- Reserve file ownership for shared tokens/components; fixtures are prototypes, not a live optimizer or real operational evidence.

## Acceptance

- [ ] Keyboard/focus, unit/horizon labels, reduced motion and responsive checks at 1440×900, 1280×720 and 390×844.
- [ ] Charts provide data alternatives and null quantiles produce no fake intervals.
- [ ] Review apps/web/AGENTS.md and installed Next.js documentation before code; public API integration waits for generated contracts.

Sources: V5 §14; ART-DIRECTION.md where compatible; V5-A16/A17.

---

# [PP-53] Connect overview, site detail and forecast/shortage explorer

GitHub issue: [#36](https://github.com/gbw30/PantryPulse/issues/36).

Suggested lane: Frontend / operational views

Development prerequisites: [PP-48 #32](https://github.com/gbw30/PantryPulse/issues/32), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-52 #35](https://github.com/gbw30/PantryPulse/issues/35).

## Work

- Connect generated API client and actual saved data for overview/site inventory, history, seven-day demand/donation forecasts and dated shortages.
- Show category/unit/horizon, actual provider, generation/cutoff/proxy/fallback metadata, exclusions and first deficit.
- Implement loading/empty/error/insufficient/degraded/stale states while retaining timestamped last successful data.
- Display model quantiles only when present and label explicit scenario buffers without probability claims.

## Acceptance

- [ ] Browser/API values match committed source records, including zero versus unknown and per-category quantities.
- [ ] Keyboard-operable filters and chart data table; no stale older response overwrites a newer selection.
- [ ] Saved reads remain available during compute outage and UI never simulates a successful live computation.

Sources: V5 §§6,9,14; V5-A13/A15/A17.

---

# [PP-54] Connect paired comparison, scenario editing, explanations and review

GitHub issue: [#37](https://github.com/gbw30/PantryPulse/issues/37).

Suggested lane: Frontend / planning workflow

Development prerequisites: [PP-48 #32](https://github.com/gbw30/PantryPulse/issues/32), [PP-50 #34](https://github.com/gbw30/PantryPulse/issues/34), [PP-52 #35](https://github.com/gbw30/PantryPulse/issues/35).

## Work

- Present CLASSICAL_GP versus EGP_PI_INSPIRED on the same snapshot/mode with six-beneficiary service/unmet/AP/RP/attribute evidence.
- Implement explicit required transfer mode, reviewed policy/disruption controls, draft-versus-applied state and deliberate Recalculate producing a new scenario.
- Poll durable jobs and display per-method statuses/failures, non-optimal FEASIBLE outcomes, validated lot transfers and remaining need.
- Provide simulated review and replay/provenance/methodology details; resolve or hold numeric per-transfer benefit under OPEN-02.

## Acceptance

- [ ] Real scenario change updates the corresponding result while preserving baseline and earlier snapshot identity.
- [ ] One-method failure stays visible without substitution; duplicate submit/stale-response behavior is tested.
- [ ] Research attribution/limitations are visible early; no purchasing, reservations or dispatch implied.

Sources: V5 §§8–10,14; OPEN-02; V5-A11/A15/A16.

---

# [PP-55] Qualify dataset sources and design representative deterministic fixtures

GitHub issue: [#38](https://github.com/gbw30/PantryPulse/issues/38).

Suggested lane: Data / research

Development prerequisites: None.

## Work

- Inspect candidate dictionary/raw samples and terms before selecting any external dataset; use DATASET-RESEARCH.md as recommendations, not accepted source policy.
- Document requested versus fulfilled proxy and actual received versus offered supply, reporting coverage, units, dates, source versions/checksums and transformation manifest.
- Design six-beneficiary/two-product simulated demo cases plus independent arithmetic/adversarial cases, including scarcity, FEFO, reserves, late arrivals and missingness.
- Keep external retail proxy evaluation separate from pantry simulation; do not infer institutional vulnerability from client demographics or guarantee a method wins.

## Acceptance

- [ ] Publish sample/schema qualification findings and explicit accepted/rejected/unknown fields; metadata alone is not import validation.
- [ ] Fixture design can start now; wire/seed serialization awaits PP-30/31/32/33 and is implemented in PP-51.
- [ ] All added assumptions are labeled simulated, reproducible and provenance-linked; redistribution terms/attribution recorded.

Sources: V5 §§2,5,7,10,16; DATASET-RESEARCH.md (recommendations only); V5-A02/A06/A10.

---

# [PP-51] Build deterministic V5 demo seed and protected isolated reset

GitHub issue: [#39](https://github.com/gbw30/PantryPulse/issues/39).

Suggested lane: Data / demo integration

Development prerequisites: [PP-35 #19](https://github.com/gbw30/PantryPulse/issues/19), [PP-37 #21](https://github.com/gbw30/PantryPulse/issues/21), [PP-38 #22](https://github.com/gbw30/PantryPulse/issues/22), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-46 #30](https://github.com/gbw30/PantryPulse/issues/30), [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33), [PP-55 #38](https://github.com/gbw30/PantryPulse/issues/38).

## Work

- Implement versioned deterministic six-beneficiary/one-hub/two-product 90-day seed with fixed America/New_York demo anchor.
- Seed explicit demand/receipt coverage, dated eligible/held/expiring lots, arrivals, routes/capacities and at least two simulated institution attributes.
- Implement reviewed presenter-only reset scoped to a demo organization, coordinating active jobs/fences, caches/history retention and audit.
- Retain small exact arithmetic fixtures separately from the expanded rehearsal data; include disruptions and both transfer modes.

## Acceptance

- [ ] Repeated reset reproduces the dataset hash; non-demo reset is rejected and unrelated organization data remains unchanged.
- [ ] Active/late worker cannot republish old results into reset state; reset transaction failure cannot leave a partial seed.
- [ ] All required 12 demand/14 donation series are represented or deliberately unavailable; no invented real-world provenance.

Sources: V5 §§2,7.1,12,16; OPEN-32; V5-A02/A08/A15/A18.

---

# [PP-56] Implement chronological forecast evaluation and representative benchmark reports

GitHub issue: [#40](https://github.com/gbw30/PantryPulse/issues/40).

Suggested lane: Forecast evaluation

Development prerequisites: [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-36 #20](https://github.com/gbw30/PantryPulse/issues/20), [PP-55 #38](https://github.com/gbw30/PantryPulse/issues/38).

## Work

- Implement agreed rolling chronological origins, frozen training/knowledge cutoffs and untouched final holdout where history supports it.
- Evaluate mandatory baselines and qualified actual providers on identical origin/series/day/unit/basis truth sets.
- Report MAE/bias/WAPE plus unavailable/missing/basis-mismatch/fallback/coverage counts; preserve full cohorts alongside common scored comparisons.
- Separate simulated pantry, external synthetic food-bank and retail proxy benchmark reports; prohibit future-covariate/scale/selection leakage.

## Acceptance

- [ ] Independent arithmetic tests include no pairs, zero actual denominator, missing actuals and uneven provider coverage.
- [ ] Reproducible manifest/commands/seed/hash and honest seasonality/domain limitations.
- [ ] Chronos is not included as a real model result until separately qualified under PP-62; a worse outcome is disclosed.

Sources: V5 §§6–7; OPEN-18; V5-A06.

---

# [PP-57] Activate meaningful CI and complete migration/contract/test gates

GitHub issue: [#41](https://github.com/gbw30/PantryPulse/issues/41).

Suggested lane: Lead / quality infrastructure

Development prerequisites: None.

Gate: Incremental infrastructure work is ready; end-to-end/full-green status requires downstream substantive tests.

## Work

- Reconcile the GitHub Actions template with current locked toolchains and actual install/check/build commands; avoid deployment side effects.
- Wire existing substantive unit/build/config checks immediately. Add genuine PostgreSQL migration and OpenAPI/TypeScript drift checks as their owning tests/contracts land; missing required full checks remain failures/unverified.
- Preserve existing quick checks and health/helper regressions; distinguish scaffold, pure, DB, process, solver, browser and release evidence.
- Make missing required checks fail or report unverified rather than adding green no-op commands.

## Acceptance

- [ ] CI detects an intentional failing check and contract drift; migrations run on identified isolated PostgreSQL.
- [ ] Initial runner/config work can start now. Deliver honest incremental gate wiring; PP-58 owns final end-to-end acceptance, so this issue must not depend on PP-58 or claim full product-green status.
- [ ] Document exact commands, artifacts, source fingerprint and remaining unimplemented gates.

Sources: V5 §16.3; OPEN-34/36; V5-A01/A13/A18.

---

# [PP-58] Verify real judge journey, research comparison and adversarial failures

GitHub issue: [#42](https://github.com/gbw30/PantryPulse/issues/42).

Suggested lane: Independent integration verification

Development prerequisites: [PP-51 #39](https://github.com/gbw30/PantryPulse/issues/39), [PP-53 #36](https://github.com/gbw30/PantryPulse/issues/36), [PP-54 #37](https://github.com/gbw30/PantryPulse/issues/37), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31), [PP-57 #41](https://github.com/gbw30/PantryPulse/issues/41).

## Work

- Build Playwright/API/DB checks for reset/import/read → live baseline forecast → shortage → paired methods → changed scenario → simulation review/replay.
- Independently verify both modes, actual solver integration, AP/RP-active difference and frozen input equality without relying only on solver's checker.
- Exercise authorization, duplicates, concurrent stock versions, missing history, late corrections, provider fallback, queued/cancelled/interrupted jobs, timeout and one-method failure.
- Measure actual saved-read and per-method responsiveness; disclose target misses separately from correctness and hard-limit failures.

## Acceptance

- [ ] Assertions prove persisted state/hash changes and exact values; screenshots alone or landing-page smoke are insufficient.
- [ ] Real PostgreSQL/API/solver/browser run with exact commit/runtime/commands; missing/skipped/mock-only checks remain unverified.
- [ ] All V5-A01–13/A15/A16 evidence mapped with failures repaired or explicit release blockers.

Sources: V5 §§16–17; V5-A01–13/A15/A16; WQ acceptance cross-reference.

---

# [PP-59] Complete rendered accessibility, responsive and visual acceptance

GitHub issue: [#43](https://github.com/gbw30/PantryPulse/issues/43).

Suggested lane: Frontend / independent UX verification

Development prerequisites: [PP-53 #36](https://github.com/gbw30/PantryPulse/issues/36), [PP-54 #37](https://github.com/gbw30/PantryPulse/issues/37).

## Work

- Inspect real seeded UI at three required viewports; repair comprehension, contrast, overflow, touch target and focus issues.
- Walk filters/site detail/chart tables/scenario editor/job controls/review entirely by keyboard.
- Validate reduced motion, meaningful announcements, honest point/quantile charts and persistent scenario/provider/status labels.
- Capture evidence and human review of actual rendered app; proposed art direction remains subject to visual acceptance.

## Acceptance

- [ ] 1440×900, 1280×720 and 390×844 screenshots plus keyboard/reduced-motion observations.
- [ ] Automated accessibility findings addressed with manual checks; critical values never depend solely on color/hover.
- [ ] At-risk site/date/action and method tradeoffs are understandable without developer narration.

Sources: V5 §14/16; ART-DIRECTION.md; V5-A17.

---

# [PP-60] Verify worker readiness, redacted observability and effective resource limits

GitHub issue: [#44](https://github.com/gbw30/PantryPulse/issues/44).

Suggested lane: Worker / operations verification

Development prerequisites: [WQ-06 #18](https://github.com/gbw30/PantryPulse/issues/18), [PP-34 #12](https://github.com/gbw30/PantryPulse/issues/12).

## Work

- Implement final safe job/readiness/capability/log/audit read models; correlate requests/jobs/attempts without logging secrets/tokens/raw payloads.
- Measure busy-worker heartbeat, saved-read responsiveness, effective 6-CPU-equivalent/8-GiB ceilings and process/thread settings in the supported runtime.
- Exercise unavailable/quarantine/cleanup/deadline diagnostics and preserve distinction between API liveness, compute availability and actual provider qualification.
- Use existing authorized test runtime; any heavy hosting/model setup waits for explicit resumption and PP-63/62.

## Acceptance

- [ ] WQ-T24–28 and V5-A12/A13 evidence; health remains exactly the current process-health response.
- [ ] Configured limits are not reported as effective without actual runtime measurements.
- [ ] Document platform/resource limitations and NOT RUN gates rather than treating test handlers as model qualification.

Sources: V5 §13; BD-30/31/34–39; WQ-10; V5-A12/A13/A18.

---

# [PP-61] Resolve and implement simulated supplier proposal scope when resumed

GitHub issue: [#45](https://github.com/gbw30/PantryPulse/issues/45).

Suggested lane: Supplier / paused scope

Development prerequisites: [PP-30 #8](https://github.com/gbw30/PantryPulse/issues/8), [PP-33 #11](https://github.com/gbw30/PantryPulse/issues/11), [PP-39 #23](https://github.com/gbw30/PantryPulse/issues/23), [PP-47 #31](https://github.com/gbw30/PantryPulse/issues/31), [PP-49 #33](https://github.com/gbw30/PantryPulse/issues/33).

Gate: PAUSED: requires explicit user resumption and reviewed unresolved supplier policy before development.

## Work

- Keep OPEN-03/26–28 paused until explicit resumption; then resolve split sourcing, offer terms, coverage, currency/budget periods, limits, ranking and lifecycle.
- After reviewed policy, implement seeded/manual offers and coordinated draft baskets covering only after ETA within available forecast dates.
- Account for confirmed stock/arrivals and selected transfer plan; preserve alternatives/uncovered need and treat method baskets as alternatives under one budget.
- Keep unapproved proposals outside physical/confirmed inventory and primary comparison; no supplier messages, orders, payments or dispatch.

## Acceptance

- [ ] After-arrival coverage cannot erase earlier lost sales; shared budget/per-order constraints hold across beneficiaries.
- [ ] Repeated generation/cancel and alternatives follow final immutable proposal policy with no stock or external side effects.
- [ ] V5-A14 remains blocked until completed or explicit scope amendment; creating this issue does not resume paused work.

Sources: V5 §11; BD-22–24; OPEN-03/26–28; V5-A14.

---

# [PP-62] Separately qualify actual pinned Chronos inference when resumed

GitHub issue: [#46](https://github.com/gbw30/PantryPulse/issues/46).

Suggested lane: Forecast / paused model qualification

Development prerequisites: [PP-31 #9](https://github.com/gbw30/PantryPulse/issues/9), [PP-45 #29](https://github.com/gbw30/PantryPulse/issues/29), [PP-56 #40](https://github.com/gbw30/PantryPulse/issues/40), [PP-60 #44](https://github.com/gbw30/PantryPulse/issues/44).

Gate: PAUSED: requires explicit model/setup resumption. Not a mandatory dependency of baseline-core release.

## Work

- Preserve model/heavy setup pause until explicit resumption; then qualify pinned package/checkpoint/revision, native missing-value behavior, grouping and typed covariates.
- Integrate actual inference behind reviewed adapter/process boundary and validate date/series mapping, raw quantiles, postprocessing and fallback.
- Measure cold/warm runtime/resources and accuracy against mandatory baselines on representative chronological data.
- Keep live baseline release qualification independent; never relabel cached/mocked/fallback outputs as Chronos execution.

## Acceptance

- [ ] Actual full-scope seven-date inference and failure/270–300s containment evidence with exact versions/settings.
- [ ] Disclose worse accuracy, invalid outputs, unavailable hardware or target misses; no calibration claim from raw quantiles.
- [ ] Record model-qualified separately from core-ready, compute-ready and saved replay.

Sources: V5 §§6.5–7,15–16; BD-33; OPEN-15/18/35; V5-A05/A06.

---

# [PP-63] Prepare release evidence, authorized hosting and five demo rehearsals

GitHub issue: [#47](https://github.com/gbw30/PantryPulse/issues/47).

Suggested lane: Lead / release

Development prerequisites: [PP-58 #42](https://github.com/gbw30/PantryPulse/issues/42), [PP-59 #43](https://github.com/gbw30/PantryPulse/issues/43), [PP-60 #44](https://github.com/gbw30/PantryPulse/issues/44), [PP-56 #40](https://github.com/gbw30/PantryPulse/issues/40), [PP-61 #45](https://github.com/gbw30/PantryPulse/issues/45).

Gate: Release/hosting actions remain conditional on explicit target authorization/resumption; issue creation does not authorize deployment or submission.

## Work

- Assemble release manifest with commit/source fingerprint, dataset/snapshot/policy hashes, dependencies/runtime, accepted omissions and rollback/local fallback.
- Preserve hosting/heavy setup pause until explicit resumption; prepare configuration first, then qualify only the named authorized target with real proxy/auth/DB/compute smoke tests.
- Run five reset-to-finish rehearsals including cold/provider failure cases, backup recording and honest provider/method/limitations labels.
- Reconcile submission assets with actual results and independently confirmed event requirements; do not deploy/publish/submit merely because tests pass.

## Acceptance

- [ ] Required core/research/stock/security/FEFO/replay gates pass on merged release tree; performance target misses are measured/disclosed.
- [ ] PP-61 must complete or an explicit approved supplier scope amendment must replace that dependency; do not silently declare suppliers optional.
- [ ] PP-62 is separately reported and not a baseline-core blocker; mark Chronos unverified if not qualified.
- [ ] Record five rehearsal results, reset hashes, live target smoke where authorized, rollback/backup and accurate release claims.

Sources: V5 §§15–17; V5-A14–18; DEMO.md only where compatible with V5.
