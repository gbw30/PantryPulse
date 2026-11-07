# Status — `w1-solver`

**Lane:** `w1-solver` · **Branch:** `lane/w1-solver` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** `2026-11-07` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-S01 | done (failing tests committed `xfail(strict=True)`; marks removed in W1-S03) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_retail_oracle.py` → 24 xfailed (`NotImplementedV1` / missing `verify_plan`), 0 passed, 0 skipped |
| W1-S02 | done: NO_TRANSFERS, SOONEST_EXPIRY_FIRST, EQUAL_SHARE, MOST_URGENT_FIRST, Retail and Pantry (`test_pantry_four_methods_hand_values`, `test_pantry_hubs_never_receive`) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_baselines.py test_pantry_methods.py` → 19 + 26 passed, 0 skipped |
| W1-S03 | done: RETAIL_OPTIMIZED; the Pantry half of BD-51 (`test_bd51_relaxed_retail_only`) runs on the CR-1 schema | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_retail_oracle.py test_retail_optimized.py` → 24 + 13 passed, 0 skipped; `test_pantry_methods.py` → 26 passed |
| W1-S04 | done: pure `compare_methods`; the `or-comparison.v3` handler and publisher (one step per method, a per-method deadline that keeps 30 s for verification, independent failures, publication re-check; `planning_comparisons_v3` row with id = job_id); `api_v3` submit/get (404 `COMPARISON_NOT_FOUND` before publication); Pantry five methods | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_compare_v3.py test_comparison_v3_worker.py` → 9 + 12 passed; `test_comparison_v3_postgres.py` (with `.env.lane`, isolated schema) → 5 passed, 0 skipped; `tests/workers/test_v1_job_kinds.py` → 3 passed |
| W1-S05 | done: decomposition hardening, method search deadline, fast heuristic probe, localized capacity split (`test_allot_*`, `test_localized_split_only_products_with_need_at_receiver`), Pantry window at-risk screen and no total (`test_pantry_at_risk_uses_the_window_and_reports_no_total`), `scripts/or/bench_v1.py`, and 100 × 500 evidence for both modes (`docs/optimization/evidence/v1-scale.json`, commands under Scale benches) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization` → 315 passed, 0 skipped (with `.env.lane`, at ea6fad1); `taskset -c 0-5 uv run --frozen python ../../scripts/or/bench_v1.py --locations 100 --products 500 --mode retail` at ea6fad1 → UNITS 143.9 s, USD 145.2 s; starved 0/209 (was 123/209, USD 150/209, before the localized split); all six results verified; exit 0. `--mode pantry` at ea6fad1 → UNITS 249.6 s, five methods verified, GP/EGP OPTIMAL ×209; exit 0 |
| W1-S06 | done for both modes; `api_v3.comparison_actions` (404 `METHOD_NOT_IN_COMPARISON`, 409 `RESULT_NOT_VERIFIED`) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_actions.py` → 9 passed, 0 skipped (Pantry: `test_pantry_actions_explain_the_window`) |
| W1-S07 | done: `export_plan_csv`, `api_v3.export_comparison` (422 `UNKNOWN_ACTION_ID`), Pantry export, `test_export_changes_no_stock` on PostgreSQL (every non-queue table's row count unchanged) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_export.py` → 8 passed, 0 skipped; `test_comparison_v3_postgres.py` → 5 passed |

## Progress (2026-11-07)

- **Done:** every task W1-S01–S07 in both modes. #103 merged into the lane (18799a6); the Pantry tests run on the CR-1 schema (4b18119); localized capacity split (de0c53c); Pantry bench (e49e35c); `or-comparison.v3` worker, `api_v3`, Pantry S05–S07 tests (bfdb21e); ship-check review fixes and network-scoped `api_v3` (ea6fad1); final benches at ea6fad1.
- **Next:** quick and full gates on the final commit, then the PR.
- **Waiting on the lead (batch 2, Gabriel-approved web CRs; merge `origin/v1-local` only on the lead's signal):** fill `ActionEffect.unit` (the product's `ProductV3.unit`), `SavedComparisonV3.assumptions` and `.inbound_file_provided` (copied from the frozen scenario), and the CSV note "capacity not provided — no limit assumed" when that assumption is present (CR-w1-web-5/-6). E-1 (`RETAIL_WEIGHTS_ALL_ZERO`) needs nothing here: no fixture, test or bench uses w_exp = w_lost = 0.
- **Interpretations for lead review (W1-S04/S06/S07 wiring):**
  - Only `COMPARISON_NOT_FOUND` is specified. I chose the other codes: unknown network → 404 `NETWORK_NOT_FOUND`; submit with a scenario that isn't in the path's network → 404 `SCENARIO_NOT_FOUND`; a method not in the comparison → 404 `METHOD_NOT_IN_COMPARISON`; actions or export of an unverified method → 409 `RESULT_NOT_VERIFIED`; export with an action id not in the plan → 422 `UNKNOWN_ACTION_ID`. All are `HistoryRejected(code, status)`, mapped by `main.domain_error`.
  - Tenancy (lead-approved 2026-11-07): `api_v3` runs each request under the organization of the network in its path (`networks.organization_id`, W0-network-model §1–2), with the session's actor. The PostgreSQL tests log in under a separate presenter organization and assert that the job and the comparison row carry the network's organization. W2 consolidates the per-lane lookups into one helper.
  - `planning_ready` (the dedupe flag) is true only when every requested method verified, as in v2, so a comparison with a timed-out method can be rerun with the same input. `comparison_outcome` is SUCCEEDED / PARTIAL / FAILED.
  - The publisher checks the scenario row (organization, network, content hash, payload) and the package identity inside the publication transaction. It doesn't rebuild the methods there: `validate()` already rebuilt every claimed-verified result in the parent (`compare.publishable`), and a 100 × 500 union check inside the fenced transaction would hold the publication lock for seconds.
  - Orphans: `planning_comparisons_v3` rows are immutable (UPDATE/DELETE trigger), and the row is inserted in the same transaction as the SUCCEEDED transition, so an uncertain commit leaves the row and the success together or neither. `test_uncertain_commit_leaves_one_row_or_none_and_retry_never_doubles` shows COMMITTED → one row; ABSENT → no row, FAILED, then a retry publishes exactly one row for the retry attempt.
  - `tests/optimization/test_or_scope.py` exempts only `api_v3.py` (W0-08a froze the router-facing adapter there with a runtime argument; it reads the v1 tables). Every other OR module still may not import SQLAlchemy, models or repositories, and none may import `api_v3` (new check; three import forms mutation-tested).
  - `tests/test_v1_contract.py`: the comparisons GET/actions/export rows and the comparisons submit entry are deleted, as ORCHESTRATION §8 allows. `tests/workers/test_v1_job_kinds.py`: CR-w1-solver-4.
- **Scale benches (W1-S05, V1-A17 evidence).** Command, from `apps/api` with `.env.lane` loaded: `taskset -c 0-5 uv run --frozen python ../../scripts/or/bench_v1.py --locations 100 --products 500 --mode {retail|pantry}`. Each run writes its mode into `docs/optimization/evidence/v1-scale.json`. Runs used 6 CPUs, WSL2, seed 20261104, on a network of 100 locations, 500 products, 69 961 batches, 48 000 demand series and 960 routes. Ceilings: 330 s per method, 690 s per comparison.
  - **Final, tree ea6fad1** (after the review fixes; this is what `v1-scale.json` holds). Every method result is verified, and every union check passes.
    - Retail: comparison wall time UNITS 143.9 s, USD 145.2 s. Total 321.4 s (`/usr/bin/time` 5:21.94), peak RSS 1.45 GB, exit 0. At-risk 209/500, starved 0.
    - Pantry (`DEFAULT_PANTRY_POLICY`, `planning_days` 3, vulnerability for every pantry): five methods, UNITS 249.6 s. Total 275.2 s (4:35.90), peak RSS 1.10 GB, exit 0. At-risk 209/500, starved 0, no singleton RP groups.

    | Mode / measure | Method | Status | Transfers |
    |---|---|---|---|
    | Retail UNITS | NO_TRANSFERS | — | 0 |
    | Retail UNITS | SOONEST_EXPIRY_FIRST | — | 8 429 |
    | Retail UNITS | RETAIL_OPTIMIZED | OPTIMAL ×209 | 8 025 |
    | Retail USD | NO_TRANSFERS | — | 0 |
    | Retail USD | SOONEST_EXPIRY_FIRST | — | 9 486 |
    | Retail USD | RETAIL_OPTIMIZED | OPTIMAL ×209 | 8 775 |
    | Pantry UNITS | NO_TRANSFERS | — | 0 |
    | Pantry UNITS | EQUAL_SHARE | — | 3 473 |
    | Pantry UNITS | MOST_URGENT_FIRST | — | 3 473 |
    | Pantry UNITS | CLASSICAL_GP | OPTIMAL ×209 | 4 062 |
    | Pantry UNITS | EGP_PI_INSPIRED | OPTIMAL ×209 | 4 091 |

    Plans and statuses match the earlier runs. Publication now rebuilds every claimed-verified result, which adds about 13–30 s per comparison. EQUAL_SHARE and MOST_URGENT_FIRST report the same transfer count. The bench records counts, not plans, so whether the two plans are identical is unverified; on `pantry-four-methods` they differ.
  - Earlier runs, for the record: Retail at de0c53c, UNITS 130.9 s and USD 124.5 s, starved 0/209. Before the localized split it was 123/209 (USD 150/209). Pantry at de0c53c: 220.2 s.
  - History: the first Retail run timed out at 25 min because SOONEST_EXPIRY_FIRST took more than 23 min. Three probe fixes (6b46700 and later) brought the full Retail comparison under the ceilings.

## Ship-check review (project `verifier`, candidate b0531b8)

| Finding | Severity | Disposition |
|---|---|---|
| F1: EGP split capacity without its singleton products, so its feasible region differed from the other methods' | High | Fixed in ea6fad1: every method splits over every at-risk product (`test_singleton_product_keeps_the_shared_split`) |
| F2: the starvation screen ignored storage, so a product with no storage room was reported OPTIMAL with 0 moves | Medium | Fixed in ea6fad1: the screen counts storage on the days a unit waits at the receiver, and only receivers with need (`test_storage_share_too_small_is_starved_not_optimized`; both halves mutation-checked) |
| F3: publication re-checked only the plan and effects; objective, labels and status could be tampered | Medium | Fixed in ea6fad1: `publishable` rebuilds the whole result from the raw scenario and its own plan (`test_tampered_result_fields_are_published_unverified[...]`, `test_product_status_relabel_is_published_unverified`). Per-product native statuses remain solver claims; only their consistency is checkable without re-solving |
| F4: export didn't say "optimized per product…" or name solved products | Medium | Fixed in ea6fad1: per-row note for optimizing methods (`test_export_says_optimized_per_product_and_names_each_solved_product`) |
| F5: CR-w1-solver-4 not recorded outside the test comment | Low (process) | Recorded under Change requests below; the lead records it in BOARD/decisions |
| S4: CSV formula injection from imported names | Low | Fixed in ea6fad1 (`test_export_neutralizes_spreadsheet_formulas`) |
| No TEST-EGP-04 ablation; no RP equality boundary | Gap | Added: `test_penalty_ablation_changes_the_egp_plan` (γ_AP = 0 changes the plan; with AP off, γ_RP = 0 changes it again; γ_RP = 0 alone does not on this fixture), `test_rp_flag_unset_at_equality`; mutation-checked |
| S1: `verify_plan` shares FEFO packing, candidates and the projection with the solver path; only the shared-limit sums are re-derived independently | Design, open | Recorded. Hand-derived FEFO tests (`test_fefo_respected`) are the independent check today. An independent FEFO re-implementation is a candidate for W2 hardening |
| S2: MethodResult has no seed / worker count / OR-Tools version | Low, open | Needs a contract field (lead). Every solve uses `num_workers = 1`, seed 0 (`retail.solve`) |
| S3: Retail "expired" on day 1 includes lots already expired at the snapshot | Low, open | Effects are deltas, so actions are unaffected. Only the need weight could be inflated, and only if a frozen scenario carries already-expired lots. Whether W1-D09 excludes them is a data-lane question |
| S5: a receiver with no local need gets no share of its limits | By decision | The localized split rule (Gabriel, 2026-11-07) |

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` (standard env: PP_TEST_DATABASE_URL, PP19_* unset) | bfdb21e | PASS, exit 0 (web typecheck, web lint, api lint, api tests). Its api-tests step (`uv run --frozen pytest -q -rs`) → 1355 passed, 231 skipped. Every skip is PostgreSQL-gated and none counts as validation. 136 are "NOT RUN: PP_TEST_DATABASE_URL is not set": `test_supervisor` 54, `test_job_queue` 40, `test_v1_schema` 18, `test_job_migrations` 11, `test_local_bootstrap` 10, `test_worker_slice` 9, `test_comparison_v3_postgres` 5, `wq_support` 4, `test_v1_locations` 2, `test_long_solver_runtime` 1. 95 are the PP19 isolated-schema opt-in: `test_operational_postgres` 25, `test_stock_postgres` 17, `test_stock_adjustment_api_postgres` 9, `test_operations_api_postgres` 7, `test_forecast_api_postgres` 6, `test_inventory_api_postgres` 5, `test_planning_api_postgres` 4, `test_planning_postgres` 4 |
| `node scripts/quality/run.cjs full` (with `.env.lane`, `PP19_TEST_SCHEMA_ISOLATION=1`) | bfdb21e | PASS, exit 0, all 8 steps (quick 4 + web unit tests, web build, contract drift, database migrations). Same env, api-tests step `uv run --frozen pytest -q -rs` → 1586 passed, 0 skipped, 210.7 s (limit 480 s); migrations step → 36 passed, 0 skipped |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- **Retail semantics for the v3 path** (W1-S01): sellable through the expiry date; unsold units past an in-horizon expiry count as expired, including expiry on day 7; transfers ship on day 1 from on-hand batches, FEFO per sender over the eligible batches (expiry ≥ arrival); relaxed BD-51 means every transferred unit sells at the receiver before its expiry and by day 7; BD-49 sender protection over all 7 days plus the reserve floor. Written out in `data/demo/or-v3/README.md`.
- **Tie-break for RETAIL_OPTIMIZED:** fewer moved units, never changing the primary objective (`nothing-to-move` needs it: a useless transfer must not appear).
- **No units total across products:** in UNITS a method objective is reported only for a one-product scenario; otherwise `objective = None` and per-product values come from the effects. USD totals are summed.
- **v3 path layout:** `v3.py` (dates, roles, eligible routes, FEFO packing, transfer ids), `projection.project_v3` (kernel replay with a sentinel day so day-7 expiries count), `verify.verify_plan` (independent check including the union check of every shared limit), `product_model.py` (one product's CP-SAT physical model mirroring `project_v3`), `retail.py`, `decompose.py`, `methods.py` (dispatch and one assembly that publishes only verified plans and replays each native objective).
- **Every optimizing method is per product even on tiny scenarios,** so the oracle fixtures exercise the same path as 100 × 500.
- **Method-level native status:** OPTIMAL if every solved product is OPTIMAL, FEASIBLE if any is FEASIBLE; any product without a solution fails the method with that status and no plan (`NO_SOLUTION:<ids>`). A method that solved nothing has `native_status = None`. Each product's own status and FEASIBLE gap are in `products`.
- **Pantry + USD** raises `ValueError("MEASURE_NOT_IN_MODE")`: the optimization package may not import `app.services.jobs` (`test_or_scope.py`), so the submit layer maps it to 422.
- **TDD note for W1-S03:** the S01 oracle tests drove the implementation; the extra S03 tests then passed on first run, so each was mutation-checked instead (ignoring edited weights fails `test_weights_editable`; relabeling FEASIBLE fails `test_native_status_preserved`). `test_native_status_preserved` patches `CpSolver.status_name` to report FEASIBLE while keeping CP-SAT's real solution.
- **Heuristics share the optimizers' feasible region:** same at-risk screen and the same per-product shares (`decompose.split`, in the comparison's measure); each request takes the largest quantity `verify.product_violations` accepts (binary search), and `verify_plan` re-checks the union. Tie-breaks are written at the top of `baselines.py`.
- **`compare_methods` gains keyword-only `scenario_id`, `scenario_hash` (and `search_seconds`)**: the frozen positional signature `(ORInputV3, methods, measure)` is unchanged, but `ComparisonResultV3` requires both ids and neither is derivable from `ORInputV3`. Approved by the orchestrator 2026-11-07.
- **Publication re-verification:** `compare.publishable` rebuilds every claimed-verified result from the raw scenario and its own plan (`methods.assemble`: pack, union check, effects, objective replay, labels, and the method status its products imply). A result with any differing field is published unverified with `PUBLICATION_VERIFICATION_FAILED:<fields or violations>` and no plan. A method that raises is reported as `METHOD_ERROR:<type>` and the others still publish.
- **k-nearest (W1-S05):** `v3.candidates` keeps, per product and receiver, the `K_NEAREST = 10` nearest senders that hold eligible stock (travel days, road miles, sender id; `candidates.k_nearest`). Packing and the verifier use the same candidate set.
- **Shared limits are split among the products that can use each limit** (the ones with a candidate on that route, sender, receiver/day or storage), by `floor_shares`; global handling and the cost budget among all at-risk products. This keeps the floor rule and never exceeds a limit, while an unrelated product on another route doesn't dilute a share.
- **Decision actions (W1-S06):** `proven_binding` means the independent verifier rejects the same plan with one more unit on that route, and the why text names the limit ("One more unit is infeasible: …"); otherwise `inferred`. The remove-one effect keeps every other transfer's exact batches (no re-pack, no re-optimization); deltas are `with plan − without this transfer` at the sender and receiver, and USD is that unit change × `unit_value_usd` (Retail only, `None` without a price). `decision_actions` takes `comparison_id` keyword-only, like `compare_methods`. Money prints as cents when exact (`v3.money`), because the schema normalizes `"10.00"` to `"10"`.
- **Export (W1-S07):** `export_plan_csv` takes the frozen `scenario` keyword-only (names, units, why/effect need it; `SavedComparisonV3` has no payload) and rejects a scenario from another network/mode (`SCENARIO_MISMATCH`). Columns: scenario_id, scenario_hash, method, network_mode, product, unit, quantity, from, to, ship_date, arrival_date, why, effect (signed deltas plus the non-additive label), note (`simulated plan; no stock was reserved or moved`, plus `; no scheduled deliveries provided` without an inbound file).
- **Pantry GP/EGP objective (`pantry.py`):** a per-product port of v2 `objective.attach` and `metrics.evaluate`.
  - Goals: pantries with a positive target inside the window (`planning_days`); hubs are never goals.
  - Weight v = 1 + λ × Σ coefficient × rate, from the exact `VulnerabilityV3` rates (EGP only).
  - Terms: q = floor(10000 × v × unmet / target), Z = max q, the β blend, then AP/RP flags reified both ways (equality unflagged) and the per-product excess.
  - ε_cost uses floor(10000 × cost / cost reference); ε_waste uses floor(10000 × expired / stock).
  - There is one RP group per product, so v2's 1 / (number of groups) factor is 1.
  - Coefficients compile to integers by LCM then GCD. `pantry_objectives` replays the same integer from the verifier's projection and plan; the assembly rejects a mismatch.
  - No fewer-units tie-break for Pantry: K × these coefficients could exceed the 2**60 audit at 100 × 500.
- **EGP groups and coverage:**
  - A product with fewer than two positive-target pantries is not optimized by EGP_PI_INSPIRED. It gets the label `relative-priority group has fewer than two pantries; EGP-PI not defined` (SPEC-V5 §11 / ADR 0001: reject singleton groups rather than fabricate a comparison). CLASSICAL_GP still optimizes it.
  - A pantry goal without a vulnerability row fails EGP as `ATTRIBUTE_POLICY_COVERAGE:<ids>`; the other methods run.
- **Localized capacity split (Gabriel, 2026-11-07; `decompose.allot`):**
  - **Users.** A receiver's limits (the route into it, receiving per arrival day, storage) go only to the products with positive need at that receiver. Need is the same measure as the at-risk screen, taken at that location.
  - **Weights.** Unchanged ("the same weights"): network need × handling, × unit value in USD.
  - **Rounding and starvation.**
    - Proportional floor shares are rounded down to whole units.
    - A product whose share can't fit one unit is held to exactly one unit's handling. These products are served largest weight first, then by product ID, while capacity lasts; the rest stay starved and labelled.
    - The others split the remaining capacity proportionally. If that pushes another product below one unit, it joins the one-unit group (a fixpoint), so the priority order holds across the whole group.
    - The sum never exceeds the limit.
  - **Unchanged limits.** Sender dispatch, global handling and the cost budget keep the plain floor split.
  - **Hand value changed.** `retail-usd-flip` USD becomes lettuce 1 + oil 3, total $126.00 (was oil 3 with lettuce starved, $128.00; README).
- **Heuristic probe speed (W1-S05):** `product_violations(..., changed_sender=)` replays only the changed sender and its receivers. Packing is FEFO per sender, so no other location's lots change, and the plan before the probe already passed. Shared limits are always summed over the whole plan. `verify_plan` still re-checks the union before publication.
- **TDD note for Pantry:** `pantry.py` was drafted before its tests, so every test was mutation-checked. Each of these mutations makes at least one test fail:
  - flagging AP at equality;
  - ignoring vulnerability;
  - dropping the singleton rule;
  - ignoring the window in goal targets.
- **Oracle test names:** one parametrized `test_fixture_matches_oracle[<fixture>-<measure>]` instead of six functions; the ids carry the fixture name.

## Gotchas

- One organization per network (W0-network-model §1): a v1 request's tenant is the organization of the network in its path, not the presenter session's. Tests that log in under the network's own organization hide this; log in under a separate one.
- `planning_comparisons_v3` rows are immutable (UPDATE/DELETE trigger). A publisher can't clean an orphan; atomic publication means there is none.
- `ORInputV3` (`apps/api/app/schemas/v1_planning.py:206`) uses string IDs and v1 caps, so it cannot be fed to the v2 pipeline (`ORInputPackage`, UUID IDs). The v3 methods get a v3-native path that reuses the pure FEFO kernel (`services/optimization/kernel.py`).

## Change requests

### CR-w1-solver-1 — Pantry allocation window and EGP policy in the frozen v3 scenario
- **File(s):** `apps/api/app/schemas/v1_planning.py` (`ORInputV3`, `ScenarioOptions`); the scenario builder in `apps/api/app/services/networks/` that freezes it; regenerated contracts in `packages/contracts`.
- **Exact change (orchestrator's proposal, 2026-11-07):** `ORInputV3` gains `planning_days: int` (1..3, required in PANTRY, absent in RETAIL, validated like `retail_weights`) and `policy: ORPolicy` (`app/schemas/or_inputs.py:422`; required in PANTRY, absent in RETAIL). `ScenarioOptions` takes both; the policy defaults to the connected-flow values and is recorded in the frozen scenario.
- **Why:** `ORInputV3` has neither field. v2 carries both explicitly (`or_inputs.py:515` `planning_days` 1..3; `ORScenarioPayload.policy`). BD-50 requires an explicit 1–3-day window, and V1-SPEC §6.2 requires λ/β/coefficients to be shown and editable, so they must be frozen with the scenario rather than hardcoded in the solver. Pantry need (window unmet), BD-51 (consumption inside the window), the at-risk screen for Pantry, and the CLASSICAL_GP/EGP_PI_INSPIRED objectives all read them.
- **Unblocks:** W1-S02 (EQUAL_SHARE, MOST_URGENT_FIRST), W1-S04 (Pantry five-method comparison), W1-S05 (Pantry at-risk screen and Pantry benchmark), W1-S06/S07 Pantry cases. Retail work proceeds meanwhile.
- **Status:** approved by Gabriel via the orchestrator, 2026-11-07; the lead lands it on `v1-local`. Field-dependent code reads `scenario.planning_days` and `scenario.policy` as proposed; nothing in this lane touches the contract.

### CR-w1-solver-2 — USD mode splits shared capacity by value
- **File(s):** none out of lane (`apps/api/app/services/optimization/decompose.py`, W1-S05); the orchestrator records it in `decisions/W0-optimizer-decomposition.md` at integration.
- **Exact change:** in Retail USD mode the shared-capacity and cost-budget split uses weight `need_p × handling_units_per_unit_p × unit_value_usd_p` (UNITS keeps `need_p × handling_units_per_unit_p`), still `cap × weight_p // Σ weight` with exact rationals.
- **Why:** per product, the USD objective is `price × units objective`, so without a value-weighted split no plan can change between measures (escalation below). This formula keeps the units weight (the handling footprint of the need, which is what capacity measures) and scales it by value, so with equal prices it reduces exactly to the units split; `need × value` alone would not.
- **Unblocks:** W1-S01 `retail-usd-flip` (binding capacity, plan changes) and `retail-usd-no-flip` (non-binding, same plan).
- **Status:** approved by Gabriel via the orchestrator, 2026-11-07.

### CR-w1-solver-3 — persistence for v3 scenarios and comparisons
- **File(s):** a new migration (`ppv1_0011`), `apps/api/app/models/` (lead-only); then `apps/api/app/workers/optimization.py` `V3_REGISTRATION` publisher and `apps/api/app/services/optimization/api_v3.py` (this lane).
- **Exact change (proposal):** two owned tables, network-scoped like `net_*`:
  - `planning_scenarios_v3(id, organization_id, network_id, recorded_at, content_hash CHAR(64), payload JSONB)`. This backs `ScenarioV3`; W1-D09 `create_scenario` writes it.
  - `planning_comparisons_v3(id, organization_id, network_id, scenario_id → planning_scenarios_v3, job_id, attempt_id, measure, recorded_at, result JSONB)`. This backs `SavedComparisonV3`, with the same job/attempt foreign keys and publication fence as `planning_comparisons`.
- **Why:** no table holds a `ScenarioV3` or a `SavedComparisonV3`. The v2 `planning_scenarios`/`planning_comparisons` are keyed to v2 forecast runs, `planning_assumptions` and the v2 operational hash (`app/models/optimization.py:25-73`). So the `or-comparison.v3` worker can't load a frozen scenario or publish a result, and `api_v3.submit_comparison`/`get_comparison` have nothing to read or write.
- **Unblocks:** W1-S04 worker publisher and `api_v3` submit/get; W1-S06 `comparison_actions` and W1-S07 `export_comparison` (both read a saved comparison). The pure functions (`compare_methods`, `decision_actions`, `export_plan_csv`) proceed meanwhile.
- **Status:** approved by Gabriel via the orchestrator, 2026-11-07. The lead writes `ppv1_0011` with `PlanningScenarioV3` → `planning_scenarios_v3` (id, organization_id, network_id, dataset_version_id, forecast_run_id, recorded_at, content_hash, payload JSONB) and `PlanningComparisonV3` → `planning_comparisons_v3` (id, organization_id, network_id, scenario_id, job_id, attempt_id, measure, recorded_at, result JSONB), both immutable, in `app/models/networks.py`, landing in the same PR as CR-w1-solver-1.

### CR-w1-solver-4 — advertise the built or-comparison.v3 handler
- **File(s):** `apps/api/tests/workers/test_v1_job_kinds.py` (lead-owned), only `test_v1_stub_handlers_are_not_advertised_for_execution`.
- **Exact change:** drop or-comparison.v3 from the set asserted not advertised; assert {or-comparison.v2, or-comparison.v3} are advertised. `test_v1_job_kinds_registered` unchanged.
- **Status:** approved by Gabriel via the orchestrator, 2026-11-07; landed with the real handler in bfdb21e.

### CR-w1-solver-5 — the job status route for v1 job kinds
- **File(s):** `apps/api/app/routers/forecasts.py` `job_status` (lead-owned).
- **Exact change:** admit the v1 contracts and resolve the job's organization server-side (the session's own, or a network organization on this install, per W0-network-model §2). `status_url` stays `/api/v1/jobs/{job_id}`.
- **Why:** the route allowed only v2/forecast contracts and the session organization, so it answered 404 for every or-comparison.v3 job.
- **Status:** approved by Gabriel, 2026-11-07; the lead lands it in the batch-2 PR. Not touched in this lane.

## Escalations

- 2026-11-07 — W1-S01 `retail-usd-flip` — spec ambiguity ([ORCHESTRATION.md §5](../ORCHESTRATION.md) item 4). The wave file asks for a fixture whose optimal RETAIL_OPTIMIZED transfer changes between units and USD. Under the W0 decision (`decisions/W0-optimizer-decomposition.md` §1–2, V1-SPEC §6.2) each product is solved alone. Its USD objective is `price_p × (w_exp × expired_p + w_lost × lost_p)`, a positive multiple of its units objective, so the argmin is the same. Shared capacity is split in advance by need × handling units, not by value. So no plan can flip between the measures. Smallest case: one product, any scenario, so the USD objective = price × the units objective. Two products sharing one route capacity give the same result, because the split doesn't depend on the measure. Resolved by CR-w1-solver-2 (option b, approved 2026-11-07). Options were: (a) keep the fixture as a "no flip under per-product solving" regression, with the hand-derived monolithic flip recorded in the README for reference; (b) split shared capacity in USD mode by need × handling × unit value (a change to the decision's split rule). The other four fixtures proceed.
