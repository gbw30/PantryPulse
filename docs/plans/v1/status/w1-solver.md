# Status — `w1-solver`

**Lane:** `w1-solver` · **Branch:** `lane/w1-solver` · **Base SHA:** `39090104222e6a67b60f8d9fa0c9e798c68a38d7` · **Last update:** `2026-11-07` · **Head:** see `git log`

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W1-S01 | done (failing tests committed `xfail(strict=True)`; marks removed in W1-S03) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_retail_oracle.py` → 24 xfailed (`NotImplementedV1` / missing `verify_plan`), 0 passed, 0 skipped |
| W1-S02 | in progress: NO_TRANSFERS, SOONEST_EXPIRY_FIRST and the shared heuristic machinery (incl. EQUAL_SHARE/MOST_URGENT_FIRST code) done; the Pantry tests (equal-share/most-urgent hand values, Pantry hubs) wait on CR-w1-solver-1 | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_baselines.py` → 19 passed, 0 skipped; `tests/optimization` → 221 passed |
| W1-S03 | done for Retail; `test_bd51_relaxed_retail_only` Pantry half waits on CR-w1-solver-1 (Retail half `test_bd51_relaxed_retail_selling_on_day_5_counts` passes) | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_retail_oracle.py tests/optimization/test_retail_optimized.py` → 37 passed, 0 skipped; `tests/optimization` → 202 passed; `node scripts/quality/run.cjs quick` → PASS |
| W1-S04 | in progress: pure `compare_methods` done for Retail (independent failures, publication re-verification, v2 regression); Pantry five-method test waits on CR-w1-solver-1; `or-comparison.v3` worker publisher and `api_v3` submit/get blocked on CR-w1-solver-3 | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_compare_v3.py` → 9 passed, 0 skipped; `tests/optimization` → 230 passed |
| W1-S05 | Retail done: decomposition hardening, method search deadline, fast heuristic probe, localized capacity split (`test_allot_*`, `test_localized_split_only_products_with_need_at_receiver`), `scripts/or/bench_v1.py`, and Retail 100 × 500 evidence (`docs/optimization/evidence/v1-scale.json`). Pantry bench next | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization` → 287 passed, 0 skipped; `taskset -c 0-5 uv run --frozen python ../../scripts/or/bench_v1.py --locations 100 --products 500 --mode retail` → UNITS 130.9 s, USD 124.5 s; starved 0/209 (was 123/209, USD 150/209); all six results verified; exit 0 |
| W1-S06 | done for Retail (Pantry why text uses the window from CR-w1-solver-1, tested after merge); `api_v3.comparison_actions` waits on CR-w1-solver-3 | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_actions.py` → 8 passed, 0 skipped; `tests/optimization` → 256 passed |
| W1-S07 | in progress: pure `export_plan_csv` done (columns, selected actions only, scenario mismatch, unverified rejection, no-scheduled-deliveries note); `test_export_changes_no_stock` (PostgreSQL row counts around `api_v3.export_comparison`) waits on CR-w1-solver-3 | see `git log` | `uv run --frozen pytest -q -p no:cacheprovider tests/optimization/test_export.py` → 5 passed, 0 skipped; `tests/optimization` → 261 passed |

## Pause point (2026-11-07, Gabriel's stop)

- **Done and committed:**
  - W1-S01.
  - W1-S03 for Retail.
  - W1-S06 for Retail.
  - Pure W1-S04 (`compare_methods`) for Retail.
  - Pure W1-S07 (`export_plan_csv`).
  - W1-S05 for Retail: hardening tests, deadline, fast probe, bench and evidence.
  - Retail heuristics (W1-S02).
