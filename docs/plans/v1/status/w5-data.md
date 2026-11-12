# Status — `w5-data`

**Lane:** `w5-data` · **Branch:** `lane/w5-data` · **Base SHA:** `81c551bc2e232362f0e63a7a00126ef1ca863fb8` · **Last update:** `2026-11-12` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W5-D01 | done | see `git log --grep W5-D01` | `uv run --frozen pytest -q tests/optimization/test_scenario_donations.py tests/networks/test_build_scenario.py tests/danger/test_ranking.py tests/optimization/test_actions.py tests/optimization/test_export.py tests/test_w5_contract.py` (`.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) → 200 passed, 0 skipped; whole API suite `uv run --frozen pytest -q` (same env) → 2228 passed, 0 skipped |
| W5-D02 | in progress | — | — |
| W5-D03 | in progress | — | — |
| W5-D04 | in progress | — | — |

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
- **Hub/DC demand rows (W5-D02)** use the existing `MALFORMED` code (as a route into a hub does), so no contract change.

## Gotchas

- `tests/networks/test_build_scenario.py`'s fixture forecast job capped its output at 10,000 bytes; six series exceed it (`OUTPUT_TOO_LARGE`). Raised to 100,000 for the donation tests.

## Change requests

None.

## Escalations

None.
