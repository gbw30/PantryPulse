# PantryPulse delivery board

Update after each integration, not after each agent thought. All initial statuses are TODO; no application has been built by this kit.

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

P1 reservations/completion are separate tickets only after all P0 rows are accepted. No worker may claim a shared foundational file without a lead assignment.
