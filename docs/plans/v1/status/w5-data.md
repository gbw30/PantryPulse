# Status — `w5-data`

**Lane:** `w5-data` · **Branch:** `lane/w5-data` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-D01 | done | `cb3fd6f`, fix `f698843` | `uv run --frozen pytest -q tests/optimization/test_scenario_donations.py tests/networks/test_build_scenario.py tests/danger/test_ranking.py tests/optimization/test_actions.py tests/optimization/test_export.py tests/test_w5_contract.py` (`.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) → 200 passed, 0 skipped; whole API suite `uv run --frozen pytest -q` (same env) → 2228 passed, 0 skipped |
| W5-D02 | done | `3741685` | RED seen: hub/DC rows accepted, guide silent, bench bound 4,500,000. `uv run --frozen pytest -q tests/imports/` → 202 passed, 0 skipped (incl. `test_bench_import.py`: `test_small_bench_writes_phase_seconds_and_peak_rss` and the new `test_rows_stop_at_what_the_generator_can_write`). Whole API suite `uv run --frozen pytest -q` (`.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) → 2263 passed, 0 skipped, 0 failed |
| W5-D03 | done | `cc9c46b` | RED seen (`evaluated` with null WAPE). `uv run --frozen pytest -q tests/forecasting/test_backtest.py tests/imports/` → 211 passed, 0 skipped |
| W5-D04 | done | `fea2ec0` | RED seen (`DID NOT RAISE AccessError` for done and failed). Same command → 211 passed, 0 skipped |
| W5-UI04 (data side) | done | `8691c72` | Gabriel's decision (2026-11-12, via orchestrator): the `basis` guide names the three places the sales label shows after polish's UI04 ("the Forecast trust panels, the danger ranking and the site inspector"), never "everywhere". RED seen (`test_guide_states_single_timezone_and_blank_capacity_rule`, old wording). `uv run --frozen pytest -q tests/imports/` → 202 passed, 0 skipped |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (after the v1-local merge `abe117d` and W5-UI04) | `3d193ff` | PASS (web typecheck, web lint, api lint, api tests) |
| `node scripts/quality/run.cjs full` (`.env.lane` + `PP19_TEST_SCHEMA_ISOLATION=1`), PR candidate | `3d193ff` | PASS 8/8 (`full.json`: pass true, head `3d193ffd`, source unchanged; load ~7–10). Later commits touch only this file. |
| `node scripts/quality/run.cjs quick` | `c63d436` | PASS (web typecheck, web lint, api lint, api tests) |
| `node scripts/quality/run.cjs full` (`.env.lane` + `PP19_TEST_SCHEMA_ISOLATION=1`) | `f75da9a` | PASS 8/8 (`.claude/state/quality/full.json`: pass true, source unchanged). The gate prints no counts; the API suite on the same code (`3741685`, which differs only in this file) gave 2263 passed, 0 skipped, 0 failed. |
| `/devkit:ship-check` | `f75da9a` | Step 1: the full gate above. Step 2: project `verifier` on D02–D04, PASS WITH NOTES (below). Step 3: security-guidance isn't installed in this session, skipped. Steps 4–5: the PR waits until D01 merges into v1-local (orchestrator); `/code-review` runs once the PR exists. Step 6: no auth, payment, migration or permission change, skipped. |

Earlier runs that don't count: a full gate on `f75da9a` failed once at web unit tests. `decisions-view.test.tsx` "selecting 700 actions …" timed out at 5 s with machine load ~25 from other sessions. This lane doesn't touch `apps/web`, and the test passed 3/3 alone. A second run without `PP19_TEST_SCHEMA_ISOLATION` passed but doesn't count (PP19 suites skipped).

### Verifier on D02–D04 (`f75da9a`): PASS WITH NOTES
- Revert checks: D02 reverted gives 5 failed; D03, 2 failed; D04, 2 failed. The guard tests (hub donations, insufficient history, Retry) pass either way.
- Its own edge cases held: mixed-case `Hub`/`DISTRIBUTION_CENTER`, a hub row with other errors too, an unknown ID (only `UNKNOWN_ID`), pooled zero plus nonzero, units kept apart, a blank window staying `insufficient_history`. No in-repo producer writes hub/DC demand (10 fixture folders, both sample generators).
- Medium (web, not this lane): the D03 copy in `trust-panel.tsx`; already routed to w5-screens.
- Low (by design): a same-key replay on a done run is now 409, not 202. The web shows Retry only for `uploading` with no job.
- Info, left as is: in Pantry mode a `distribution_center` row, already refused for its type, also gets the hub/DC demand error. That file is already rejected, so it's only extra noise.
- Command: `uv run --frozen pytest -q -rs tests/imports/test_validation.py tests/imports/test_templates.py tests/imports/test_bench_import.py tests/forecasting/test_backtest.py tests/imports/test_import_job.py` → 156 passed, 0 skipped.

## D01 verification (orchestrator, 2026-11-12): PASS WITH NOTES