- **In progress (committed as WIP 3b60263):**
  - Pantry CLASSICAL_GP and EGP_PI_INSPIRED (`pantry.py`), wired into `methods.py`.
  - The `pantry-four-methods` fixture.
  - Its tests, parked as `tests/optimization/pending_cr1_pantry_methods.py` (not collected). They need `ORInputV3.planning_days`/`policy` and `DEFAULT_PANTRY_POLICY` from CR-w1-solver-1 (lead PR #103, not merged). Against a local stand-in for those fields, 21 passed, and four mutations were each caught. No Pantry test has run against the real schema.
- **Next step after #103 merges into `v1-local`:**
  1. `git fetch && git merge origin/v1-local`.
  2. Rename the parked module to `test_pantry_methods.py` and run it.
  3. Pantry bench (`--mode pantry`).
  4. CR-3 wiring: the `V3_REGISTRATION` handler and publisher in `workers/optimization.py` (insert `planning_comparisons_v3` with id = job_id); `api_v3` submit/get/actions/export, with GET returning 404 `COMPARISON_NOT_FOUND` before publication; `test_export_changes_no_stock` on PostgreSQL.
  5. Quick and full gates, ship-check, then the PR.
- **Retail 100 × 500 bench.** Run on the tree at 3b60263 (6b46700 plus Pantry wiring; Retail behaviour is identical). 6 CPUs (`taskset -c 0-5`), WSL2, seed 20261104.
  - Network: 100 locations, 500 products, 69 961 batches, 48 000 demand series, 960 routes.
  - Comparison wall time: UNITS 95.0 s, USD 77.9 s (ceiling 690 s). Total run 199.6 s, peak RSS 1.23 GB.
  - All six method results are verified, and every union check passes:

    | Measure | Method | Status | Transfers |
    |---|---|---|---|
    | UNITS | NO_TRANSFERS | — | 0 |
    | UNITS | SOONEST_EXPIRY_FIRST | — | 6 106 |
    | UNITS | RETAIL_OPTIMIZED | OPTIMAL | 5 546 |
    | USD | SOONEST_EXPIRY_FIRST | — | 5 029 |
    | USD | RETAIL_OPTIMIZED | OPTIMAL | 4 461 |

  - At-risk products: 209 of 500. Under the decision's advance split, 123 of them (USD: 150) are starved: "capacity share too small to move one unit". This reproduces the W0-10 review finding. The rule is kept and the counts are recorded; a localized-weight option is still to be raised with the lead.
  - History: the first run timed out at 25 min. Per-method profiling then showed SOONEST_EXPIRY_FIRST taking more than 23 min, NO_TRANSFERS 21.6 s and RETAIL_OPTIMIZED 55.6 s. The fix in 6b46700 brought the heuristic to 85.8 s with the same 6 106 transfers.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
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
- **Publication re-verification:** `compare_methods` re-runs `verify_plan` and recomputes effects for every result that claims verification; one that doesn't replay is published unverified with `PUBLICATION_VERIFICATION_FAILED:<violations>` and no plan. A method that raises is reported as `METHOD_ERROR:<type>` and the others still publish.
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

## Escalations

- 2026-11-07 — W1-S01 `retail-usd-flip` — spec ambiguity ([ORCHESTRATION.md §5](../ORCHESTRATION.md) item 4). The wave file asks for a fixture whose optimal RETAIL_OPTIMIZED transfer changes between units and USD. Under the W0 decision (`decisions/W0-optimizer-decomposition.md` §1–2, V1-SPEC §6.2) each product is solved alone. Its USD objective is `price_p × (w_exp × expired_p + w_lost × lost_p)`, a positive multiple of its units objective, so the argmin is the same. Shared capacity is split in advance by need × handling units, not by value. So no plan can flip between the measures. Smallest case: one product, any scenario, so the USD objective = price × the units objective. Two products sharing one route capacity give the same result, because the split doesn't depend on the measure. Resolved by CR-w1-solver-2 (option b, approved 2026-11-07). Options were: (a) keep the fixture as a "no flip under per-product solving" regression, with the hand-derived monolithic flip recorded in the README for reference; (b) split shared capacity in USD mode by need × handling × unit value (a change to the decision's split rule). The other four fixtures proceed.
