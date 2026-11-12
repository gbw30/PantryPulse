# Status — `w5-data`

**Lane:** `w5-data` · **Branch:** `lane/w5-data` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-D01 | done | `cb3fd6f` | `uv run --frozen pytest -q tests/optimization/test_scenario_donations.py tests/networks/test_build_scenario.py tests/danger/test_ranking.py tests/optimization/test_actions.py tests/optimization/test_export.py tests/test_w5_contract.py` (`.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) → 200 passed, 0 skipped; whole API suite `uv run --frozen pytest -q` (same env) → 2228 passed, 0 skipped |
| W5-D02 | blocked (CR-w5-data-1) | — (code and tests ready, held out of the branch) | RED seen: hub/DC rows accepted, guide silent. GREEN: `tests/imports/test_validation.py tests/imports/test_templates.py` → 120+ passed. Whole suite with it applied → 1 failed (`tests/imports/test_bench_import.py::test_small_bench_writes_phase_seconds_and_peak_rss`: the lead-owned bench generator writes hub demand), 2238 passed, 0 skipped |
| W5-D03 | done | `cc9c46b` | RED seen (`evaluated` with null WAPE). `uv run --frozen pytest -q tests/forecasting/test_backtest.py tests/imports/` → 211 passed, 0 skipped |
| W5-D04 | done | `fea2ec0` | RED seen (`DID NOT RAISE AccessError` for done and failed). Same command → 211 passed, 0 skipped |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

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

- `tests/networks/test_build_scenario.py`'s fixture forecast job capped its output at 10,000 bytes; six series exceed it (`OUTPUT_TOO_LARGE`). Raised to 100,000 for the donation tests.

## Change requests

### CR-w5-data-1 — the bench import must not write demand history for hubs
- **File(s):** `apps/api/scripts/bench_import.py` (lead-only; `scripts/` isn't a lane path)
- **Exact change:** in `_rows`, make one hub and give demand only to pantries. The locations line becomes `{'hub' if i == 0 else 'pantry'}`, and the demand pairs become `pairs = ((i, p) for i in range(1, LOCATIONS) for p in range(PRODUCTS))`. Update the `--rows` help to "demand_history rows (at most 4,455,000: 99 pantries × 500 × 90; a hub has no demand history, W5-D02)". Alternative: keep 5 hubs and start at `range(5, LOCATIONS)` (at most 4,275,000).
- **Why:** W5-D02 refuses `demand_history` rows for hubs and DCs (W4 decisions §10). Today the generator writes rows for L000–L004, which are hubs, so `test_bench_import.py::test_small_bench_writes_phase_seconds_and_peak_rss` fails with `generated files did not validate: … L000 is a hub …`. The 4.5 M envelope (100 × 500 × 90) can no longer be reached by a network that has a hub; whether V1-SPEC §5.1's figure needs a note is the lead's call. W5-PK04 (bulk-import measurement) uses this bench.
- **Unblocks:** W5-D02. Once it lands on v1-local I merge it and commit D02 from the held patch.
- **Status:** open

## Notes for other lanes (read-only for me)

- **W5-D03 → web:** `apps/web/src/components/data-explorer/trust-panel.tsx:64-72` shows `NOT_EVALUATED` ("accuracy not evaluated: needs 35+ days") for every non-`evaluated` status. After D03, a series whose scored actuals sum to 0 arrives as `not_evaluated_zero_actual` with `reason: sum_actual_zero`, so it would read "needs 35+ days" (wrong) where it showed `NOT_MEASURABLE` before. The panel needs a branch for this status, e.g. the existing NOT_MEASURABLE copy. W5-UI04/UI05 (`w5-polish`) or the lead should decide; merge both together.
- **W5-D01 → W5-UI04:** `DangerRow.basis` and `ProductProjection.basis` are now filled (`demand` | `sales` | null). The why text carries the donation sentence as plain text, so the web needs no change for it.

## Escalations

None.
