# Wave 1 — lanes `w1-data`, `w1-solver`, `w1-web`

**Base:** the `v1-local` head after W0-10 (`{{BASE_SHA}}`, filled at launch). **Mode:** B (multi-session) for all three lanes. **Ownership and ports:** [README](README.md#file-ownership-matrix). **Contract:** frozen in W0-08, and the lanes don't change it. Every task follows the TDD loop and the rules in [ORCHESTRATION.md §8](ORCHESTRATION.md#8-rules-every-lane-inherits). Each lane ends with `/devkit:ship-check` and one PR into `v1-local`.

Backend lanes run tests from `apps/api` with `uv run --frozen pytest -q <path>` after loading `.env.lane`. PostgreSQL tests must not skip.

---

## Lane `w1-data` — templates, import, enrichment, distance, network → scenario

Agent role: `solver-engineer` scope "solver/data" (CLAUDE.md), working under `.claude/rules/data.md` and `api.md`. Service functions to implement: README rows owned by W1-D02…D09.

### W1-D01: Spikes S5 (Census) and S6 (Google) · S · depends on: none · informs V1-A10, A11

**Files:**
- Create: `docs/plans/v1/spikes/S5-census.md`, `docs/plans/v1/spikes/S6-google.md`, `apps/api/tests/fixtures/census/geocode-batch-fl.json`, `apps/api/tests/fixtures/census/acs-tract-fl.json`, `apps/api/tests/fixtures/google/route-matrix-documented.json`, `apps/api/tests/enrichment/test_fixtures_shape.py`.

- [ ] **Step 1:** write `test_fixtures_shape.py::test_census_geocode_fixture_has_tract` and `::test_acs_fixture_has_poverty_and_snap` (FAIL: files missing).
- [ ] **Step 2:** call the Census batch geocoder with about 10 **public-building** Florida addresses (county courthouses, libraries), then call the ACS 5-year API by county for the poverty and SNAP tables. Save the responses as fixtures. Record in S5:
  - the match rate;
  - the table IDs and year;
  - rate limits without a key;
  - what an outage looks like.
- [ ] **Step 3:** in S6, choose the Google endpoint (Routes API `computeRouteMatrix` vs legacy Distance Matrix) from the current docs. Record the request shape, quota, per-element billing, and how to show the lookup count up front. Save a **documented example** response as the fixture, labeled as such; no key is used.
- [ ] **Step 4:** tests PASS. Commit. Outbound calls go only to Census and the Google docs pages.

### W1-D02: Template row validation (pure) · M · depends on: none · V1-A07, A08

**Files:** create `apps/api/app/services/imports/validate.py`, `apps/api/app/services/imports/columns.py`; test `apps/api/tests/imports/test_validation.py`.

**Interface:** `validate_files(files, settings: ImportSettings, envelope=V1_ENVELOPE) -> ValidationReport`, with `ValidationReport.ok: bool`, `.errors: list[RowError(file, line, column, reason)]` (at most 1000 kept), `.error_count: int`, and `.rows: ParsedNetwork` (only when `ok`).

- [ ] **Step 1:** write one failing test per error class. Each asserts the exact `RowError`, with `line` 1-based and counting the header:
  - `test_wrong_header_is_malformed`;
  - `test_duplicate_key` (the same `location_id`/`product_id`/`batch_id` twice, **also after trimming whitespace**);
  - `test_negative_quantity`;
  - `test_fractional_quantity` (`"2.5"`);
  - `test_unknown_location_id_in_inventory`;
  - `test_missing_expiry_without_non_expiring`;
  - `test_over_envelope_location` (the 101st location; the reason contains `limit 100`);
  - `test_history_after_as_of_date_rejected` (no future leakage);
  - `test_non_us_state_rejected`;
  - `test_non_iso_date_rejected` (`11/04/2026` → reason `use YYYY-MM-DD`);
  - `test_quantity_above_solver_bound_rejected` (above the `Count` bound in `or_inputs.py:14`, with a clear reason, never a 500 later);
  - `test_role_not_valid_for_mode` (`store` in a Pantry network);
  - `test_error_cap_1000` (5000 bad rows → 1000 kept, `error_count == 5000`).
- [ ] **Step 2:** write the truth tests:
  - `test_blank_demand_quantity_is_none` (never `0`);
  - `test_utf8_bom_and_crlf_accepted`;
  - `test_non_utf8_file_rejected_with_reason`;
  - `test_ids_case_sensitive_after_trim`;
  - `test_basis_sales_flagged`.
- [ ] **Step 3:** run them (FAIL). Implement with the stdlib `csv` module, streaming row by row.
- [ ] **Step 4:** run them (PASS). Commit.

### W1-D03: Blank templates and the column guide · S · depends on: W1-D02 · V1-A06

**Files:** create `apps/api/app/services/imports/templates.py`, `data/templates/blank/{locations,products,inventory,demand_history,routes,inbound,donation_history}.csv`; test `apps/api/tests/imports/test_templates.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_every_column_has_guide_entry`: every header in every template has `required`, `unit` (or `null`), `meaning`, and an `effect_on_plan` text that isn't empty.
  - `test_blank_templates_are_header_only`.
  - `test_blank_templates_match_validator_columns`.
  - `test_type_values_per_mode`: Pantry `hub`/`pantry`; Retail `distribution_center`/`store`.
  - `test_guide_states_single_timezone_and_blank_capacity_rule`: the copy contains "capacity not provided — no limit assumed".
  - `test_examples_kind_returns_501_until_w3`: `kind=example` raises `NotImplementedV1("W3-P03")`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-D04: Staging and the atomic commit · M · depends on: W1-D02 · V1-A07, A08 · S4 mechanism decided

**Files:** create `apps/api/app/services/imports/staging.py`, `apps/api/app/repositories/imports.py`; test `apps/api/tests/imports/test_import_postgres.py`.

**Shape (S4, frozen in W0-07/W0-08):** `store_import_file` writes each upload under `PP_IMPORT_DIR` (the `imports` volume, shared by api and worker) and records bytes and sha256 in `import_runs.files`. The job COPYs into a per-run UNLOGGED `import_staging` partition, validates set-based into `import_errors`, then loads `net_demand_history`/`net_donation_history` into a per-version partition (`LIKE … INCLUDING CONSTRAINTS`, add keys, `ATTACH`) in one transaction ([W0-network-model.md](decisions/W0-network-model.md)).

- [ ] **Step 1:** write the failing PostgreSQL tests:
  - `test_any_error_saves_nothing`: row counts in every network table are unchanged after a file with one bad row.
  - `test_batches_round_trip_exact`: quantity, `expiry_date`, `non_expiring` and `batch_id` are equal before and after.
  - `test_blank_demand_stays_null_in_database`.
  - `test_one_audited_import_event`.
  - `test_import_writes_no_stock_ledger_or_receipt_rows`.
  - `test_inbound_outside_horizon_kept_and_listed`.
- [ ] **Step 2:** run them (FAIL). Implement staging via PostgreSQL `COPY` with set-based validation, as S4 recommends. Read the upload through the router's `chunks` (`bounded_chunks` in `routers/v1_imports.py`), never `request.stream()` directly: that generator enforces the 160 MiB cap, and only this task makes the end-to-end cap testable.
- [ ] **Step 3:** run them (PASS). Commit.

### W1-D05: The import job, progress, re-import and network reads · M · depends on: W1-D04 · V1-A07, A09

**Files:** create `apps/api/app/services/imports/api.py`, `apps/api/app/workers/imports.py`, `apps/api/app/services/networks/api.py`, `apps/api/app/repositories/networks.py`, `apps/api/scripts/bench_import.py`; test `apps/api/tests/imports/test_import_job.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_create_then_commit`: `POST /imports` returns 201 `ImportCreated`; `POST /imports/{id}/commit` returns 202 `ImportAccepted` with an `import.v1` job, and 422 naming any missing required file (routes in [W0-08-scenario-and-import.md](decisions/W0-08-scenario-and-import.md)).
  - `test_progress_phases_in_order`: `uploading → staging → validating → committing → done`, with `progress.done ≤ progress.total` in the phase's unit (bytes, rows, checks, rows; S4 §6).
  - `test_failed_import_reports_errors_and_saves_nothing`: no dataset version and no network data rows. `POST /imports` already created the network row (W0-08), so `GET /networks` hides a network whose first import never succeeded; its errors stay readable through `GET /imports/{id}` (V1-SPEC §6.1 "nothing is saved").
  - `test_reimport_creates_new_dataset_version_and_old_scenarios_keep_theirs`.
  - `test_second_import_while_first_runs_returns_409`.
  - `test_list_networks_returns_mode_timezone_as_of`.
  - `test_as_of_defaults_to_day_after_last_history`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS).
