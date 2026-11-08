# Wave 3 — lanes `w3-forecast`, `w3-samples`, `w3-web`

**Base:** the `v1-local` head after W2 (`{{BASE_SHA}}`). **Mode:** B for all three lanes. The wave-1 code is merged, so lanes call it but don't modify it; needing a change to it is a CR. Same rules as wave 1 ([ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-inherits)).

---

## Lane `w3-forecast` — backtest, network forecasts, inbound, danger ranking, volume

Agent role: `forecast-engineer`. Skill: `verify-forecast`. Rules: `.claude/rules/forecasting.md`, `data.md` (for `services/inventory/**`).

### W3-F01: Spike S7, forecast and backtest volume · S · depends on: none · informs V1-A17

**Files:** create `apps/api/scripts/bench_forecast.py`, `docs/plans/v1/spikes/S7-forecast-volume.md`.

- [ ] **Step 1:** generate 50,000 series × 90 days. Time the existing `forecast.v1` baseline (7 points each) plus 4 backtest origins against the 300 s ceiling (forecast 270/300 s). Record seconds, rows written, storage MB and peak RSS.
- [ ] **Step 2:** write a verdict, "fits" or "needs X". If it needs more, W3-F06 files a CR with the evidence. Commit.

### W3-F02: Rolling-origin backtest · M · depends on: none · V1-A12

**Files:** create `apps/api/app/services/forecasting/backtest.py`; test `apps/api/tests/forecasting/test_backtest.py`.

**Interface:** `backtest_series(history, fit, origins=4, horizon=7) -> BacktestScore{origins_evaluated, wape_pct: Decimal | None, bias_pct: Decimal | None, status: "evaluated" | "not_evaluated_insufficient_history", scored_points}`. It uses the V5 §7 formulas on **one** scored set, shared by WAPE and bias.

- [ ] **Step 1:** write the failing tests:
  - `test_wape_and_bias_hand_values`: a 42-day fixture with WAPE and bias derived by hand.
  - `test_same_scored_set_for_wape_and_bias`.
  - `test_missing_actuals_excluded_not_zero`.
  - `test_under_35_days_not_evaluated`.
  - `test_origins_weekly_last_four`.
  - `test_no_future_leakage`: each origin fits only on data before it.
  - `test_zero_denominator_reports_none`.
  - `test_location_rollup_from_series`.
  - `test_location_rollup_never_pools_units`: a location with products in two units gets two rows (W2-06 carry-in).
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

**W2-06 carry-in:** `BacktestResult.locations` is one `LocationBacktest{location_id, unit, series_count, score}` per location and unit, on the pooled scored set of that location's demand series in that unit. Different units are never pooled ([decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md) §2, CR-w1-web-4 b).

### W3-F03: Forecasts for imported networks, with donations · M · depends on: W3-F02 · V1-A12, A08, A23

**Files:** modify `apps/api/app/workers/forecasting.py` and `apps/api/app/services/forecasting/*` (network series source, backtest persistence); test `apps/api/tests/forecasting/test_network_forecast.py`.

**W1 carry-in (2026-11-07):**
- `create_scenario` (W1-D09, `services/networks/scenario.py`) already accepts only a forecast run that:
  - is `planning_ready`;
  - has `frozen_input.dataset_id` equal to the network's dataset version;
  - has `data_cutoff_date` equal to that version's `as_of_date`;
  - keys its series by `net_locations.id` and `net_products.id`.
  Anything else is 409. Publish runs in exactly that shape, and add `test_create_scenario_accepts_a_published_network_run`.
- Implement `list_forecast_runs(rt, scope, network_id) -> ForecastRunList` (CR-w1-web-2) next to `submit_network_forecast`.
- `forecast.v1` is in `V1_NETWORK_JOBS` since W2-06 (`0730730`), so `GET /jobs/{id}` answers for a network forecast. `forecast.chronos.v1` is not; running Chronos for networks is a CR.
- Implement `get_forecast_run(rt, scope, network_id, forecast_run_id) -> NetworkForecastRun` (CR-w1-web-4 a, W2-06) in `services/forecasting/network.py`. Map series back to CSV ids, list every series with its status and reason (never forecast from zeros), and drop the route from `STUBS` in `tests/test_v1_contract.py`. Example: `packages/contracts/examples/v1/NetworkForecastRun.json`.
- A re-import publishes a new dataset version, and older runs are then refused with `STALE_DATASET_VERSION`.