- F1 (Medium), fixed in `f698843`: a window donation sum above 100,000 raised in `decimal_literal` (500 on actions/export). The failing test came first; the total is now formatted as the exact Decimal.
- F3 (Low), added in `f698843`: `test_donations_never_change_a_result_projection_or_effect`, 22 cases (5 or-v3 fixtures plus bench 14×10, every method of the mode). It checks that the projection, the whole `MethodResult` and every action's text and effect stay unchanged with 1,000/day donations everywhere.
- F2 (Low): note under Gotchas.
- Evidence: `uv run --frozen pytest -q tests/optimization/test_scenario_donations.py tests/optimization/test_actions.py tests/optimization/test_export.py` → 161 passed, 0 skipped.

## Regenerated golden files

- `apps/api/tests/networks/fixtures/mini-network/expected-scenario.json` and `expected-hash.txt` (W5-D01): the mini network's forecast fixture has one available P1 × RICE donation series, so the frozen scenario now carries `donations` and its hash changes (`9201bdb1…` → `d3caf76c…`). There is no generator script for this golden (W1-D09 wrote it from the test's own output); it was regenerated from the old file plus the one `donations` row the real `build_scenario` output added (the only diff `test_golden_mini_network_scenario_hash` reported), then checked by that test against a real PostgreSQL build.
- `expected-scenario-pre-w5.json` and `expected-hash-pre-w5.txt` (new, same folder): byte copies of the golden as frozen before W5-L01. The lead's `test_w5_contract.py::test_stored_mini_network_scenario_keeps_its_golden_hash` now reads these, so it still proves a scenario stored before W5-L01 keeps its hash.
- `data/demo/or-v3/*`: unchanged. They are hand-derived inputs with no `donations` (empty donations are omitted from dumps, so their hashes hold). The new donation tests add rows in the test instead.

## Decisions made inside the lane