- [ ] **Step 3:** run `bench_import.py --rows 4500000`. It writes `artifacts/bench/import.json` with seconds and peak RSS. Note the result in your status file; A09 itself is measured in W5-PK04. Commit.

### W1-D06: Geocoding and ACS enrichment · M · depends on: W1-D01, W1-D05 · V1-A10

**Files:** create `apps/api/app/services/enrichment/{census.py,api.py}`, `apps/api/app/workers/enrichment.py`, `apps/api/app/repositories/enrichment.py`; test `apps/api/tests/enrichment/test_census.py`.

**Interface:** `CensusClient(transport: Callable[[urllib.request.Request], bytes])`. Tests inject a fixture transport; the stdlib `urllib` needs no new dependency.

- [ ] **Step 1:** write the failing tests:
  - `test_matched_address_stores_coordinates_tract_and_source`: the source string is `ACS 5-year YYYY, tract NNNN`, plus `fetched_at`.
  - `test_unmatched_address_listed_with_fix_hint`.
  - `test_outage_marks_unknown_and_import_still_succeeds`.
  - `test_retry_fills_unknown_fields`.
  - `test_given_coordinates_skip_geocoding_call`: the transport is never called.
  - `test_egp_blockers_list_unknown_until_manual_value_or_explicit_exclusion`.
  - `test_manual_override_labeled_manual`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-D07: Straight-line distance and `routes.csv` · S · depends on: W1-D05 · V1-A11

