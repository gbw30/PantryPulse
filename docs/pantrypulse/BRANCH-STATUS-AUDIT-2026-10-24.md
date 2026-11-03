# PantryPulse branch and GitHub backlog audit

**Audit date:** October 24, 2026 (America/New_York).  
**Scope:** committed code, tests and documentation on `main`, `VP` and `or_pipeline`, plus all 59 pre-existing issues and seven new backlog items. This supersedes the earlier [9:18 p.m. status snapshot](GITHUB-STATUS-REPORT-2026-10-24.md).

## Outcome

Seven delivered main issues were closed: **#13–18 and #20**. The six previously closed helper issues **#1–6** remain closed. **53 existing issues** received current evidence/status blocks and labels; broader incomplete items remain open. Seven non-duplicate issues were created: **#67–73**.

The resulting backlog contains **66 issues: 13 closed and 53 open**. Labels distinguish delivered work, branch implementation, partial work, blockers, ready follow-ups, pauses and deferred roadmap work. Closing a foundation issue does not accept all of V5.

No source branch was merged or reset, no application implementation changed, and no hosted database migration or deployment occurred. Existing supplier/Chronos/hosting pauses remain. Documentation changes from this audit are in the current local checkout; this audit does not claim they are already merged into any of the three reviewed branches.

## Branches inspected

