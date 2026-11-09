# Status — `w3-forecast`

**Lane:** `w3-forecast` · **Branch:** `lane/w3-forecast` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-08` (save point, W3 paused by Gabriel) · **Head:** the commit that carries this file

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-F02 | done | `94737e5` | `uv run --frozen pytest -q tests/forecasting/test_backtest.py` → 13 passed, 0 skipped |
| W3-F01 | done | `70dc30e` | S7 verdict **fits with a compact network input** ([S7](../spikes/S7-forecast-volume.md)): `bench_forecast.py --part compact --series 50000` → 10.27 s compute, 1,714 MB peak; `--part db` → 50,001 rows, 8.7 + 8.5 MB; `--part existing --sample 500` → ~10,700 s extrapolated (does not fit) |
| W3-F04 | in progress (not started: no edits yet) | — | — |
| W3-F03 | todo | — | — |
| W3-F05 | todo | — | — |
| W3-F06 | todo | — | — |

Order: F02 → F01 → F04 → F03 → F05 → F06. F01 and F02 depend on nothing (wave-3.md), and S7 should time the real backtest code, not a stand-in. F04 depends on nothing; F03 needs F02; F05 needs F03 and F04.

## Resume here: W3-F04, exact next step

The save point fell between tasks. No W3-F04 file has been touched; the tree is clean at the head.

1. **RED:** append five cases to `apps/api/tests/test_inventory_projection.py`, and add `# covers: V1-A23` as its first line. Per W2-06 §3, the cases test `app.services.optimization.projection.project_v3`, not `services/inventory/projection.py`. Build scenarios from `tests.optimization.test_retail_oracle.load("retail-nothing-to-move")`: store `A`, product `P` (case), planning days 2026-11-02 to 11-08. Replace `batches`, `demand` (A × P only) and `inbound`, set `inbound_file_provided=True`, and re-validate with `ORInputV3.model_validate`. The hand tables, days d1–d7:
   - `test_inbound_enters_once_on_arrival_date_arrivals_first`: no stock, inbound 10 on d3, demand 4/day → served `[0,0,4,4,2,0,0]`, unmet `[4,4,0,0,2,4,4]`.
   - `test_inbound_not_also_counted_on_hand`: batch 5 + inbound 10 on d2, demand 20 on d7 only → d7 served 15, unmet 5; on-hand d1 = 5, d2 = 15.
   - `test_outside_horizon_inbound_excluded`: `ORInputV3` rejects an arrival on 11-09 or on 11-01 (as-of). `scenario._inbound` already drops `within_horizon = false` rows; the frozen schema is the boundary.
   - `test_inbound_expiry_applies_fefo`: batch 6 (expiry d5), inbound 4 on d2 (expiry d3), demand 2/day → served `[2,2,2,2,2,0,0]` and expired all 0. Batch-first would waste 2 of the inbound.
   - `test_golden_arithmetic_with_inbound`: put the table in the docstring. Batch 8 (expiry d2), inbound 6 on d3 (expiry d4), inbound 5 on d5 (non-expiring), demand 3/day → served `[3,3,3,3,3,2,0]`, unmet `[0,0,0,0,0,1,3]`, expired `[0,2,0,0,0,0,0]`, on-hand `[5,2,3,0,2,0,0]`. Check: 8 + 6 + 5 = 17 served + 2 expired.
2. These characterize an existing kernel, so they may pass on the first run. If they do, run a throwaway mutation check (not committed) from the scratchpad: monkeypatch `project_v3`'s inbound so it counts twice, or so it arrives a day early, and show that each case fails. Record that in this file. If any case fails against `project_v3`, it is a solver-lane bug: stop and file a CR, because `services/optimization/**` is not this lane's path.
3. Commit "W3-F04: …" with this file, then push.

## W3-F03 design notes (from the survey; not started)