- **Why text: whose donations, over which days (W5-D01).** The why names the **receiver's** donation forecast for the action's product, summed over the same days as its projected unmet (the Pantry window, or all 7 days in Retail), with the period stated: "At Pantry 1, expected donations (forecast, not confirmed): 1.5 cases over 2 days, not counted as supply." Without a forecast: "Pantry 1 has no donation forecast." The sender's donations are not named: the why is about the receiver's need, and every hub would otherwise read "no donation forecast". The sum is exact (decimal), not rounded up per day as demand targets are, so it never overstates expected help. Easy to change if the orchestrator reads "each location" as both ends.
- **Basis on projections (W5-D01).** `basis` comes from the frozen demand row, so a product with no available forecast (unknown target) and a hub/DC with no demand series both read `None` (the contract's "unknown or not applicable"). A danger row takes its driving product's basis; a Retail DC ranked on expiry has none.
- **Hub/DC demand rows (W5-D02)** use the existing `MALFORMED` code (as a route into a hub does), so no contract change. Donation history at a hub stays allowed (a hub can receive donations).
- **D03:** only Σactual = 0 gets a reason (`sum_actual_zero`); `not_evaluated_insufficient_history` keeps `reason = None`, because its status already says why. A not-evaluated zero-actual score still reports its scored points and origins.
- **D04:** the check is on the **stored** phase. A run whose job stopped before finishing still reads `staging`, so the web's Retry (commit the same run again) keeps working; a test pins it.

## Gotchas

- **Replay flake `test_actions.py::test_actions_equal_the_full_network_replay[bench-retail-RETAIL_OPTIMIZED-receiving-None]` (seen once by w5-screens at load ~27): not reproduced, no fix made.**
  - The solve is CP-SAT with 1 worker, seed 0 and a **wall-clock** limit of 5 s per product (`retail.py:40-42`, `methods.py:47`). The whole bench 14×10 method takes 0.23 s here.
  - Forcing a short limit does give the suspected failure: 0.05 s still verifies (some products FEASIBLE), but ≤ 0.005 s returns UNKNOWN with `NO_SOLUTION:P002,P006,P007,P009`, no plan, and the assert at line 282 fails.
  - Reaching that from 5 s needs a slowdown of more than 20×. Under 32 busy loops on 16 cores (load ~29), all 30 bench-retail replay cases passed twice, at about 150 s a run, and once more after the load stopped.
  - Not changed: a deterministic limit (`max_deterministic_time`) isn't exposed by `run_method`, so it would need a production solver change, which is out of scope. Raising the test's `search_seconds` would only hide an unconfirmed cause.
  - The assert already prints `result.failure_reason`. A `NO_SOLUTION:…` there confirms a timeout; anything else points elsewhere (for example a FEASIBLE plan that `saturated(…, "receiving")` doesn't expect). The captured failure output is the next step.

- **Donation literals share demand's 100,000-per-day cap (verifier F2, note only):** `scenario.py` parses donation points with `decimal_literal`, so a donation forecast over 100,000 per day blocks freezing the scenario, the same limit demand has. The why's **sum** is not capped (F1 fixed in `f698843`).

- `tests/networks/test_build_scenario.py`'s fixture forecast job capped its output at 10,000 bytes; six series exceed it (`OUTPUT_TOO_LARGE`). Raised to 100,000 for the donation tests.

## Change requests

### CR-w5-data-1 — the bench import must not write demand history for hubs
- **File(s):** `apps/api/scripts/bench_import.py` (lead-only; `scripts/` isn't a lane path)
- **Exact change:** in `_rows`, make one hub and give demand only to pantries. The locations line becomes `{'hub' if i == 0 else 'pantry'}`, and the demand pairs become `pairs = ((i, p) for i in range(1, LOCATIONS) for p in range(PRODUCTS))`. Update the `--rows` help to "demand_history rows (at most 4,455,000: 99 pantries × 500 × 90; a hub has no demand history, W5-D02)". Alternative: keep 5 hubs and start at `range(5, LOCATIONS)` (at most 4,275,000).
- **Why:** W5-D02 refuses `demand_history` rows for hubs and DCs (W4 decisions §10). Today the generator writes rows for L000–L004, which are hubs, so `test_bench_import.py::test_small_bench_writes_phase_seconds_and_peak_rss` fails with `generated files did not validate: … L000 is a hub …`. The 4.5 M envelope (100 × 500 × 90) can no longer be reached by a network that has a hub; whether V1-SPEC §5.1's figure needs a note is the lead's call. W5-PK04 (bulk-import measurement) uses this bench.
- **Unblocks:** W5-D02.
- **Status:** approved (Gabriel, 2026-11-12) as a one-time exception: the lane makes the change inside its D02 commit. Done in the W5-D02 commit (see the task row): one hub (`'hub' if i == 0`), demand pairs over `range(1, LOCATIONS)`, and `MAX_ROWS = 4,455,000` used for the `--rows` default, bound and error text, plus the usage line in the docstring. Nothing else in the script changed.

### CR-w5-data-2 — the import page should read the run when a commit answers IMPORT_ALREADY_FINISHED
- **File(s):** `apps/web/src/components/import/import-view.tsx` (w5-polish / w5-screens / lead; not this lane)
- **Exact change:** in `commit()` (`import-view.tsx:143-149`), before the 4xx branch, add `if (error instanceof ApiError && error.code === "IMPORT_ALREADY_FINISHED") return track(importId);` so that a finished run is shown as it is (done, or failed with its row errors) instead of "Import request failed … Nothing was saved." Add a unit test: commit rejects 409 `IMPORT_ALREADY_FINISHED`, status reads `done`, and the page shows the finished import.
- **Why:** W5-D04 (`fea2ec0`) answers 409 for a run stored done or failed.
  - The plain lost-response path is unaffected. The web never resends a commit by itself: on no answer or a 5xx it reads the run (`track`, `import-view.tsx:149`). Each commit sends a fresh random key (`network-api.ts:29` passes none), and the API ignores the caller's key anyway: its queue key comes from the run (`imports/api.py`).
  - One path does change. A commit that got no answer is admitted, but its phase write is lost. After 30 checks the page shows "didn't start" with Retry. The admitted job later records itself (`repositories/imports.py:87-91`, `set_job_phase`) and finishes. A Retry clicked on that stale page used to get 202 with the same job and be tracked to its real end. Now it gets 409 and the page wrongly says nothing was saved.
- **Why keep the 409 (not 202 for a finished run):** the decision (W4 §7, wave-5 W5-D04) is that a done or failed run is refused, admits no job and keeps its phase. A 202 would have to name the run's old job, which for a failed run may be the cancelled job, and would still read as "accepted". The 409 with its own code tells the client exactly what happened, and reading the run gives it the outcome. The fix belongs in the client's handling of that code.
- **Unblocks:** nothing in this lane; it closes a W5-D04 integration edge before release.
- **Status:** approved (Gabriel, 2026-11-12); w5-polish implements it (`import-view.tsx`, with a unit test keyed on `IMPORT_ALREADY_FINISHED`). v1-local carries the edge briefly, between this lane's merge and polish's, and it is fixed before the W6 release candidate.

## Notes for other lanes (read-only for me)

- **W5-D03 → web:** (approved 2026-11-12: `w5-screens` adds the `not_evaluated_zero_actual` branch before D03 reaches v1-local.) `apps/web/src/components/data-explorer/trust-panel.tsx:64-72` shows `NOT_EVALUATED` ("accuracy not evaluated: needs 35+ days") for every non-`evaluated` status. After D03, a series whose scored actuals sum to 0 arrives as `not_evaluated_zero_actual` with `reason: sum_actual_zero`, so it would read "needs 35+ days" (wrong) where it showed `NOT_MEASURABLE` before. The panel needs a branch for this status, e.g. the existing NOT_MEASURABLE copy. W5-UI04/UI05 (`w5-polish`) or the lead should decide; merge both together.
- **W5-D01 → W5-UI04:** `DangerRow.basis` and `ProductProjection.basis` are now filled (`demand` | `sales` | null). The why text carries the donation sentence as plain text, so the web needs no change for it.

## Escalations

None.