**Files:** create `apps/api/app/services/enrichment/distance.py`; test `apps/api/tests/enrichment/test_distance.py`.

**Plan call (confirmed by Gabriel 2026-11-04):** `travel_days = max(1, ceil(road_hours / 24))`, where `road_miles = haversine_miles × 1.3` and `road_hours = road_miles / 45`. A same-region transfer arrives the next day, as in V1-SPEC's example "ship on Nov 6, arrives Nov 7".

- [ ] **Step 1:** write the failing tests:
  - `test_haversine_hand_value`: Tallahassee (30.4383, −84.2807) to Gainesville (29.6516, −82.3248) is about 130 miles straight-line → road ≈ 169 miles → `travel_days == 1`.
  - `test_k10_nearest_within_150_miles`: a 12-sender fixture keeps the nearest 10 within 150 miles.
  - `test_hubs_and_dcs_never_receive`.
  - `test_routes_csv_overrides_computed_values`.
  - `test_routes_csv_disabled_removes_route`.
  - `test_method_label_straight_line_estimate`.
  - `test_route_method_maps_between_api_and_database`: API `straight_line_estimate | google_road | routes_csv` ↔ `net_routes.method` `straight_line | google | user` (`ppv1_0008_networks.sql`).
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-D08: Bring-your-own Google key · M · depends on: W1-D01, W1-D07 · V1-A11

**Files:** create `apps/api/app/services/enrichment/google.py`, `apps/api/app/services/enrichment/settings.py`; test `apps/api/tests/enrichment/test_google.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_no_google_call_without_key`.
  - `test_key_never_in_logs_responses_or_errors`: `caplog`, the `GET /settings` body and a provider-error envelope never contain the key.
  - `test_preview_counts_only_uncached_routes`.
  - `test_results_cached_and_labeled_google_road_with_fetch_date`.
  - `test_routes_csv_still_overrides_google`.
  - `test_provider_error_keeps_straight_line_routes`.
- [ ] **Step 2:** run them (FAIL), implement using S6's endpoint, run them (PASS), commit.

### W1-D09: Network → frozen scenario · M · depends on: W1-D05, W1-D06, W1-D07 · V1-A10, A23 (supply side)

**Files:** create `apps/api/app/services/networks/scenario.py`; test `apps/api/tests/networks/test_build_scenario.py`, plus the fixture `apps/api/tests/networks/fixtures/mini-network/`. That fixture has 1 hub, 3 pantries and 2 products, plus a **fixture forecast run** inserted directly; the forecast lane isn't active until W3.

