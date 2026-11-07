> **October 25, 2026 approved integration:** [Connected OR integration](../optimization/CONNECTED-INTEGRATION.md) supersedes conflicting OR-only/no-proxy guidance and earlier solver limits for the connected simulated application. Historical checkpoint evidence remains scoped to its original code and contracts.

# PantryPulse delivery board

Current source includes the baseline API/presenter flow (PR #75), connected OR comparisons/UI and executable Linux/browser CI (PR #76), plus the bounded compute setup reviewed in PR #77. See [CURRENT-STATUS.md](CURRENT-STATUS.md), [SPEC-V5](SPEC-V5.md) and [PR #77 review](PR-77-REVIEW.md). The planning/task rows below retain their recorded historical status and do not override subsequent integrated evidence.

## v1 waves (current, 2026-11-04)

The plan is [docs/plans/v1/](../plans/v1/README.md), which implements [V1-SPEC](V1-SPEC.md). Protocol: [ORCHESTRATION.md](../plans/v1/ORCHESTRATION.md). The orchestrator (lead) keeps this table current. Lanes report only through their own `docs/plans/v1/status/<lane>.md`.

| Wave | Lanes (at most 3) | Mode | Tasks | Acceptance IDs | Status |
|---|---|---|---|---|---|
| W0 Foundation | orchestrator (spikes S1, S4 in-session) | orchestrator + A | W0-01…W0-10 | A02, A04, A21, A22 (+ S1/S3/S4 findings) | DONE: `w0/foundation` (`39c50e8`) merged into v1-local as `3909010` (PR #102, 2026-11-06). W0-06 S3: Windows + WSL clean clones pass (`spikes/S3-docker.md`); W0-10: verifier reviews, or-input-v3 validator fix `428d014`, Codex review fixes `a5a182c`/`0195c0b`, atomic import `ppv1_0010` (`05a1351`), doc conflicts with V1-SPEC resolved (`1137a68`), spike findings applied to wave-1/3. CI: 1413 backend + 154 e2e passed. `ListAgents` lists peer local sessions (checked 2026-11-07); lane visibility is confirmed at W1 launch |
| W1 | `w1-data`, `w1-solver`, `w1-web` | B | W1-D01…D09, W1-S01…S07, W1-W01…W08 | A06–A11, A13–A17, A20, A21, A23 | IN PROGRESS since 2026-11-07 (base `3909010`; lanes reachable through `SendMessage`). Lead CRs on `w1/cr-scenario-window-policy`, approved by Gabriel 2026-11-07: CR-w1-solver-1 window/policy in or-input-v3 (`4e77ab0`), CR-w1-solver-3 `ppv1_0011` v3 tables (`b86b5a7`), CR-w1-data-2 publisher prepare/discard hook (`0c6c617`), CR-w1-web-1/2/3 locations read + forecast-run and projection contracts (`234a70f`), CR-w1-data-1 bundled ACS tract table (`399cf6b`), W1-D08 Google key passed only to the step child via `Registration.child_secrets` (`afeb023`), CR-w1-data-3 enrichment.v1 advertised (lane-side, `f4f7ce2`). Full gate PASS at `afeb023`. CR-w1-solver-2 (Retail USD value-weighted split) is lane-owned. Lead calls: hubs always route candidates; comparison_id = job_id |
| W2 Integrate W1 | orchestrator | orchestrator + A | W2-01…W2-06 | A22 + backend journey | NOT STARTED |
| W3 | `w3-forecast`, `w3-samples`, `w3-web` | B | W3-F01…F06, W3-P01…P04, W3-W01…W03 | A02, A05, A06, A08, A12, A13, A17, A20, A23 | NOT STARTED |
| W4 Integrate W3 | orchestrator | orchestrator + A | W4-01…W4-04 | full connected journey, A20 review | NOT STARTED |
| W5 | `w5-polish`, `w5-packaging` | B | W5-UI01…UI03, W5-PK01…PK05 | A03, A04, A09, A17–A21, A24 | NOT STARTED |
| W6 Release | orchestrator + Gabriel | orchestrator + A | W6-01…W6-06 | A01, A18, A22, A24 | NOT STARTED |

W0 handoff (2026-11-04):
- **Decisions:** `docs/plans/v1/decisions/` (network model and login table, per-product optimizer). Spike reports: `docs/plans/v1/spikes/` (S1, S4).
- **W0-05 (done, `9e14797`):** login hash in `local_logins`, password only in `.pantrypulse/local-login.txt`; proxy token via a shared read-only volume (`PP_TRUSTED_PROXY_TOKEN_FILE`). Also fixed: the insecure-cookie guard now checks the verified browser origin (compose login returned 503).
- **W0-08 (done, 2026-11-06):** `6b18bc2` decisions, `28d180c` streaming proxy, `6c605b5` v1 API surface (08a), `a6fd470` job kinds, examples, generated contract (08b). [Decision record](../plans/v1/decisions/W0-08-scenario-and-import.md).
  - Gabriel's calls: `or-input-v3` with v2 untouched; S4 create → upload → commit import routes; v1 forecasts and comparisons under `/networks/{id}`; 501 in the existing error envelope; new `IMPORT`/`ENRICHMENT` job kinds (migration `ppv1_0009`).
  - Evidence: `node scripts/quality/run.cjs full` PASS at the 08b tree (second run). The first run failed once on `tests/workers/test_process_driver.py::test_orphaned_group_from_a_dead_parent_is_found_and_killed_by_identity`, which passed 5/5 alone and isn't touched by W0. It's load-sensitive and should be looked at in W0-10. Config tests 30/30. v2 OpenAPI paths and schemas are unchanged against the previous `openapi.json`.
  - The Next standalone server streams uploads: `apps/web/scripts/check-upload-streaming.mjs`, sink first byte after 1 MiB of 150 MiB.
- **W0-10:**
  - verifier review of the branch and of the S1 capacity split;
  - reword W1-S05's "decomposed equals monolithic" test;
  - before the merge, a doc pass against `7067b0b` (no bloat, better agent context retrieval) that also removes the personal vault references from the committed plan and prompts.
- **Test environment:** `PP_TEST_DATABASE_URL` and `PP19_TEST_DATABASE_URL` set to `postgresql+psycopg://pantrypulse:isolated_test_only@127.0.0.1:55433/pantrypulse_test`, with `PP19_TEST_SCHEMA_ISOLATION=1`.

Gates: Gabriel approves each wave start, every change request, every merge into `v1-local`, and every release action. The re-plan gate is W0-10.

## Historical rows

| ID | Outcome | Owner | Depends on | Exit evidence | Status |
|---|---|---|---|---|---|
| PP-01 | Confirm repo, rules, deadline and P0 | Lead/human | none | Scope and decision log | TODO |
| PP-02 | Canonical domain and API contracts | Lead | PP-01 | OpenAPI and fixtures | TODO |
| PP-03 | Schema and initial migration | Lead | PP-02 | Fresh DB migration test | TODO |
| PP-04 | Demo seed/reset and provenance | Solver/data | PP-03 | Scoped reset test | TODO |
| PP-05 | Tokens and dashboard composition | Frontend/human | PP-01 | Chosen screenshot direction | TODO |
| PP-06 | CI and preview skeleton | Lead | PP-02,03 | Reachable web/API/DB | TODO |
| PP-07 | Sites/inventory/adjustments | Lead/API | PP-03 | Nonnegative/version tests | TODO |
| PP-08 | CSV demand validation | Forecast | PP-02,03 | Row errors/duplicate/null tests | TODO |
| PP-09 | Seasonal-naive provider | Forecast | PP-08 | Seven dated points | TODO |
| PP-10 | Lost-sales inventory projection | Forecast | PP-09 | Golden arithmetic tests | TODO |
| PP-11 | Chronos adapter and failure fallback | Forecast | PP-09 | Actual provider metadata | TODO |
| PP-12 | Independent transfer feasibility checker | Solver | PP-02 | Edge fixtures | TODO |
| PP-13 | OR-Tools allocation | Solver | PP-10,12 | Golden/invariant tests | TODO |
| PP-14 | Immutable scenario and plan persistence | Solver | PP-13 | Replay and snapshot test | TODO |
| PP-15 | Dashboard and site detail integration | Frontend | PP-07,10 | Real API screenshots | TODO |
| PP-16 | Forecast/uncertainty views | Frontend | PP-11,15 | Labels and chart alternative | TODO |
| PP-17 | Plan explanation and comparison | Frontend | PP-14,15 | Same-horizon comparison | TODO |
| PP-18 | Scenario controls and replan | Frontend | PP-14,17 | Stale-response test | TODO |
| PP-19 | Main Playwright judge journey | Verifier/lead | PP-18 | Actual state-change assertions | TODO |
| PP-20 | Visual/motion/accessibility repair | Frontend | PP-19 | Critic and human review | TODO |
| PP-21 | Adversarial audit and fixes | Reviewer/lead | PP-19 | P0 coverage matrix | TODO |
| PP-22 | Release/rollback and five rehearsals | Lead/human | PP-20,21 | Release evidence + backup | TODO |
| PP-23 | Submission assets | Lead/human | PP-22 | Rules-specific checklist | TODO |
| PP-24 | BE-01 transfer mode and method types (#1) | Lead | none | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-25 | BE-02 mode-dependent route predicate (#2) | Lead | PP-24 | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-26 | BE-03 daily demand rounding (#3) | Lead | none | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-27 | BE-04 fixed-point floor primitive (#4) | Lead | none | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-28 | BE-05 native solver-status gate (#5) | Lead | none | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-29 | BE-06 history alignment without imputation (#6) | Lead | none | Unit tests + verifier at a3f44c1 | MERGED; independent review pending |
| PP-31 | WQ-01 internal job contracts and pure policies | Lead | none | Pure tests (WQ-T01–T04) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| PP-32 | WQ-02 jobs-only migration and queue repository | Lead | PP-31 | Isolated PostgreSQL tests (WQ-T05–T10, T19–T21, T27) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| PP-33 | WQ-03 supervisor ownership/heartbeat/recovery | Lead | PP-32 | Supervisor tests with fake boundary (WQ-T08, T11, T13, T22) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| PP-34 | WQ-04 Linux process driver and containment | Lead | PP-31 | Linux real-process tests (WQ-T12, T14, T23) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| PP-35 | WQ-05 fenced publication and commit reconciliation | Lead | PP-32 | PostgreSQL tests (WQ-T18–T20) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| PP-36 | WQ-06 PostgreSQL + supervisor + test-job vertical slice | Lead | PP-32–35 | Linux slice with real supervisor SIGKILL (WQ-T10–T15, T21, T22) | PR #52 foundation; reviewed and regression-tested (see PP-31 packet) |
| [PP-45](tasks/PP-45.md) | Persisted baseline forecast API (#29) | VaishnaviPhadtare | Operational history + shared worker foundation | 817 unit / 44 PostgreSQL checks; generated contracts / proxy / real pooled-Neon HTTP smoke | Local VP implementation; Linux live-worker smoke, independent review and OR convergence remain open |

| [VP inventory](tasks/PP-46-vp-inventory.md) | Authenticated current inventory snapshot API | VaishnaviPhadtare / lead | Operational schema + presenter access | 824 non-integration tests passed (11 Linux skips); 5 isolated PostgreSQL/HTTP tests; 2 proxy tests; Ruff, web types/lint and contract drift passed | Implemented locally on VP; independent release review and UI data binding remain open |

| [PP-47](tasks/PP-47.md) | Audited existing-lot adjustment HTTP API | VaishnaviPhadtare / lead | Stock service + PP-46 + presenter access | 848 non-integration tests passed (11 Linux skips); 14 PostgreSQL/HTTP tests (9 adjustment + 5 snapshot); 3 proxy tests; Ruff, web types/lint and contract drift passed | Implemented locally on VP; receipt creation/posting API, UI binding and independent release review remain open |

| [PP-49](tasks/PP-49.md) | Remaining operational and planning APIs | VaishnaviPhadtare / lead | PP-45–48 | 856 backend checks, native solving, isolated PostgreSQL checks, 21 migration checks, two final planning checks and real HTTP read smoke; see task packet | Implemented on VP; supervised Linux worker, UI binding and independent release acceptance remain open |

PP-49 supersedes earlier remaining-work notes about receipt APIs and OR convergence
in PP-45/47/48; their original evidence remains historical.

P1 reservations/completion are separate tickets only after all P0 rows are accepted. No worker may claim a shared foundational file without a lead assignment.

Review-fix integration: PR #51 integrated the PR #49 baseline core and PR #50 design lab with V5 corrections. See tasks/PP-30-pr-review-fixes.md for the bounded task and verification evidence.

## Current integration tasks

Forecasting follow-up: [execution plan and milestones](../forecasting/EXECUTION-PLAN.md)
tracks PBIs [#80–#86](https://github.com/gbw30/PantryPulse/issues?q=is%3Aissue+%22PBI-FC-%22),
assigned to @GestebanFalcon under existing #38 (sources), #40 (evaluation) and #46
(Chronos). All seven now have local implementation/decision evidence pending
review/publication; calibrated improvements remain #70. The
[final dossier](../forecasting/QUALIFICATION.md) records insufficient Chronos
coverage and unchanged defaults. The work uses main through PR #78 and does not
reopen delivered baseline/job/OR infrastructure.

[PP-46](tasks/PP-46.md) implements the approved connected simulated OR flow. Measured evidence and outstanding gates are tracked in [FINALIZATION](../optimization/FINALIZATION.md); historical TODO rows do not override this bounded scope.

PR #77 reconciles local/Fly compute configuration and current documentation, with a 725-second local stop grace and preserved existing runtimes. Fly account/platform/deployment qualification remains separate.

[PP-50](tasks/PP-50-vp-api-review.md) prepares VP API convergence on main, preserving
canonical planning and original migration histories. See [review/evidence](VP-API-INTEGRATION.md).