| Branch | Exact head | Relationship to audited main | Actual implementation |
| --- | --- | --- | --- |
| [main](https://github.com/gbw30/PantryPulse/tree/873d3569ee6bcb9efb827f930cb6d0c40c84db47) | `873d3569ee6bcb9efb827f930cb6d0c40c84db47` | Baseline | Six helpers, corrected offline forecasting, illustrative design lab and durable worker foundation from PRs #7/#51/#52/#53. Application API is still health-only and production registry empty. |
| [VP](https://github.com/gbw30/PantryPulse/tree/6f3d04e60f6f121a8064d1543b7f2f83136896b9) | `6f3d04e60f6f121a8064d1543b7f2f83136896b9` | 4 commits ahead, 0 behind | Operational contracts, domain SQL/ORM, receipt revisions, ledger/stock commands, confirmed-supply reconciliation, operational projection and pure frozen-scenario/freshness helpers. Domain routes and public imports remain absent. |
| [or_pipeline](https://github.com/gbw30/PantryPulse/tree/46ff0cd8aaf299b1874e7400e42bdc9f6b23d978) | `46ff0cd8aaf299b1874e7400e42bdc9f6b23d978` | 2 commits ahead, 19 behind | Native classical/research-inspired allocation, independent enumeration/checking, simulated input/scenario/result persistence, production OR worker handlers, auth/API/proxy, generated contracts, CLI and saved comparison UI. Authoritative source integration remains unavailable. |

Commit ancestry is separate from functionality: OR selectively incorporated shared queue code, so “19 behind” does not mean that its worker foundation is absent. Shared worker code also diverges and must be reconciled.

[PR #58](https://github.com/gbw30/PantryPulse/pull/58) was open for design-lab typography/chart refinements at the initial GitHub snapshot. It is outside the three branch heads above and was not counted as delivered product functionality.

## Fresh verification

All sources were exported from the exact refs above into ignored audit directories and mounted read-only in disposable Linux test containers. Tests reused the installed `pantrypulse-api:latest` dependency image. Database checks used a newly created PostgreSQL 16 container with no host ports, no volume and no external network; existing development/Neon databases were not used.

| Branch | Command from `apps/api` (`python -m pytest` prefix) | Result | Scope |
| --- | --- | --- | --- |
| main | `-q -p no:cacheprovider --ignore=tests/integration --ignore=tests/workers --tb=short` | **642 passed** | Existing helpers, forecasting and pure/job behavior |
| main | `-q -p no:cacheprovider tests/integration/test_job_migrations.py tests/integration/test_job_queue.py tests/integration/test_supervisor.py --tb=short` | **89 passed** | Actual queue migrations, transactional admission and supervisor repository behavior |
| VP | `-q -p no:cacheprovider tests/test_operational_schema.py tests/test_operational_models.py tests/test_scenario_contract.py tests/test_inventory_projection.py tests/test_stock_commands.py tests/test_merged_migrations.py --tb=short` | **159 passed** | Contracts, pure stock/projection/scenario and migration graph |
| VP | `-q -p no:cacheprovider tests/integration/test_operational_postgres.py tests/integration/test_stock_postgres.py --tb=short` | **38 passed** | Actual migrations, ownership/integrity, stock posting, concurrency and rollback |
| or_pipeline | `-q -p no:cacheprovider tests/optimization --tb=short` | **104 passed** | Actual native OR-Tools solves, exact oracle/equivalence, thresholds/ablations, replay and CLI |
| or_pipeline | `-q -p no:cacheprovider tests/integration/test_or_persistence.py tests/integration/test_or_http.py --tb=short` | **40 passed** | Actual OR persistence, migrations, auth and HTTP behavior |

**Total: 1,072 passing test cases across these focused runs.** No skipped test is counted. The existing Starlette/httpx deprecation warning appeared in the API runs.

The audit did **not** rerun the full browser/rehearsal matrix, Linux cgroup/OOM/descendant tests, the complete worker vertical slice, production web builds or hosted Actions. PR #52 and the OR branch's checkpoint retain their own recorded evidence; it is historical evidence for its original tree/environment.

## Integration blockers found in code

### 1. Incompatible audit tables and migration histories — #67

VP defines [operational `audit_events`](https://github.com/gbw30/PantryPulse/blob/6f3d04e60f6f121a8064d1543b7f2f83136896b9/apps/api/app/models/operational.py#L351) with required `command_id` and `event`; OR defines [another `audit_events`](https://github.com/gbw30/PantryPulse/blob/46ff0cd8aaf299b1874e7400e42bdc9f6b23d978/apps/api/app/models/or_records.py#L327) with `actor_id`, `action` and `resource_id`. Separate branch tests pass, but the schemas are incompatible under that same table name.

VP's head `pp_merge_0003` joins the operational and worker histories. OR extends the worker history to `0005_or_active_dedup`. No reviewed combined successor, metadata/env integration or audit-table migration exists. [#67](https://github.com/gbw30/PantryPulse/issues/67) owns this convergence and combined upgrade/regression proof.

### 2. Accepted operational expiry differs from the OR draft — #68

[VP's projection](https://github.com/gbw30/PantryPulse/blob/6f3d04e60f6f121a8064d1543b7f2f83136896b9/apps/api/app/services/inventory/projection.py#L73) expires dated stock when `expires_on < day`, preserving accepted use through expiry day. It distinguishes dated, declared non-expiring and unknown expiry.

[OR's recurrence](https://github.com/gbw30/PantryPulse/blob/46ff0cd8aaf299b1874e7400e42bdc9f6b23d978/apps/api/app/services/inventory/kernel.py#L49) expires it when `expires_on <= day`; provisional OR-DEC-001 and SQL transfer-date constraints use that exclusive boundary. VP also records later donor/usefulness decisions. A conversion, new version or explicitly approved amendment is required; historical scenarios must remain replayable.

[#68](https://github.com/gbw30/PantryPulse/issues/68) owns contract reconciliation across schemas, CP constraints, projection, verifier, SQL, fixtures and documentation. Do not treat either branch's independently passing tests as evidence that they implement the same policy.

### 3. Committed CI cannot reproduce the saved full-gate claim — #41/#63

Every reviewed branch has only `pantrypulse-ci.yml.template`; none has an active `.yml`/`.yaml` workflow.

The [committed OR gate configuration](https://github.com/gbw30/PantryPulse/blob/46ff0cd8aaf299b1874e7400e42bdc9f6b23d978/.claude/quality-gate.json) still calls:

- `apps/web` npm script `test:unit`, which is missing.
- `apps/web` npm script `contracts:check`, which is missing (OR's new script is at the root).
- `apps/api/tests/integration/test_migrations.py`, which is missing.

The OR checkpoint records a different successful gate sequence. That saved result is not evidence that this committed configuration works. [#41](https://github.com/gbw30/PantryPulse/issues/41) and [#63](https://github.com/gbw30/PantryPulse/issues/63) remain partial; no duplicate CI issue was created.

### 4. Committed-source forecasting and OR composition remain absent — #29/#64–66

The [OR from-sources endpoint](https://github.com/gbw30/PantryPulse/blob/46ff0cd8aaf299b1874e7400e42bdc9f6b23d978/apps/api/app/routers/or_api.py#L207) explicitly returns `SOURCE_INTEGRATION_UNAVAILABLE`. No branch provides a complete committed forecast publication handler and authoritative forecast/inventory/operational read composition.

VP supplies substantial ledger/stock foundations, so #65's old “no storage” assumption is obsolete. It does not supply the OR read adapters. Keep #29/#64–66 open, using existing offline forecasting and shared queue code.

The [VP receipt repository](https://github.com/gbw30/PantryPulse/blob/6f3d04e60f6f121a8064d1543b7f2f83136896b9/apps/api/app/repositories/operational.py) explicitly provides small persistence primitives; it is not the bounded CSV/bulk import workflow requested in #22.

## Issue-by-issue disposition

The six helper issues #1–6 remain correctly closed. The following table covers every other pre-existing issue. Each updated issue contains immutable source links and a scoped completion/remaining-work explanation.

| Issue | Existing scope | Current disposition | Evidence branch |
| --- | --- | --- | --- |
| [#8](https://github.com/gbw30/PantryPulse/issues/8) | [PP-30] Freeze operational identity, history, receipt and ledger contracts | Implemented on branch; open | VP |
| [#9](https://github.com/gbw30/PantryPulse/issues/9) | [PP-31] Review forecasting branch and freeze forecast, fallback and reuse contracts | Partially implemented; open | main |
| [#10](https://github.com/gbw30/PantryPulse/issues/10) | [PP-32] Pass independent mathematical specification and enumeration gate | Implemented on branch; open | or_pipeline |
| [#11](https://github.com/gbw30/PantryPulse/issues/11) | [PP-33] Freeze operational scenario, FEFO and shared feasibility contracts | Blocked; open | VP |
| [#12](https://github.com/gbw30/PantryPulse/issues/12) | [PP-34] Specify presenter access, public API conventions and job integration contracts | Partially implemented; open | or_pipeline |
| [#13](https://github.com/gbw30/PantryPulse/issues/13) | [WQ-01] Implement pure job state, admission, deadline and handler contracts | Delivered on main; closed | main |
| [#14](https://github.com/gbw30/PantryPulse/issues/14) | [WQ-02] Build durable queue schema and transactional admission repository | Delivered on main; closed | main |
| [#15](https://github.com/gbw30/PantryPulse/issues/15) | [WQ-04] Build controlled process driver with actual deadline and descendant cleanup | Delivered on main; closed | main |
| [#16](https://github.com/gbw30/PantryPulse/issues/16) | [WQ-03] Implement supervisor ownership, heartbeat, claiming and crash recovery | Delivered on main; closed | main |
| [#17](https://github.com/gbw30/PantryPulse/issues/17) | [WQ-05] Implement fenced atomic result publication and uncertain-commit recovery | Delivered on main; closed | main |
| [#18](https://github.com/gbw30/PantryPulse/issues/18) | [WQ-06] Verify durable worker vertical slice on isolated PostgreSQL | Delivered on main; closed | main |
| [#19](https://github.com/gbw30/PantryPulse/issues/19) | [PP-35] Implement operational database models and initial history/ledger migrations | Implemented on branch; open | VP |
| [#20](https://github.com/gbw30/PantryPulse/issues/20) | [PP-36] Integrate reviewed baseline forecasting core and safe fallback boundary | Delivered on main; closed | main |
| [#21](https://github.com/gbw30/PantryPulse/issues/21) | [PP-37] Implement audited stock posting, adjustments and confirmed-supply reconciliation | Implemented on branch; open | VP |
| [#22](https://github.com/gbw30/PantryPulse/issues/22) | [PP-38] Implement revision-aware demand and donation history imports | Blocked; open | VP |
| [#23](https://github.com/gbw30/PantryPulse/issues/23) | [PP-39] Implement dated FEFO inventory and shortage projection | Implemented on branch; open | VP |
| [#24](https://github.com/gbw30/PantryPulse/issues/24) | [PP-40] Implement common lot-aware feasible region for both allocation methods | Implemented on branch; open | or_pipeline |
| [#25](https://github.com/gbw30/PantryPulse/issues/25) | [PP-41] Build independent allocation feasibility and replay verifier | Implemented on branch; open | or_pipeline |
| [#26](https://github.com/gbw30/PantryPulse/issues/26) | [PP-42] Implement immutable research policy and independent AP/RP metrics | Implemented on branch; open | or_pipeline |
| [#27](https://github.com/gbw30/PantryPulse/issues/27) | [PP-43] Implement CLASSICAL_GP with the shared operational constraints | Implemented on branch; open | or_pipeline |
| [#28](https://github.com/gbw30/PantryPulse/issues/28) | [PP-44] Implement EGP_PI_INSPIRED with active AP/RP goals and ablations | Implemented on branch; open | or_pipeline |
| [#29](https://github.com/gbw30/PantryPulse/issues/29) | [PP-45] Persist forecasts and integrate bounded forecast worker/publication | Blocked; open | main |
| [#30](https://github.com/gbw30/PantryPulse/issues/30) | [PP-46] Persist frozen operational scenarios, policies and per-method results | Partially implemented; open | or_pipeline |
| [#31](https://github.com/gbw30/PantryPulse/issues/31) | [PP-47] Integrate sequential allocation/comparison jobs and checked publication | Implemented on branch; open | or_pipeline |
| [#32](https://github.com/gbw30/PantryPulse/issues/32) | [PP-48] Expose saved domain reads and generated API/TypeScript contracts | Partially implemented; open | or_pipeline |
| [#33](https://github.com/gbw30/PantryPulse/issues/33) | [PP-49] Implement presenter authorization and thin same-origin Next.js proxy | Implemented on branch; open | or_pipeline |
| [#34](https://github.com/gbw30/PantryPulse/issues/34) | [PP-50] Expose authorized submissions, scenario changes and job controls | Partially implemented; open | or_pipeline |
| [#35](https://github.com/gbw30/PantryPulse/issues/35) | [PP-52] Build accessible product shell and explicit fixture-based UI states | Partially implemented; open | or_pipeline |
| [#36](https://github.com/gbw30/PantryPulse/issues/36) | [PP-53] Connect overview, site detail and forecast/shortage explorer | Blocked; open | or_pipeline |
| [#37](https://github.com/gbw30/PantryPulse/issues/37) | [PP-54] Connect paired comparison, scenario editing, explanations and review | Partially implemented; open | or_pipeline |
| [#38](https://github.com/gbw30/PantryPulse/issues/38) | [PP-55] Qualify dataset sources and design representative deterministic fixtures | Partially implemented; open | or_pipeline |
| [#39](https://github.com/gbw30/PantryPulse/issues/39) | [PP-51] Build deterministic V5 demo seed and protected isolated reset | Partially implemented; open | or_pipeline |
| [#40](https://github.com/gbw30/PantryPulse/issues/40) | [PP-56] Implement chronological forecast evaluation and representative benchmark reports | Partially implemented; open | main |
| [#41](https://github.com/gbw30/PantryPulse/issues/41) | [PP-57] Activate meaningful CI and complete migration/contract/test gates | Partially implemented; open | or_pipeline |
| [#42](https://github.com/gbw30/PantryPulse/issues/42) | [PP-58] Verify real judge journey, research comparison and adversarial failures | Partially implemented; open | or_pipeline |
| [#43](https://github.com/gbw30/PantryPulse/issues/43) | [PP-59] Complete rendered accessibility, responsive and visual acceptance | Partially implemented; open | or_pipeline |
| [#44](https://github.com/gbw30/PantryPulse/issues/44) | [PP-60] Verify worker readiness, redacted observability and effective resource limits | Partially implemented; open | or_pipeline |
| [#45](https://github.com/gbw30/PantryPulse/issues/45) | [PP-61] Resolve and implement simulated supplier proposal scope when resumed | Paused; open | main |
| [#46](https://github.com/gbw30/PantryPulse/issues/46) | [PP-62] Separately qualify actual pinned Chronos inference when resumed | Paused; open | main |
| [#47](https://github.com/gbw30/PantryPulse/issues/47) | [PP-63] Prepare release evidence, authorized hosting and five demo rehearsals | Blocked; open | or_pipeline |
| [#48](https://github.com/gbw30/PantryPulse/issues/48) | [BACKLOG] V5 parallel development plan and dependency index | Partially implemented; open | main |
| [#54](https://github.com/gbw30/PantryPulse/issues/54) | [OR] Draft 1.1 implementation tracker and Codex handoff | Partially implemented; open | or_pipeline |
| [#55](https://github.com/gbw30/PantryPulse/issues/55) | [OR-DOCS] Adopt Draft 1.1 specs and searchable provisional decisions | Partially implemented; open | or_pipeline |
| [#56](https://github.com/gbw30/PantryPulse/issues/56) | [OR-ADAPTER] Adapt merged forecasts to frozen OR targets without double rounding | Partially implemented; open | or_pipeline |
| [#57](https://github.com/gbw30/PantryPulse/issues/57) | [OR-TOOLS] Add bounded offline OR commands and reproducible evidence tooling | Partially implemented; open | or_pipeline |
| [#59](https://github.com/gbw30/PantryPulse/issues/59) | [PBI-OR-01] Understand the frozen assumptions behind a saved comparison | Ready; open | or_pipeline |
| [#60](https://github.com/gbw30/PantryPulse/issues/60) | [PBI-OR-02] Read the saved allocation result first on a phone | Ready; open | or_pipeline |
| [#61](https://github.com/gbw30/PantryPulse/issues/61) | [PBI-OR-03] Explain who gains, who loses, and why AP/RP flags appear | Ready; open | or_pipeline |
| [#62](https://github.com/gbw30/PantryPulse/issues/62) | [PBI-OR-04] Accept the explained OR journey across desktop, mobile and keyboard | Blocked; open | or_pipeline |
| [#63](https://github.com/gbw30/PantryPulse/issues/63) | [PBI-OR-05] Give the team an auditable acceptance ledger and reproducible CI gate | Partially implemented; open | or_pipeline |
| [#64](https://github.com/gbw30/PantryPulse/issues/64) | [PBI-OR-06] Publish a committed baseline forecast that planning can trust | Blocked; open | main |
| [#65](https://github.com/gbw30/PantryPulse/issues/65) | [PBI-OR-07] Build an OR snapshot from authoritative stock and operational records | Blocked; open | VP |
| [#66](https://github.com/gbw30/PantryPulse/issues/66) | [PBI-OR-08] Complete the committed-source forecast-to-OR planning journey | Blocked; open | or_pipeline |

“Implemented on branch” keeps an issue **open** for review/integration; it is not a claim of acceptance on main. Partial items can reuse existing code and must not be restarted as empty implementations.

## New backlog coverage

| Issue | Missing scope | Scheduling |
| --- | --- | --- |
| [#67](https://github.com/gbw30/PantryPulse/issues/67) | VP/OR audit-table, migrations, metadata and shared worker convergence | P0 integration blocker |
| [#68](https://github.com/gbw30/PantryPulse/issues/68) | Expiry, lot partition, event order and donor/usefulness contract reconciliation | P0 integration blocker |
| [#69](https://github.com/gbw30/PantryPulse/issues/69) | Atomic operational approval, reservations, cancellation/completion and discrepancy audit | P1 deferred |
| [#70](https://github.com/gbw30/PantryPulse/issues/70) | Calibrated uncertainty, typed covariates, stronger baselines and evaluated selection/ensembles | P1 deferred |
| [#71](https://github.com/gbw30/PantryPulse/issues/71) | Organization/site-scoped roles beyond the single demo presenter | P1 deferred |
| [#72](https://github.com/gbw30/PantryPulse/issues/72) | Fuller multi-period research and endogenous-weighting design/validation | P1 deferred |
| [#73](https://github.com/gbw30/PantryPulse/issues/73) | Richer routing beyond the bounded given-route/single-batch model | P1 deferred |

The five deferred items come from V5 §2.2 and the forecasting enhancement roadmap. They track future scope without scheduling implementation, changing current policies or resuming supplier/model/hosting work. Existing #59–66 already cover saved assumptions, mobile hierarchy, explanations, browser acceptance, CI and committed-source integration; no duplicate PBIs were added.

## Recommended next sequence

1. Resolve **#67/#68** together with #11/#65. Preserve applied migration history and later accepted operational decisions.
2. Finish **#9/#22/#29/#64**, then authoritative stock/operational adapters **#65**. Reuse the delivered core and worker foundation.
3. Repair committed gate wiring and activate actual CI under **#41/#63**; qualify the combined branch candidate.
4. Complete ready UI items **#59–61**, then acceptance **#62** and connected-source journey **#66**.
5. Finish broader operational screens, data qualification and release checks under **#36/#38–44/#47**. Supplier #45 and Chronos #46 remain paused; P1 items remain deferred.

Research claims remain bounded to `EGP_PI_INSPIRED` on simulated institutional attributes. Neither changed allocations nor successful native tests establish real-world fairness or poverty outcomes.