- [ ] **Step 1:** write the failing tests:
  - `test_golden_mini_network_scenario_hash`: the expected canonical hash is committed in the fixture.
  - `test_inbound_in_horizon_counted_once_not_also_on_hand`.
  - `test_inbound_outside_horizon_excluded_and_listed`.
  - `test_blank_capacity_no_limit_with_assumption_text`: the text is "capacity not provided — no limit assumed".
  - `test_reserve_floors_default_zero_listed_as_assumption`.
  - `test_cost_budget_off_by_default`.
  - `test_egp_freeze_blocked_until_attributes_resolved`.
  - `test_retail_scenario_uses_seven_day_horizon`.
  - `test_donation_forecast_never_supply`.
  - `test_no_scheduled_deliveries_flag_when_no_inbound_file`.
- [ ] **Step 2:** run them (FAIL), implement on top of the existing `freeze_scenario`, run them (PASS), commit.
- [ ] **Step 3:** lane done. Run `node scripts/quality/run.cjs full`, then `/devkit:ship-check`, then open the PR `lane/w1-data → v1-local`.

---

## Lane `w1-solver` — methods, Retail objective, scale, decisions

Agent role: `solver-engineer`. Skills: `cpsat-patterns`, `egp-pi-model`, `verify-solver`. Rules: `.claude/rules/optimization.md`.

### W1-S01: Retail oracle fixtures (spike 2, test-first) · S–M · depends on: none · V1-A15

**Files:** create `data/demo/or-v3/README.md` (one hand derivation per fixture), `data/demo/or-v3/retail-{expiry-transfer,lost-vs-waste,usd-flip,nothing-to-move,day5-expiry}.{input,expected}.json`; test `apps/api/tests/optimization/test_retail_oracle.py`.

- [ ] **Step 1:** derive each fixture by hand, with at most 2 stores, 2 products and 3 batches. Write the derivation in the README: expired units, lost sales, and the objective in units and in USD at `w_exp = 1`, `w_lost = 1`. The `usd-flip` fixture's optimal transfer changes between units and USD. In `day5-expiry`, a batch expires on day 5 of 7 and must sell before then at the receiver.
- [ ] **Step 2:** write `test_<fixture>_matches_oracle` for each fixture. Each runs `run_method(..., RETAIL_OPTIMIZED, measure)` and asserts expired, lost and objective equal the expected file. Also `test_verifier_accepts_expected_allocations`.
- [ ] **Step 3:** run them. Expected: FAIL (`NotImplementedV1("W1-S03")`). Commit the fixtures and the failing tests marked `xfail(strict=True)`. Remove the marks in W1-S03.

### W1-S02: Deterministic baselines · M · depends on: none · V1-A14, A15

**Files:** create `apps/api/app/services/optimization/baselines.py`, `apps/api/app/services/optimization/methods.py`; test `apps/api/tests/optimization/test_baselines.py`.

**Declared tie-breaks** (spec: "Builder", must be declared and tested): earliest first-deficit day, then `location_id` ascending, then `product_id` ascending. Equal-share remainders go to receivers in that same order.

- [ ] **Step 1:** write the failing tests:
  - `test_no_transfers_is_empty_and_verified`.
  - `test_equal_share_two_receivers_hand_values`.
  - `test_most_urgent_first_two_receivers_hand_values`: on the same fixture, equal-share and most-urgent-first give different allocations from each other and from CLASSICAL_GP, with every value derived by hand in the docstring.
  - `test_soonest_expiry_first_moves_earliest_batches`.
  - `test_baselines_deterministic`: 10 repeats give identical output.
  - `test_fefo_respected`.
  - `test_hubs_never_receive`.
  - `test_retail_store_sends_only_surplus_beyond_protected_7_day_forecast_plus_reserve`.
  - `test_every_baseline_result_passes_independent_verifier`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-S03: RETAIL_OPTIMIZED · M–L · depends on: W1-S01, W1-S02 · V1-A15