- [ ] **Step 1:** write the failing tests:
  - `test_every_eligible_series_gets_seven_dated_points_with_actual_provider_and_fallback`.
  - `test_series_under_14_days_listed_ineligible_not_zero_filled`.
  - `test_location_with_all_blank_history_listed_not_forecast`.
  - `test_sales_basis_carried_to_series_label`.
  - `test_donation_series_forecast_labeled_not_confirmed`.
  - `test_backtest_persisted_and_served_by_get_backtest`.
  - `test_chronos_off_by_default`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W3-F04: Inbound in the projection · S–M · depends on: none · V1-A23

**Files:** modify `apps/api/app/services/inventory/projection.py`; test `apps/api/tests/test_inventory_projection.py` (new cases).

- [ ] **Step 1:** write the failing tests:
  - `test_inbound_enters_once_on_arrival_date_arrivals_first`: BD-48 daily order.
  - `test_inbound_not_also_counted_on_hand`.
  - `test_outside_horizon_inbound_excluded`.
  - `test_inbound_expiry_applies_fefo`.
  - `test_golden_arithmetic_with_inbound`: a hand table in the docstring.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W3-F05: Danger ranking service · M · depends on: W3-F03, W3-F04 · V1-A13, A23

**Files:** create `apps/api/app/services/danger/{__init__,ranking}.py`; test `apps/api/tests/danger/test_ranking.py`.

**Interface:** `danger_ranking(projection, mode) -> list[DangerRow{location_id, rank, score_ratio: Decimal, band, reason: "unmet" | "expiry", driving_product_id, driving_units, unit, first_deficit_date}]`. Band thresholds are declared in the module and tested.

**W1 carry-in:**
- Also implement `get_projection(rt, scope, network_id, forecast_run_id, location_id) -> LocationProjection` (CR-w1-web-3). Its route is a 501 stub today (STUBS in `tests/test_v1_contract.py`), and the W1 site inspector reads it.
- Decided at W2-06: danger and the projection reuse `services/optimization/projection.py::project_v3`, which already counts frozen inbound once, so the danger ranking stays in step with the solver. W3-F04's inbound tests apply to that kernel.

- [ ] **Step 1:** write the failing tests:
  - `test_pantry_score_is_worst_product_unmet_share_of_7_day_demand`, computed independently in the test.
  - `test_ties_broken_by_earliest_first_deficit_day`.
  - `test_retail_score_is_max_of_unmet_share_and_expiry_share_with_reason`.
  - `test_never_sums_units_across_products`: no field aggregates different products.
  - `test_donation_forecasts_do_not_change_score`.
  - `test_inbound_changes_score_once`.
  - `test_get_danger_endpoint_matches_service`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W3-F06: The 50k-series ceiling · M · depends on: W3-F01, W3-F03 · V1-A17 · [conditional on S7]

