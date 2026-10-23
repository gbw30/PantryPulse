# PantryPulse acceptance matrix

Initial status for every row: NOT RUN. Suggested test names are implementation targets; the kit does not claim those app tests already exist. Keep the final matrix in Git with evidence links/commit IDs.

| Requirement | Required evidence | Suggested owner |
|---|---|---|
| FR-01 sites | API and E2E show three named sites and category quantities | Lead/frontend |
| FR-02 stock | Negative/fractional count rejected by API and database constraint | Lead/data |
| FR-03 import | Valid rows accepted; malformed/duplicate/missing rows identify line errors | Forecast |
| FR-04 forecast | Six eligible series × seven dated points; fixed cutoff and series IDs | Forecast |
| FR-05 fallback | Inject actual provider exception/timeout; labeled usable baseline persisted | Forecast/verifier |
| FR-06 projection | Golden arithmetic plus arrivals/outgoing/expiry timing | Forecast |
| FR-07 shortage | Correct first deficit/date/category; not confirmed-shortage language | Forecast/frontend |
| FR-08 uncertainty | Quantile order/null behavior and visible method label; no fabricated coverage | Forecast/frontend |
| FR-09 scenario | History/forecast hashes unchanged; validated overrides persisted | Solver/data |
| FR-10 optimization | Independent constraint checker, tiny exhaustive oracle and edge fixtures | Solver/verifier |
| FR-11 explanation | Transfer source/destination/category/quantity/benefit/assumptions visible | Frontend |
| FR-12 comparison | Same snapshot/horizon/unit before/after; residual unmet visible | Solver/frontend |
| FR-13 failure | Contradictory hard constraints, UNKNOWN and MODEL_INVALID handled honestly | Solver/frontend |
| FR-14 reset | Scoped demo reset restores known state and main E2E repeats | Lead/verifier |
| FR-15 replay | Saved input reconstructs feasible vector/objective semantics after DB changes | Solver/data |
| FR-16 P1 approval | Revalidation + atomic reservations + 409 competing approvals | Lead/data |
| FR-17 P1 completion | Paired movements + reservation release + duplicate no-op/conflict policy | Lead/data |
| FR-18 P1 evaluation | Chronological holdout/baseline MAE/WAPE/bias; zero-denominator handling | Forecast |
| FR-19 P1 roles | Authz tests match actual roles; no claim from hidden UI alone | Lead |
| FR-20 P2 integrations | Deferred; no live operational integration implied | Human |

Quality gates:

- Quick: web typecheck/lint, API lint and backend correctness tests. Target <=120 seconds total; measure and keep Stop's outer timeout above the actual total. If the quick suite grows, select a meaningful invariant/fallback subset for Stop and keep the full backend suite in CI.
- Full: quick + frontend unit/build, canonical contract drift and real fresh-DB migration test.
- E2E: Chromium judge flow against running frontend/API/isolated PostgreSQL; assert shortage/plan/scenario result changes, reset and actual error behavior.
- Visual: real screenshots at three viewports plus keyboard/reduced-motion observations and human taste acceptance.
- Release: full/E2E/visual + deployed URL smoke, cold/fallback path and five reset runs.

No global line-coverage target substitutes for these tests. One property test that catches invented inventory is more useful than many assertions mirroring the implementation. Vitest covers scenario dirty/applied state, stale-response ordering, semantic labels and a meaningful error interaction. Playwright covers the complete user story, not pixel snapshots alone. Use database transactions/concurrency tests for mutation semantics; unit mocks cannot establish atomicity.

Evidence fields: acceptance ID, source SHA/fingerprint, environment/dataset version, command, timestamp, pass/fail/unverified, artifact path and reviewer. Do not reuse a green record after source/config/input changes. A known-good committed baseline is valuable but does not validate an untested merge.