**Files:** create `apps/api/app/services/optimization/retail.py`; modify `apps/api/app/services/optimization/verify.py` (retail measures); test `apps/api/tests/optimization/test_retail_optimized.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_usd_unavailable_when_any_included_product_lacks_price`: the reason names the products.
  - `test_default_weights_disclosed_in_result`: `w_exp = 1`, `w_lost = 1`.
  - `test_weights_editable`.
  - `test_bd51_relaxed_retail_only`: a unit that sells on day 5 at the receiver counts in Retail; the same transfer is rejected under Pantry BD-51.
  - `test_single_dispatch_on_first_planning_day`.
  - `test_native_status_preserved`: FEASIBLE is never relabeled OPTIMAL.
  - Remove the `xfail` marks from W1-S01.
- [ ] **Step 2:** run them (FAIL). Implement CP-SAT minimizing `w_exp × expired + w_lost × lost_sales` over the seven forecast days, integer-scaled per `cpsat-patterns`.
- [ ] **Step 3:** run `test_retail_oracle.py` and `test_retail_optimized.py` (PASS). Commit.

### W1-S04: N-method comparison (`or-comparison.v3`) · M · depends on: W1-S02, W1-S03 · V1-A14, A15

**Files:** modify `apps/api/app/services/optimization/compare.py` and `apps/api/app/workers/optimization.py`; test `apps/api/tests/optimization/test_compare_v3.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_pantry_five_methods_one_scenario_one_feasible_region`, in both `HUB_ONLY` and `HUB_AND_PANTRY`.
  - `test_retail_three_methods_units_and_usd`.
  - `test_every_published_result_verified`.
  - `test_failed_method_reported_others_still_published`: one method returns UNKNOWN; it's shown with its status and no plan.
  - `test_unverified_result_never_published`.
  - `test_v2_paired_comparison_unchanged`: regression for V1-A22.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-S05: Scale to the envelope · M–L · depends on: W1-S04 · V1-A17 · S1 branch 1 (decided at W0-10)

**Files:** create `apps/api/app/services/optimization/decompose.py` (at-risk screen, capacity split, union check); modify `apps/api/app/services/optimization/candidates.py` (k-nearest) and `apps/api/app/services/optimization/service.py`; create `scripts/or/bench_v1.py`, `docs/optimization/evidence/v1-scale.json`; test `apps/api/tests/optimization/test_scale_v1.py`.

**Approach** ([W0-optimizer-decomposition.md](decisions/W0-optimizer-decomposition.md)): one CP-SAT model per product, and by default only at-risk products. Reimplement from the decision; don't copy `spike/w0-s1`. The independent review of the spike (W0-10) found these gaps, and each one is a test below:
- **At risk** means what the decision says (§1): the no-transfer FEFO kernel of the frozen scenario (`problem.baseline`, so reserves, confirmed inbound and eligibility count) projects unmet demand. Pantry: inside the allocation window. Retail: unmet demand, or expiry within 7 days. The spike's screen ignored inbound and reserves and used 3-day need but a 7-day expiry window, so an expiry-only Retail product got zero capacity.
- **Split by handling units.** Shares are need × `handling_units_per_unit`, because capacities are in handling units. Use integer floor: `cap * need_p // total_need`.
- **No silent starvation.** If a needed product's share is smaller than one unit's handling, the product is reported as "capacity share too small to move one unit", never as optimized. In the spike this hit 170 of 194 at-risk products.
- **Split the cost budget too.** The spike gave each product the whole budget, so N products could spend N× the budget. Split it the same way; the union check enforces the total.
- **Storage binds.** Subtract the projected end-of-day handling stock of every product, solved or not, from storage, then split the rest. Stock already above storage is reported, not made infeasible.
- **The union check is asserted.** Recompute every shared limit in or-input-v3 (route `capacity_per_batch`, receiving, dispatch, storage, global handling, and the cost budget priced with route `cost_per_handling_unit_usd`) from the raw scenario and the union of all per-product plans. Any violation fails the method with a native status. The spike only logged this check.
- **No network objective total.** Per-product objectives (Z, AP/RP normalization) don't add up to a network optimum, and FEASIBLE products add time-limit noise. Report per-product status and gap, and network totals only of physical quantities (units moved, unmet, expired) with the count of OPTIMAL and FEASIBLE products.