- **Compact `forecast.v1` network payload** (S7): `{"network_forecast": {...}}`, frozen at submit by `services/forecasting/network.py`. It holds the last 42 days per series plus observed/missing counts, keyed by `net_locations.id`/`net_products.id`. Its step output is compact; the publisher builds the stored `ForecastOutput`. Raise `forecast.v1` `max_output_bytes` (4 MB, this lane's `workers/forecasting.py`) to fit the compact step output, about 8 MB at 50k series.
- **Ineligible series** (< 14 observed days, or all blank) are `required=False` and `INSUFFICIENT_DATA`, so the run stays `planning_ready`. `create_scenario` already lists them as "No available forecast, so no demand target (not zero)".
- **Backtest persistence is CR-w3-forecast-1 (filed, open).** W3-F03 builds everything else first; `get_backtest` and `test_backtest_persisted_and_served_by_get_backtest` wait for the decision.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | | |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | | |
| `/devkit:ship-check` | | |

## Decisions made inside the lane

- **`bias_pct` = 100 × Σ(prediction − actual) / Σactual** — the frozen field is a percentage, and V5 §7's bias (Σerror / n) is in units. This uses V5's error sign (positive = over-forecast) on WAPE's denominator, so the two metrics read one scored set and are both unavailable when Σactual = 0 (`test_zero_denominator_reports_none`). Both are rounded to 0.01 (half-even). — W3-F02.
- **Origins:** origin k (k = 1 nearest) is the weekly cutoff n − 7k. Its fit sees `history[:n − 7k]` and scores the next seven days. 4 × 7 + 7 prior days = the 35-day minimum, which is checked on the calendar length of the gap-explicit history. — W3-F02.
- **The backtest fit is the network forecast's own chain:** seasonal naive, then the labeled moving average (14-day window, 3 samples) when a prior weekday is missing. When neither can forecast at an origin, that origin is left out of the scored set (it adds nothing to `origins_evaluated`). — W3-F02.
- **`origins_evaluated`** counts the origins that contributed at least one scored pair. For a location roll-up it is the number of distinct origins pooled. A roll-up whose series are all under 35 days is `not_evaluated_insufficient_history`. — W3-F02.
- **No ceiling CR:** S7 measured 10.3 s of 300 s at 50,000 series on the compact path. W3-F06 re-measures on the built path. — W3-F01.

## Gotchas

- **`forecast.v1` can't carry a network as it stands.** Its frozen input is one pydantic `DemandRevision` per history day, re-prepared by every `validate_input` (4× per job). That came to 53 s for 500 series, ~10,700 s extrapolated to 50k, and its worker bounds are 800 series, 60k observations, 16 MB in and 4 MB out. The verbose `ForecastOutput` passes 4 MB at about 2,000 series. (S7)
- **Step children have no database connection** (`workers/child.py`): the job input must carry everything a step reads. Only the publisher (`validate`, the optional `prepare` and `publish`) runs in the supervisor with the engine.
- **`forecast_series` / `forecast_points` have foreign keys to the v2 `sites`/`products`**, so a network run (keyed by `net_locations.id`/`net_products.id`, W1-D09) can't write them. `create_scenario` reads only `forecast_runs.output`, so a network run writes that row alone.
- **`forecast_runs.output` at 50k series is 106 MB of JSON but only 8.7 MB stored** (TOAST). Re-reading and validating it costs `create_scenario` about 4.5 s per freeze.
- **`ORInputV3` rejects inbound outside the planning days** (`v1_planning.py:298`), so out-of-horizon rows never reach `project_v3`; `scenario._inbound` filters on `within_horizon`.

## Change requests

### CR-w3-forecast-1 — persist each forecast run's backtest so `GET /forecasts/{job_id}/backtest` can serve it

- **File(s):** a new lead migration `apps/api/migrations/versions/ppv1_0014_*.py` (`down_revision = "ppv1_0013"`), and one model: option B changes `apps/api/app/models/forecasts.py` (`ForecastRun`); option A changes `apps/api/app/models/networks.py` (`BacktestScore`). Both are lead-only.
- **Why:** `BacktestResult` (frozen, W0-08 / CR-w1-web-4) needs, per demand series, `score.origins_evaluated`, and per location × unit a `LocationBacktest` scored on the **pooled** set: Σ|error| / Σactual over all of that location's series in that unit, never a mean of WAPEs (`test_location_rollup_from_series`). `backtest_scores` (ppv1_0008) can't serve either:
  - it has no `origins_evaluated`;
  - it stores only the ratios `wape`/`bias`, not the sums a pooled roll-up needs (Σ|error|, Σerror, Σactual can't be recovered from the ratios);
  - its only key is the dataset version (`UNIQUE (dataset_version_id, location_id, product_id, series_kind, method)`), but `GET /forecasts/{job_id}/backtest` asks for one run. Two runs on one version under different policies would collide.

  Nothing writes `backtest_scores` today (only its model and `tests/integration/test_v1_schema.py` reference it), so either option is safe for existing data.
- **Option A — extend `backtest_scores` (one row per demand series):**
  - add `forecast_run_id uuid NOT NULL`, with the tenant FK `(organization_id, forecast_run_id) → forecast_runs (organization_id, id)`;
  - replace the unique key with `UNIQUE (forecast_run_id, location_id, product_id, series_kind)`; `method` stays as a label;
  - add `origins_evaluated integer NOT NULL`, `CHECK (origins_evaluated BETWEEN 0 AND 4)` and `CHECK (evaluated OR origins_evaluated = 0)`;
  - add `abs_error_sum numeric`, `error_sum numeric` and `actual_sum numeric`, NULL exactly when `NOT evaluated`, with `abs_error_sum >= 0` and `actual_sum >= 0`;
  - widen `wape`/`bias` beyond `numeric(12,6)`, or store them unbounded. They hold percentages, and an over-forecast against a tiny actual (actual 1, prediction 10⁶ → 10⁸ %) overflows 12,6.

  Reads: the location rows come from a `SUM(...) GROUP BY location_id, unit` over up to 50,000 rows per request (unit via `net_products`). Writes: 50,000 rows inside the publication transaction (0.48 s in S7).
- **Option B — one `forecast_runs.backtest` JSONB column:**
  - `ALTER TABLE forecast_runs ADD COLUMN backtest jsonb NULL`, plus `CHECK (backtest IS NULL OR jsonb_typeof(backtest) = 'object')`. Downgrade drops both. NULL for every v2 run and for existing rows.
  - `ForecastRun.backtest = mapped_column(JSONB)`.
  - Stored shape: the `BacktestResult` body without `forecast_job_id` and `network_id`, which come from the row: `{"series": [SeriesBacktest], "locations": [LocationBacktest], "ineligible": [IneligibleSeries]}`, keyed by the CSV ids of the run's dataset version.
  - Only the `forecast.v1` network publisher writes it, in the same `INSERT` as the run row. Only `get_backtest` reads it: one row, validated with `BacktestResult`.
- **Recommendation: B.** The backtest is a property of exactly one run: the same frozen input, policy and method chain, and like `output` it never changes after publish. Keeping it on the run row gives one write in the insert the publisher already does, no extra 50,000-row insert inside the queue lock, and one row read per `GET`. The pooled roll-ups are computed once at publish from the exact sums (`ScoredSet`, W3-F02), so no sums need storing and nothing overflows. A needs five column changes, a new key and a 50,000-row aggregate on every read to rebuild what the publisher already computed. B leaves `backtest_scores` unused: the lead can drop it in the same migration or keep it for a later queryable view.
- **Unblocks:** W3-F03's `get_backtest` and `test_backtest_persisted_and_served_by_get_backtest`; the `GET /forecasts/{job_id}/backtest` row in `STUBS`.
- **Status:** open (orchestrator and Gabriel decide; the lead lands any migration).

## Escalations

(none)
