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

Source-spec requirements without an FR number (added after the 2026-10-23 audit; see PROJECT-CONTRACT.md):

| Requirement | Required evidence | Suggested owner |
|---|---|---|
| SPEC-11.6 baseline comparison (D08) | Every plan stores no-redistribution, equal-share, greedy and optimized results on one snapshot. The independent checker reports zero violations for each. Deterministic tie-break tests. A two-receiver fixture where equal share or greedy differs from the optimized result, with values derived by hand (the golden fixture alone gives the same 40-meal answer under all three non-zero policies). Replay reproduces the comparison. Demo Scene 6 shows it with simulated labels | Solver/frontend |
| SPEC-9.7 model selection (D09) | With an evaluation where the baseline wins, new runs default to baseline and selection_reason says so. Where Chronos wins, Chronos stays the default. With no evaluation, runs are labeled "accuracy not evaluated". Existing runs are unchanged | Forecast/verifier |
| SPEC-13.5 observability and audit | Structured log entries carry request_id, plus provider/fallback/duration for forecasts, solver status/duration for plans, and expected/actual version for 409s. Audit rows exist for movements, reviews and resets. A test asserts that no secret, connection string, token or raw CSV row appears in captured logs | Lead |
| SPEC-8.1 status codes | API tests per code: 400 malformed body or CSV headers, 403 unauthorized or non-demo reset, 404 unknown IDs, 409 stale version, 422 invalid business input, 500 envelope without internals, and 503 for a provider failure with fallback disallowed while existing reads still return 200 | Lead/forecast |
| SPEC-8.6 shortage response | The GET /shortages contract test asserts first deficit date, quantity with unit, current eligible inventory, inbound supply with included statuses, run/method, planning mode and risk label, for central and conservative modes on the same snapshot | Forecast |
| SPEC-7 schema columns | The migration test asserts site latitude/longitude (nullable) and active, category active, scenario organization_id, forecast run organization_id/data_source_label/evaluation_json/error_message/selection_reason, and plan objective_value. An inactive site is excluded from projection and planning | Lead |

Quality gates:

- Quick: web typecheck/lint, API lint and backend correctness tests. Target <=120 seconds total; measure and keep Stop's outer timeout above the actual total. If the quick suite grows, select a meaningful invariant/fallback subset for Stop and keep the full backend suite in CI.
- Full: quick + frontend unit/build, canonical contract drift and real fresh-DB migration test.
- E2E: Chromium judge flow against running frontend/API/isolated PostgreSQL; assert shortage/plan/scenario result changes, reset and actual error behavior.
- Visual: real screenshots at three viewports plus keyboard/reduced-motion observations and human taste acceptance.
- Release: full/E2E/visual + deployed URL smoke, cold/fallback path and five reset runs.

No global line-coverage target substitutes for these tests. One property test that catches invented inventory is more useful than many assertions mirroring the implementation. Vitest covers scenario dirty/applied state, stale-response ordering, semantic labels and a meaningful error interaction. Playwright covers the complete user story, not pixel snapshots alone. Use database transactions/concurrency tests for mutation semantics; unit mocks cannot establish atomicity.

Evidence fields: acceptance ID, source SHA/fingerprint, environment/dataset version, command, timestamp, pass/fail/unverified, artifact path and reviewer. Do not reuse a green record after source/config/input changes. A known-good committed baseline is valuable but does not validate an untested merge.