- [ ] **Step 1:** write the failing test `apps/api/tests/forecasting/test_forecast_scale.py::test_batched_series_equal_unbatched_on_small_set`: batching never changes the output.
- [ ] **Step 2:** if S7 says "fits", run `bench_forecast.py --series 50000`. If S7 says "needs X", optimize batching first. Only if that still misses 300 s, file a CR to raise the forecast ceiling, with the evidence. Commit the benchmark result as `docs/forecasting/evidence/v1-forecast-scale.json` (wall time, series, peak RSS, commit).
- [ ] **Step 3:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w3-forecast → v1-local`.

---

## Lane `w3-samples` — two fictional Florida networks, examples and seed

Agent role: `solver-engineer` ("solver/data"). Rules: `.claude/rules/data.md`. Samples are generated, then **imported through the merged W1 importer** (`app.services.imports.staging.run_import`; the seed runs before the worker starts, so the API commit path would answer 503), never written to the tables directly.

**W1 rules every sample must pass** (2026-11-07; see `decisions/W0-08-scenario-and-import.md` §7–§8):
- Coordinates on every location, and both rates (`poverty_rate`, `snap_rate`) on every pantry. Given coordinates skip geocoding, so no ACS lookup fills them.
- Every receiver within 150 mi of its hub/DC.
- At least 2 pantries with demand per product (EGP's singleton rule).
- Whole `handling_units_per_unit`; a fractional value blocks the freeze.
- Quantities ≤ 100,000.
- History ≤ 90 days and never after `as_of_date`; inbound strictly after `as_of_date`.
- Short batch ids with no `/`, so frozen batch ids stay readable instead of hashed.
- `unit_value_usd` on every Retail product.
- Add `test_each_sample_freezes_cleanly`.
- `run_import` queues no `enrichment.v1`, so a sample's enrichment shows `not_started`.
- W2-06 carry-ins ([decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md)):
  - The importer sets `networks.is_sample` (#119). Create each sample network with `app.services.imports.api.create_import(rt, scope, request, *, is_sample=True)`. HTTP can't set the flag, and a re-import keeps it (decisions §2).
  - A fractional `handling_units_per_unit` is now a row error at import.
  - Lots already expired at `as_of_date` are left out of the frozen scenario and listed as an assumption.
  - Sample rates are labeled "sample values", not "manual" (V1-SPEC §8).

### W3-P01: Pantry sample · M · depends on: none · V1-A05

**Files:** create `apps/api/app/services/samples/pantry.py`, `data/samples/README.md`; test `apps/api/tests/samples/test_pantry_sample.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_shape_1_hub_8_pantries_6_products_90_days`.
  - `test_dates_relative_to_today`: the last history date is `today − 1`; batches include future expiries.
  - `test_city_level_coordinates_no_street_addresses`.
  - `test_poverty_snap_prefilled_labeled_sample_values`.
  - `test_validates_clean_through_validate_files`.
  - `test_deterministic_for_seed_and_date`.
  - `test_labeled_sample_data_fictional`.
- [ ] **Step 2:** run them (FAIL). Implement, extending the `data/demo/forecasting-v1.json` style.
- [ ] **Step 3:** run them (PASS). Commit.

### W3-P02: Retail sample · M · depends on: W3-P01 · V1-A05

**Files:** create `apps/api/app/services/samples/retail.py`; test `apps/api/tests/samples/test_retail_sample.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_shape_1_dc_20_stores_50_products_with_unit_value_usd`.
  - `test_varied_expiry_including_within_7_days`.
  - `test_fictional_chain_name_no_real_brands`: checks against a denylist of real US grocery and CPG brand names kept in the test.
  - `test_validates_clean`.
  - `test_includes_inbound_and_donation_history_rows`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W3-P03: Template examples generated from the samples · S · depends on: W3-P02 · V1-A06

**Files:** create `apps/api/scripts/generate_samples.py`, `data/templates/examples/*.csv`; implement the `kind="example"` branch in `apps/api/app/services/imports/templates.py`.

The W3 matrix gives `w3-samples` ownership of `templates.py` for this wave. Only the `example` branch changes. The `blank` behavior from W1-D03 stays as merged, and its tests must keep passing.

Test `apps/api/tests/samples/test_examples.py`:

- [ ] **Step 1:** write the failing tests:
  - `test_example_files_equal_generator_output`: a drift check.
  - `test_every_template_has_example`.
  - `test_examples_validate_clean`.
  - `test_get_template_example_returns_csv`.
- [ ] **Step 2:** run them (FAIL), implement, generate, run them (PASS), commit.

### W3-P04: Seed service · M · depends on: W3-P02 · V1-A02, A05

**Files:** implement `apps/api/app/services/samples/__init__.py::ensure_samples(session, today) -> SeedReport`; test `apps/api/tests/samples/test_seed.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_first_start_loads_both_samples`.
  - `test_second_start_loads_nothing`: no duplicates.
  - `test_new_freshly_dated_version_when_newest_older_than_7_days`.
  - `test_older_versions_and_results_untouched`.
  - `test_no_outbound_network_calls`: the socket connect is patched to raise.
  - `test_never_resets`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS).
- [ ] **Step 3:** run the stack with `COMPOSE_PROJECT_NAME=pp-samples PP_WEB_PORT=3102 docker compose up --build -d --wait` and check that both samples appear, with the network disabled for the seed container if feasible. Then `down -v`.
- [ ] **Step 4:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w3-samples → v1-local`.

---

## Lane `w3-web` — wire to the real API, connected journeys, accessibility

Agent role: `frontend-engineer`. The wave-1 screens exist. This lane replaces mocks with the real API wherever the wave-1 backend is merged:
- **real API:** import, enrichment, routes, scenario, comparison, actions, export;
- **contract examples until W4:** the forecast backtest, danger and sample-example endpoints, which are built in parallel this wave. That also covers the W1-added `ForecastRunList`, `LocationProjection` and network-forecast POST mocks; drop W1's `?forecast_run_id=` / `?forecast_job_id=` URL stopgaps once runs can be listed.

**W2-06 carry-ins** (live smoke and review; [decisions/W2-06-change-requests.md](decisions/W2-06-change-requests.md) §3). Each gets a failing test first:
- The import page states that addresses without coordinates are sent to the Census geocoder. V1-SPEC line 48 requires an explicit, labeled lookup.
- No "simulated network" wording on a real import (the Live chip, the Atlas subtitle, the session footer). Keep the pill only for samples, using `Network.is_sample`.
- The header shows the snapshot's `as_of_date`, not today.
- The product picker no longer stays on "Loading products…".
- No legacy fixture atlas above an imported network's ranking.
- Wire names in the trust panel and Decisions (`LocationList`).
- The column guide says that a pantry given coordinates also needs both rates, or an exclusion.
- CR-w1-web-4 is defined: the trust panel reads `NetworkForecastRun` (the method, fallback reason, missing days, quantile band and donation series) and `BacktestResult.locations` (one row per location and unit). Mocks come from the new examples until W4.

### W3-W01: Wire import, enrichment and settings · M · depends on: none · V1-A06, A07, A10, A11, A23

**Files:** modify `apps/web/src/lib/*-api.ts`, `apps/web/src/components/{import,enrichment}/**`; test `apps/web/tests/e2e/v1-connected-import.spec.ts` (runs only under `PP_RUN_CONNECTED=1`, and **counts as evidence only in the connected run**).

- [ ] **Step 1:** write the failing tests:
  - connected `@V1-A07 bad file rejected: failure message and per-row fixes shown, and no network or dataset version created`.
  - connected `@V1-A06 @V1-A23 good template set with inbound and donation_history imports and shows progress`.
  - connected `@V1-A10 offline enrichment marks unknown with retry`. The API runs with no egress. Use a fixture with at least one address without coordinates: located rows are never looked up, so sample data alone proves nothing here.
  - connected `@V1-A11 route labels`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS) against the lane's API on 8003 and the `pantrypulse_web_test` schema. Commit.

### W3-W02: Wire comparison and decisions; connected journeys per mode · M · depends on: W3-W01 · V1-A14, A15, A16

**Files:** modify `apps/web/src/components/{scenario-lab,recommendations,decisions}/**`; test `apps/web/tests/e2e/v1-connected-journey.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - connected `@V1-A14 pantry: import → scenario (both transfer modes) → 5 methods verified → decisions → export`.
  - connected `@V1-A15 retail: 3 methods units and USD, USD unavailable with reason on a no-price variant`.
  - connected `@V1-A16 export CSV contains hash and simulated text; stock tables unchanged`, checked with the W1-S07 row-count check (no v1 route reads batches).
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W3-W03: Accessibility at three viewports · S–M · depends on: W3-W02 · V1-A20

**Files:** test `apps/web/tests/e2e/v1-a11y.spec.ts`.

- [ ] **Step 1:** write the failing tests: `@V1-A20` for the import, decisions and atlas ranking screens at 1440×900, 1280×720 and 390×844. Each covers a keyboard-only path, axe with 0 violations (`tests/e2e/a11y.ts`), and `prefers-reduced-motion` with no non-essential animation.
- [ ] **Step 2:** run them (FAIL), fix, run them (PASS).
- [ ] **Step 3:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w3-web → v1-local`.
