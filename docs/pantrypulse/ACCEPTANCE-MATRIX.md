> **October 25, 2026 approved integration:** [Connected OR integration](../optimization/CONNECTED-INTEGRATION.md) supersedes conflicting OR-only/no-proxy guidance and earlier solver limits for the connected simulated application. Historical checkpoint evidence remains scoped to its original code and contracts.

# PantryPulse acceptance matrix

> **Current authority (2026-11-04):** [V1-SPEC](V1-SPEC.md) §13 defines v1 acceptance; [SPEC-V5](SPEC-V5.md) §16 still governs everything V1-SPEC does not change. The FR/SPEC rows further down are the historical planning matrix, kept for traceability; the v1 disposition table says what happens to each.

## V1 acceptance (current)

Full criteria and evidence are in [V1-SPEC §13](V1-SPEC.md#13-acceptance-criteria). Every row starts at NOT RUN. PASS needs evidence for the exact commit and environment. Skipped, mocked or fixture-only checks don't count.

| ID | Requirement (short) | Suggested owner | Status | Replaces / traces |
|---|---|---|---|---|
| V1-A01 | Clean `git clone` + `docker compose up` on Windows 11 and Ubuntu 24.04 reaches login | Lead/human | NOT RUN | V5-A18 |
| V1-A02 | Only web port published; `PP_WEB_PORT`; data survives restart; seed not duplicated | Lead | NOT RUN | — |
| V1-A03 | Full journey with no keys; only Census egress after install | Lead/verifier | NOT RUN | — |
| V1-A04 | Generated local login; password never in logs/Git/bundle; auth + CSRF enforced | Lead | NOT RUN | V5-A13 |
| V1-A05 | Two fictional Florida sample networks, offline, no real brands, freshly dated | Solver/data | NOT RUN | FR-01, FR-14 (seed part) |
| V1-A06 | Every template: blank copy, example from sample, in-app column guide | Frontend/data | NOT RUN | — |
| V1-A07 | Import rejects each error class with file/line/column/reason; nothing saved | Lead/data | NOT RUN | FR-02, FR-03 |
| V1-A08 | Blank demand stays missing; `sales` basis labeled; exact batch round-trip | Forecast/data | NOT RUN | V5-A02 |
| V1-A09 | Max-envelope bulk import as durable job with progress; measured time | Lead/data | NOT RUN | — |
| V1-A10 | Census geocode + ACS attributes with source/year; outage/unmatched handling; EGP blocked on unknowns | Lead/data | NOT RUN | — |
| V1-A11 | Straight-line default; BYO Google key cached/labeled/never exposed; `routes.csv` override | Lead/data | NOT RUN | — |
| V1-A12 | Seven dated points with provider/fallback; backtest WAPE/bias or "not evaluated" | Forecast | NOT RUN | FR-04, FR-05, FR-08, FR-18, V5-A04–A06 |
| V1-A13 | Danger ranking equals independent calculation; no cross-unit sums; table alternative | Frontend/forecast | NOT RUN | FR-07 |
| V1-A14 | Pantry: five methods, both transfer modes, verifier on every result | Solver/verifier | NOT RUN | FR-10, FR-12, FR-13, SPEC-11.6 (D08), V5-A09–A11 |
| V1-A15 | Retail: three methods in units and USD; optimized matches hand oracles | Solver/verifier | NOT RUN | — (new objective) |
| V1-A16 | Action/why/effect; effect equals remove-one re-projection; export with hash; no stock change | Frontend/solver | NOT RUN | FR-11, FR-15, OPEN-02 |
| V1-A17 | 100 × 500 forecast + comparison per mode within ceilings; peak RAM/CPU recorded | Solver/forecast | NOT RUN | V5-A12 |
| V1-A18 | Newcomer completes the README journey on Windows 11 and Linux | Lead/human | NOT RUN | V5-A15 |
| V1-A19 | README hardware requirements come from measured runs | Lead | NOT RUN | — |
| V1-A20 | New screens pass keyboard/axe/reduced motion at three viewports | Frontend/ux-critic | NOT RUN | V5-A17 |
| V1-A21 | Vitest (group A) and `test:docker` (group B) in CI; story coverage maps every V1-A ID | Lead | NOT RUN | — |
| V1-A22 | Existing backend/config/full/connected e2e gates green, zero skips | Verifier | NOT RUN | V5-A01, V5-A07, V5-A08 |
| V1-A23 | `inbound.csv` arrivals counted once; donations 0 vs missing; donation forecast shown, not used as supply | Forecast/solver | NOT RUN | V5-A02, V5-A03 |
| V1-A24 | `--build` from clean clone; after authorized release, plain `up` pulls images; first-run times recorded | Lead/human | NOT RUN | — |

## Historical rows: v1 disposition

| Historical row | v1 disposition |
|---|---|
| FR-01 sites (three named sites) | Superseded: user-imported networks plus sample networks → V1-A05/A07 |
| FR-02, FR-03 | Covered by V1-A07 (template import replaces general CSV import) |
| FR-04–FR-08 | Covered by V1-A12/A13 |
| FR-09, FR-15 | Retained via V1-A22 (existing scenario/replay gates) and V1-A16 |
| FR-10, FR-12, FR-13 | Covered by V1-A14/A15 |
| FR-11 | Covered by V1-A16; OPEN-02 resolved for v1 as a remove-one counterfactual |
| FR-14 reset | v1 "start over" = `docker compose down -v` (V1-SPEC §7); scoped in-app reset deferred |
| FR-16, FR-17 (P1 approval/completion) | Deferred to v2 or later (V1-D02: plan export only) |
| FR-18 evaluation | Partly in v1 as the per-network backtest (V1-A12); model selection deferred |
| FR-19 roles | Deferred; single local presenter (V1-A04) |
| FR-20 integrations | Deferred |
| SPEC-11.6 baselines (D08) | In v1: no-transfer, equal-share, most-urgent-first (Pantry) and soonest-expiry-first (Retail) → V1-A14/A15 |
| SPEC-9.7 model selection (D09) | Deferred (V1-SPEC §11) |
| SPEC-13.5 observability/audit | Unchanged requirement; not a v1 gate beyond V1-A04's log check |
| SPEC-8.1 status codes | Retained via V1-A22 |
| SPEC-8.6 shortage response | Superseded for v1 by V1-A13 (danger ranking + first deficit) |
| SPEC-7 schema columns | Superseded; v1 schema follows V1-SPEC §6.1 templates |
| V5-A14 supplier proposals | Deferred to v2 by V1-D07 (scope amendment) |

## Historical matrix (V4/V5 era)

> Historical planning matrix. V5 section 16 is the consolidated V5 acceptance matrix.

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

- Quick: web typecheck/lint, API lint and backend correctness tests. Current complete quick-gate budget is 600 seconds with a 360-second backend timeout; measure and keep Stop's outer timeout above the actual total. If the quick suite grows, select a meaningful invariant/fallback subset for Stop and keep the full backend suite in CI.
- Full: quick + frontend unit/build, canonical contract drift and real fresh-DB migration test.
- E2E: Chromium judge flow against running frontend/API/isolated PostgreSQL; assert shortage/plan/scenario result changes, reset and actual error behavior.
- Visual: real screenshots at three viewports plus keyboard/reduced-motion observations and human taste acceptance.
- Release: full/E2E/visual + deployed URL smoke, cold/fallback path and five reset runs.

No global line-coverage target substitutes for these tests. One property test that catches invented inventory is more useful than many assertions mirroring the implementation. Vitest covers scenario dirty/applied state, stale-response ordering, semantic labels and a meaningful error interaction. Playwright covers the complete user story, not pixel snapshots alone. Use database transactions/concurrency tests for mutation semantics; unit mocks cannot establish atomicity.

Evidence fields: acceptance ID, source SHA/fingerprint, environment/dataset version, command, timestamp, pass/fail/unverified, artifact path and reviewer. Do not reuse a green record after source/config/input changes. A known-good committed baseline is valuable but does not validate an untested merge.
