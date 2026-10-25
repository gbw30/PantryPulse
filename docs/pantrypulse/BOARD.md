# PantryPulse delivery board

Update after each integration. [Project specification V5](SPEC-V5.md) records the current implementation/branch state and acceptance. PP-01–23 retain the historical planning board and require reconciliation; PP-24–29 were merged through PR #7. PR #51 integrated the offline forecasting core and design lab; live domain API/database acceptance remains open. PP-31–36 (worker/job queue foundation, [ADR 0005](../architecture/0005-worker-job-queue.md)) are delivered by PR #52; they use test handlers only. No completed application is claimed.

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

| [PP-46](tasks/PP-46.md) | Authenticated current inventory snapshot API | VaishnaviPhadtare / lead | Operational schema + presenter access | 824 non-integration tests passed (11 Linux skips); 5 isolated PostgreSQL/HTTP tests; 2 proxy tests; Ruff, web types/lint and contract drift passed | Implemented locally on VP; independent release review and UI data binding remain open |

| [PP-47](tasks/PP-47.md) | Audited existing-lot adjustment HTTP API | VaishnaviPhadtare / lead | Stock service + PP-46 + presenter access | 848 non-integration tests passed (11 Linux skips); 14 PostgreSQL/HTTP tests (9 adjustment + 5 snapshot); 3 proxy tests; Ruff, web types/lint and contract drift passed | Implemented locally on VP; receipt creation/posting API, UI binding and independent release review remain open |

| [PP-49](tasks/PP-49.md) | Remaining operational and planning APIs | VaishnaviPhadtare / lead | PP-45–48 | 856 backend checks, native solving, isolated PostgreSQL checks, 21 migration checks, two final planning checks and real HTTP read smoke; see task packet | Implemented locally on VP, uncommitted/unpushed; supervised Linux worker, UI binding and independent release acceptance remain open |

PP-49 supersedes earlier remaining-work notes about receipt APIs and OR convergence
in PP-45/47/48; their original evidence remains historical.

P1 reservations/completion are separate tickets only after all P0 rows are accepted. No worker may claim a shared foundational file without a lead assignment.

Review-fix integration: PR #51 integrated the PR #49 baseline core and PR #50 design lab with V5 corrections. See tasks/PP-30-pr-review-fixes.md for the bounded task and verification evidence.