- [ ] **Step 1:** write the failing tests:
  - `test_at_risk_screen_uses_frozen_baseline` (inbound and a reserve change the result) and `test_not_at_risk_products_untouched_and_labeled` ("not at risk; not optimized").
  - `test_split_floors_by_handling_need_share_and_never_exceeds_capacity` (property test over random capacities and needs).
  - `test_starved_product_reported_not_optimized`.
  - `test_cost_budget_split_union_within_budget` (2 products, budget B).
  - `test_storage_shared_across_products` (2 products, destination storage nearly full: the union must not overflow).
  - `test_union_check_fails_on_planted_violation`, one case per limit kind (bound + 1).
  - `test_decomposed_equals_monolithic_when_no_shared_capacity_binds` (small instance, non-binding capacities: same objective and verifier result) and `test_decomposed_feasible_for_monolithic_when_capacity_binds` (the union passes the monolithic verifier; the objective gap is recorded, not asserted).
  - `test_no_network_objective_total` (totals are physical and labeled with OPTIMAL/FEASIBLE counts).
  - `test_k_nearest_routes_used`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS).
- [ ] **Step 3:** run `bench_v1.py --locations 100 --products 500 --mode pantry|retail`. It writes the evidence JSON with wall time, native status counts, verifier and union-check results and peak RSS per mode. Expected (S1): at-risk pair ≤ 690 s, worker RSS under 8 GiB (the spike's 6-process pool held about 4.9 GB, so load the scenario once and share it). Commit.

### W1-S06: Decision actions — why, plus the remove-one effect · M · depends on: W1-S04 · V1-A16

**Files:** create `apps/api/app/services/optimization/actions.py`; test `apps/api/tests/optimization/test_actions.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_action_text_format`: e.g. "Move 40 cases of Bottled water from Hub North to Pantry 12, ship on Nov 6, arrives Nov 7."
  - `test_why_text_from_frozen_inputs`: "Pantry 12 runs out on Nov 8 (projected unmet 55 cases over 3 days); Hub North has 120 cases beyond its protected need; 30 of them expire Nov 12."
  - `test_explanation_kind_proven_binding_vs_inferred`.
  - `test_effect_equals_independent_reprojection`: the test re-projects with `services/optimization/projection.py` itself, minus one transfer and without re-optimizing, and compares the sender/receiver unmet, expired and USD deltas.
  - `test_no_total_effect_field`: effects are never summed.
  - `test_non_additive_label_text`: "effect of this action given the rest of the plan; effects don't add up across actions".
  - `test_usd_effect_absent_when_usd_unavailable`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-S07: Plan export CSV · S · depends on: W1-S06 · V1-A16

**Files:** create `apps/api/app/services/optimization/export.py`; test `apps/api/tests/optimization/test_export.py`.

- [ ] **Step 1:** write the failing tests:
  - `test_export_columns`: scenario ID, scenario hash, method, network mode, product, units, quantity, from, to, ship date, arrival date, why, effect, and the note `simulated plan; no stock was reserved or moved`.
  - `test_export_only_selected_actions`.
  - `test_export_changes_no_stock`: a PostgreSQL row-count snapshot of the lots, ledger and receipt tables is unchanged.
  - `test_no_scheduled_deliveries_note_when_no_inbound`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.
- [ ] **Step 3:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w1-solver → v1-local`.

---

## Lane `w1-web` — every new screen, against contract mocks

Agent role: `frontend-engineer`. Read `docs/pantrypulse/ART-DIRECTION.md` and ADR 0002 first; follow `.claude/rules/frontend.md`. Build mocks only from `packages/contracts/examples/v1/*.json` (Playwright `page.route`, the pattern in `tests/e2e/recommendations-fixtures.ts`). Use types from `packages/contracts/src/schema.d.ts`. Don't edit `globals.css`; ask for token changes with a CR. Run unit tests with `npm run test:unit --workspace @pantrypulse/web`, and e2e with `PLAYWRIGHT_PORT=3003 npx playwright test <spec>` from `apps/web`.

### W1-W01: Vitest port (group A) and the 647f6a8 carry-over · S–M · depends on: none · V1-A21

**Files:**
- Create: `apps/web/tests/unit/{atlas-layout,network-atlas,site-inspector,static-fixture,status}.test.ts(x)`, ported from `wip/overview-intake-backup` `b54ec7c` and re-checked against the current components.
- Modify: `apps/web/src/components/scenario-lab/*` through `git cherry-pick 647f6a8`.

- [ ] **Step 1:** port each test unchanged and run it. Expect some to fail where components changed since the old main `a4573b5`; record each failing test. Then fix the **tests** where components legitimately changed (never the components, in this task), and record each change in the status file. Don't port `outlook.test.ts` or `outlook-chart.test.tsx`.
- [ ] **Step 2:** run `npm run test:unit --workspace @pantrypulse/web`. Expected: PASS, with `forecast-proxy.test.mjs` included.
- [ ] **Step 3:** `git fetch origin wip/main && git cherry-pick 647f6a8` (one line in `scenario-lab.tsx`: the builder panel widened to 24rem), then take screenshots at 1440×900 and 390×844 into `artifacts/w1-web/647f6a8-*.png`. Note the visual check in the status file. Commit.

### W1-W02: Network switcher, mode vocabulary and v1 navigation · S–M · depends on: none · V1-A14, A15 (labels), A05 (badge)

**Files:** create `apps/web/src/lib/network-api.ts`, `apps/web/src/lib/mode-vocabulary.ts`, `apps/web/src/components/shell/network-switcher.tsx`; modify `apps/web/src/components/shell/app-sidebar.tsx`; tests `apps/web/tests/unit/mode-vocabulary.test.ts`, `apps/web/tests/e2e/v1-shell.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `transfer mode labels per network mode`: `HUB_ONLY` → "Hub → pantries only" / "DC → stores only"; `HUB_AND_PANTRY` → "Hub and pantries → pantries" / "DC and stores → stores". `role labels per mode`.
  - e2e `@V1-A05 sample network shows "Sample data — fictional"`.
  - e2e `@V1-A14 receipts, posting, adjustments and lot declarations are not in v1 navigation`.
  - e2e `switching network updates vocabulary`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-W03a: Templates and the column guide · M · depends on: W1-W02 · V1-A06, A20

**Files:** create `apps/web/src/app/import/page.tsx`, `apps/web/src/components/import/template-guide.tsx`; tests `apps/web/tests/unit/template-guide.test.tsx`, `apps/web/tests/e2e/import-templates.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `every column renders required/optional, unit, meaning and effect on plan`.
  - unit `optional blank columns say they never become zero`.
  - e2e `@V1-A06 each template offers blank and example downloads`; until W3, the example link shows a disabled state with the reason from the 501 envelope.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-W03b: Upload, progress, errors and network settings · M · depends on: W1-W03a · V1-A07, A23, A20

**Files:** create `apps/web/src/components/import/{upload-form,import-progress,import-errors,network-settings}.tsx`; tests `apps/web/tests/unit/import-errors.test.tsx`, `apps/web/tests/e2e/import-upload.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `renders file, line, column and reason per error`.
  - unit `shows "first 1,000 of N errors" when error_count > 1000`.
  - unit `nothing saved message on failure`.
  - unit `outside-horizon inbound listed`.
  - unit `"no scheduled deliveries provided" when no inbound.csv`.
  - unit `one timezone field with the single-timezone note`.
  - unit `as_of_date defaults to day after last history and is editable`.
  - e2e `@V1-A07 rejected import shows errors, and the new network does not appear in the network switcher`.
  - e2e `@V1-A23 inbound and donation files are optional and labeled`.
  - e2e `@V1-A20 import keyboard-only path + axe`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-W04: Enrichment and settings · M · depends on: W1-W02 · V1-A10, A11, A20

**Files:** create `apps/web/src/app/settings/page.tsx`, `apps/web/src/components/enrichment/{enrichment-status,attribute-editor,google-key-form,route-list}.tsx`; tests `apps/web/tests/unit/google-key-form.test.tsx`, `apps/web/tests/e2e/enrichment.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `key input is cleared after save and never re-rendered; only "configured" shows`.
  - unit `fetch shows "This will make N Google lookups" before confirming`.
  - unit `route method labels "straight-line estimate" / "Google road distance, fetched DATE"`.
  - e2e `@V1-A10 unmatched addresses listed with retry`.
  - e2e `@V1-A10 EGP blocked banner lists locations until values entered or excluded`.
  - e2e `@V1-A10 source line "Source: ACS 5-year YYYY, tract NNNN"`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-W05: Atlas danger ranking · M · depends on: W1-W02 · V1-A13, A20

**Files:** modify `apps/web/src/components/overview/{network-atlas,site-list,risk-legend}.tsx`; create `apps/web/src/components/overview/danger-ranking.tsx`; tests `apps/web/tests/unit/danger-ranking.test.tsx`, `apps/web/tests/e2e/atlas-ranking.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `ranked rows show driving product and its units`.
  - unit `no cross-product unit total is rendered anywhere`.
  - unit `band has text label and shape, not color only`.
  - unit `retail shows the higher of unmet share and expiry share with its reason`.
  - e2e `@V1-A13 table alternative lists the same ranking`.
  - e2e `@V1-A13 selecting a row opens the site inspector`.
  - e2e `@V1-A20 axe clean at 1440×900, 1280×720, 390×844`.
- [ ] **Step 2:** run them (FAIL). Implement, with locations placed by real coordinates in the existing schematic projection (no paid tile key).
- [ ] **Step 3:** run them (PASS). Commit.

### W1-W06: Forecast trust panel · M · depends on: W1-W02 · V1-A12, A08, A23

**Files:** create `apps/web/src/components/data-explorer/{trust-panel,backtest-summary}.tsx`; modify `apps/web/src/components/data-explorer/forecast-chart.tsx`; test `apps/web/tests/unit/trust-panel.test.tsx`, e2e `apps/web/tests/e2e/forecast-trust.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `shows method, fallback reason, missing-day count`.
  - unit `sales basis label "sales (undercounts demand when shelves were empty)"`.
  - unit `quantile band only when provider returned quantiles`.
  - unit `"accuracy not evaluated: needs 35+ days"`.
  - unit `"on your last 4 weeks, this forecast was off by about X%" plus over/under bias`.
  - unit `"expected donations (forecast, not confirmed): X"`.
  - e2e `@V1-A12 @V1-A08 trust panel with mocked BacktestResult`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.

### W1-W07: Mode-aware method comparison · M · depends on: W1-W02 · V1-A14, A15

**Files:** modify `apps/web/src/components/scenario-lab/{wizard,results,model}.ts(x)`, `apps/web/src/components/recommendations/{recommendations-screen,vocabulary}.tsx`, `apps/web/src/lib/planning-api.ts`; tests `apps/web/tests/unit/method-comparison.test.tsx`, `apps/web/tests/e2e/v1-comparison.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `pantry lists 5 methods, retail lists 3`.
  - unit `transfer mode has no default and must be chosen`.
  - unit `USD option disabled with the unavailable reason`.
  - unit `each method shows verification status; a failed method shows its native status and no plan`.
  - unit `per-location effects table`.
  - e2e `@V1-A14 pantry comparison mocked in both transfer modes`.
  - e2e `@V1-A15 retail comparison mocked in units and USD`.
- [ ] **Step 2:** run them (FAIL), implement, and run `research-claims-check` on any EGP copy. Run them (PASS), commit.

### W1-W08: Decisions and export · M · depends on: W1-W07 · V1-A16, A20

**Files:** create `apps/web/src/app/decisions/page.tsx`, `apps/web/src/app/decisions/print/page.tsx`, `apps/web/src/components/decisions/{action-card,action-list,export-bar}.tsx`; tests `apps/web/tests/unit/action-card.test.tsx`, `apps/web/tests/e2e/decisions.spec.ts`.

- [ ] **Step 1:** write the failing tests:
  - unit `action/why/effect three parts`.
  - unit `proven vs inferred badge`.
  - unit `non-additive label visible`.
  - unit `no summed effect anywhere`.
  - unit `USD effect hidden with reason when unavailable`.
  - e2e `@V1-A16 select actions, export CSV download contains scenario hash and "simulated plan; no stock was reserved or moved"`.
  - e2e `@V1-A16 print page shows the same rows`.
  - e2e `@V1-A20 decisions keyboard + axe + reduced motion`.
- [ ] **Step 2:** run them (FAIL), implement, run them (PASS), commit.
- [ ] **Step 3:** lane done. Run `full`, then `/devkit:ship-check`, then open the PR `lane/w1-web → v1-local`.
