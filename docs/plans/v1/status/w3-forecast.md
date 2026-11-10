# Status — `w3-forecast`

**Lane:** `w3-forecast` · **Branch:** `lane/w3-forecast` · **Base SHA:** `0a4959359a447233e8ca5eea87b1917d70bd7de8` · **Last update:** `2026-11-09` · **Head:** the commit that carries this file

## Tasks

| Task | Status | Commit | Evidence (command → result) |
|---|---|---|---|
| W3-F02 | done | `94737e5` | `uv run --frozen pytest -q tests/forecasting/test_backtest.py` → 13 passed, 0 skipped |
| W3-F01 | done | `70dc30e` | S7 verdict **fits with a compact network input** ([S7](../spikes/S7-forecast-volume.md)): `bench_forecast.py --part compact --series 50000` → 10.27 s compute, 1,714 MB peak; `--part db` → 50,001 rows, 8.7 + 8.5 MB; `--part existing --sample 500` → ~10,700 s extrapolated (does not fit) |
| W3-F04 | done | `db08dde` | `uv run --frozen pytest -q tests/test_inventory_projection.py` → 71 passed, 0 skipped (6 new cases on `project_v3`). They passed on the first run: they characterize the existing kernel (W2-06 §3). A throwaway mutation check, one process per mutant, killed all 5 mutants: inbound counted twice, on hand from day 1 and arriving after demand fail all 4 kernel cases; ignored delivery expiry and on-hand-before-deliveries fail the FEFO case |
| W3-F03 | done | `0f0decd`, `eacf8b2` (backtest), merge `bdfb0cd`, this commit | After merging `origin/v1-local` (`ppv1_0014`, PR #123): `PP19_TEST_SCHEMA_ISOLATION=1 uv run --frozen pytest -q tests/forecasting tests/danger tests/test_v1_contract.py tests/networks tests/workers tests/test_inventory_projection.py tests/integration/{test_v1_backend_journey,test_forecast_api_postgres,test_worker_slice,test_v1_job_status}.py` → 443 passed, 0 skipped, including `test_backtest_persisted_and_served_by_get_backtest` (stored row, service and `GET /forecasts/{job_id}/backtest`, 404 for an unknown job). PR #127 review fix `700cf54`: windows end on the version's last history day, so the default as-of date keeps seasonal naive (`test_default_as_of_day_after_history_is_not_a_blank_day` red at `MOVING_AVERAGE`, fallback, missing 1; `test_network_window.py` gaps 0, 1, 3, 9) |
| W3-F05 | done | `86b5672` | `PP19_TEST_SCHEMA_ISOLATION=1 uv run --frozen pytest -q tests/danger/test_ranking.py` → 10 passed, 0 skipped (3 rule tests on hand-built projections; 7 on a Pantry and a Retail network through the real import and production `forecast.v1`, including both HTTP routes). A throwaway mutation check, one process per mutant, killed all 7 mutants: Pantry scoring expiry, no first-day tie-break, inbound ignored, HIGH moved to 0.60, wrong driving units, unknown demand treated as known, expiry winning ties. PR #127 review fix `700cf54`: unmet now wins a tie between locations too (`test_unmet_wins_a_retail_tie_between_locations`, red first). Related suites `tests/danger tests/forecasting tests/test_v1_contract.py tests/networks tests/test_inventory_projection.py tests/integration/test_v1_backend_journey.py` → 398 passed, 0 skipped |
| W3-F06 | done | `23c998d` (code), this commit (evidence) | `uv run --frozen pytest -q tests/forecasting/test_forecast_scale.py` → 2 passed: splitting the series (sizes 1, 2, 4, reversed) never changes the output (passed on the first run, it characterizes `compute`; a mutant reading another series' values is killed), and the worst-case input fits (red at 20,602,900 > 16,000,000 bytes, green after `max_input_bytes` → 24 MB). `bench_forecast.py --part built --series 50000` at `23c998d` → forecast job 12.5 s of 300 s, 1,094 MB peak, step output 13.4 MB of 32 MB, publish 4.2 s in the lock before the INSERT; `--part freeze` → 3.1 s history aggregate over 4.5 M rows. [Evidence](../../../forecasting/evidence/v1-forecast-scale.json). Related suites (forecasting, workers, danger, networks, contract, projection, 4 integration files) → 444 passed, 0 skipped |

Order: F02 → F01 → F04 → F03 → F05 → F06. F01 and F02 depend on nothing (wave-3.md), and S7 should time the real backtest code, not a stand-in. F04 depends on nothing; F03 needs F02; F05 needs F03 and F04.

## Save point 2026-11-09 (superseded: `ppv1_0014` merged, W3-F03 done)

- **Head:** the commit that adds this section, on top of WIP `eacf8b2`. Branch `lane/w3-forecast`, pushed; no PR yet.
- **Done:** W3-F01 `70dc30e`, W3-F02 `94737e5`, W3-F04 `db08dde`, W3-F05 `86b5672`, W3-F06 `23c998d` + `2339048` (evidence). W3-F03 is done except the backtest read.
- **WIP `eacf8b2` (waits on `ppv1_0014`):** `network.build_backtest` writes the BacktestResult body (by CSV ids, without its two ids) into `forecast_runs.backtest` in `publish_network`'s INSERT. `backtest.get_backtest` serves it from that row, using the network's tenancy, with 404 `FORECAST_RUN_NOT_FOUND` for any other job. The backtest `STUBS` row is removed. `test_backtest_persisted_and_served_by_get_backtest` is marked as waiting on `ppv1_0014`; it is **not skipped**.
- **Expected red until `ppv1_0014` is merged in:** every test that publishes a network run fails with `PUBLICATION_STORAGE_FAILED` because the column is missing: `tests/forecasting/test_network_forecast.py`, `tests/danger/test_ranking.py` (its 7 PostgreSQL tests) and the new backtest test. Non-database suites pass: `tests/test_v1_contract.py tests/forecasting/test_backtest.py tests/forecasting/test_forecast_scale.py` → 62 passed. Checked at `eacf8b2`: `build_backtest` builds on a small input (3 series, 2 roll-ups, 2 ineligible), and the only remaining failure is the missing column.
- **Exact next step:** when the lead says `ppv1_0014` is merged, run `git fetch && git merge origin/v1-local` (it also brings PR #122). Then run `PP19_TEST_SCHEMA_ISOLATION=1 uv run --frozen pytest -q tests/forecasting tests/danger tests/test_v1_contract.py tests/networks tests/workers tests/test_inventory_projection.py tests/integration/{test_v1_backend_journey,test_forecast_api_postgres,test_worker_slice,test_v1_job_status}.py` with `.env.lane` loaded, expecting 0 skipped. Fix anything red, commit "W3-F03: backtest persisted and served" with the status update, and push. Then run `--part built` again to measure the extra `build_backtest` time inside the publication lock, and add it to the evidence and the known limits.
- **Then finish:** `quick`, then `full` with `.env.lane` (0 skipped), then `/devkit:ship-check` with the `verifier` agent, then `gh pr create --base v1-local --head lane/w3-forecast --title "w3-forecast: backtest, network forecasts, inbound, danger ranking, volume"`.
- **For PR review (lead):** `forecast.v1` `max_input_bytes` 16 → 24 MB. Measured limits at 50,000 series, with their commands, are in "Known limits for the PR" below and in `docs/forecasting/evidence/v1-forecast-scale.json`.

## Next

1. **PR #127** (https://github.com/gbw30/PantryPulse/pull/127) is open into `v1-local`. `/code-review` found 2 issues, both fixed in `700cf54` (Gates). Wait for the orchestrator's review.

## Gates

| Gate | Commit | Result |
|---|---|---|
| `node scripts/quality/run.cjs quick` | `e532b2b` | PASS (web typecheck, web lint, api lint, api tests) |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | `e532b2b` | PASS, all 8 steps (adds web unit tests, web build, contract drift, database migrations) |
| Backend as CI runs it: `PP19_TEST_SCHEMA_ISOLATION=1 uv run --frozen pytest -q --junitxml=…` then `python scripts/quality/require-test-evidence.py …` | `e532b2b` | 2105 passed, 0 failed, 0 skipped; "2105 backend tests completed without skips or failures". Neither gate prints skip counts, and its plain `pytest -q` skips the PP19 opt-in suites, so this run is the 0-skipped evidence |
| `/code-review 127` (2 CLAUDE.md reviewers, 2 bug reviewers, each finding re-checked by its own validator) | `6c90f60` | 2 confirmed bugs, both fixed test-first in `700cf54`: (1) the window ended on the as-of date, which by default (V1-SPEC §6.1, both samples) has no history, so every series fell back to the moving average labeled `INSUFFICIENT_DATA` with `missing_count` one too high; (2) the location sort skipped "unmet before expiry". CLAUDE.md reviewers: no issues. The "out-of-horizon inbound in the expiry base" question is moot: `scenario._inbound` keeps `within_horizon` rows only |
| `node scripts/quality/run.cjs full` (with `.env.lane`) | `7961d1d` (merge of `origin/v1-local` `a2c7258`, #125/#126) | PASS, all 8 steps |
| Backend as CI runs it (as above) | `7961d1d` | 2118 passed, 0 failed, 0 skipped; "2118 backend tests completed without skips or failures" |
| `node scripts/quality/run.cjs quick` | `dd7ef76` (docs only on top of `7961d1d`) | PASS (web typecheck, web lint, api lint, api tests). The first run at `7961d1d` passed all 4 steps but refused the result, "source changed during checks", because this file was edited mid-run |
| `bench_forecast.py --part freeze --series 50000` | `7961d1d` | the new `_history_end` query: 0.24 s, run right after the backend suite (load 11.5); evidence key `freeze_history_end` |
| `/devkit:ship-check` | `15eb5f8` → `7d6718a` | Step 1 green. Step 2 was the project `verifier` (independent, read-only): no blocking defect, 373 passed / 0 skipped in its focused run, 0 of 3,000 mismatches against its own rolling-origin oracle, 4 Low findings. Three were fixed in `7d6718a` (an unscored backtest now reports not evaluated; two test oracles made independent); the fourth (`bias_pct` interpretation) goes to the lead. Step 3: security-guidance isn't installed. Steps 4–5: the PR, then `/code-review` |

## Decisions made inside the lane

- **A backtest with nothing scored is not evaluated:** 35+ calendar days where no origin can be scored (every fit window blank, or every scored actual blank) reports `not_evaluated_insufficient_history` with 0 origins, never `evaluated` without metrics (verifier finding, 2026-11-09). — W3-F02.
- **Lead-authorized edit of `apps/api/tests/test_v1_contract.py` (lead, 2026-11-09), in the merge of `origin/v1-local` only.** The merge conflicted on `STUBS`: #121 removed W3-P03 and this lane removed W3-F03/F05, so no route raises `NotImplementedV1` any more. As the lead decided: `STUBS`, `test_unimplemented_routes_return_501_with_task_id` (now an empty parameter set, so it would skip) and `test_network_scoped_job_routes_return_501` (it asserted nothing) are deleted. `test_not_implemented_v1_answers_501_with_task_id` keeps the 501 handler (`app/main.py:145`) covered through a throwaway route raising `NotImplementedV1("W3-TEST")`, with the same assertions. `tests/test_v1_contract.py` → 46 passed, 0 skipped. No other change to that file.
- **Network runs freeze a compact input** (`services/forecasting/network.py`). Per series: the last 42 days to the version's last history day, `history_end` (gap-explicit). The as-of date defaults to the day after that day (V1-SPEC §6.1), so the days between are not history and never count as blank; seasonal naive repeats each horizon day's prior comparable weekday across that gap (PR #127 review, `700cf54`). Also stored per series: plus observed, missing and sales-day counts, keyed by `net_locations.id`/`net_products.id`. The history is aggregated in PostgreSQL, so the 4.5 M history rows never enter Python. The policy is fixed (seasonal naive, then the moving average with a 14-day window and 3 samples, 14-day minimum), so a request can't choose Chronos. — W3-F03 (S7).
- **`forecast_run_id` = `job_id`** for network runs, like the existing publisher's `id = run_id = job_id`. `result_url` is `/networks/{id}/forecasts/{job_id}`. — W3-F03.
- **One step, per-series fallback:** each series tries seasonal naive, then the moving average. `fallback_reason` is seasonal naive's own `ProviderError` code, as in `service.forecast`. There is no whole-batch fallback step for networks. — W3-F03.
- **`required` = the series is AVAILABLE**, so a run with some ineligible series stays `planning_ready`. `create_scenario` then lists those series as "No available forecast, so no demand target (not zero)". This is the shape the W1 fixture used. — W3-F03.
- **Series basis:** `sales` if any of its rows is `sales` (the import's own `sales_basis_series` rule). A mixed series takes the conservative label. — W3-F03.
- **New stores are listed:** a pantry or store with stock or deliveries but no demand rows gets an `INSUFFICIENT_DATA` demand series, "No demand history rows for this location and product". It is never forecast from zeros (plan Review Focus 5). Hubs and DCs are not listed. — W3-F03.
- **Envelope:** more than 50,000 series (demand + donation) is refused at submit with 422 `FORECAST_SERIES_OVER_ENVELOPE`, never truncated. — W3-F03.
- **`forecast.v1` `max_output_bytes` 4 MB → 32 MB** (this lane's `workers/forecasting.py`). It caps both the step's stdout and the publish package, and the compact network output is about 11 MB at 50,000 series. The input stayed at 16 MB until W3-F06 (next entry). — W3-F03.
- **`forecast.v1` `max_input_bytes` 16 MB → 24 MB** (this lane's `workers/forecasting.py`). The network input at the envelope's worst case (50,000 series, 64-character IDs, every day 100,000 units) encodes to 20.6 MB; 4-digit daily quantities already passed 16 MB and submit refused them with `INPUT_TOO_LARGE`. S7's 8.5 MB used short keys and small quantities. `forecast.chronos.v1` keeps its own 16 MB (network runs never use Chronos). Precedent: `or-comparison.v3` is 64 MB. — W3-F06.
- **Tenancy helper:** reuses `optimization.api_v3._tenant` rather than adding a third copy. W2-06 §4 defers "one tenancy helper" to W4. — W3-F03.

- **Danger replays the run's own dataset version** (the version in its frozen input, not the network's latest) through `project_v3` with no transfers, the solver's rounded demand targets (`scenario._demand`), on-hand lots as `scenario._batches` keeps them and in-horizon inbound from `scenario._inbound`. Forecast, stock and deliveries then come from one snapshot. Published versions never change. — W3-F05.
- **Bands:** `HIGH` ≥ 0.50, `MEDIUM` ≥ 0.20, below is low (`services/danger/ranking.py`). The score is quantized to 0.0001, and the ranking uses that shown value. — W3-F05.
- **Shares:** unmet share = 7-day unmet / 7-day target, for a known target above 0. In Retail, expiry share = units expiring unsold in the horizon / (eligible on hand now + confirmed in-horizon inbound), for a product with dated stock. A hub or DC has no demand series, so in Retail its dated stock is scored by its expiry share (no local demand). — W3-F05.
- **Ties:** between a product's two shares, between products and between locations, the earliest first day of that loss wins, then unmet before expiry, then the ID (byte order). For an expiry-driven row, `first_deficit_date` is the first day stock expires unsold. — W3-F05.
- **Unknown is not zero:** a demand series that isn't AVAILABLE makes target, served and unmet unknown (`null` per day), and its expiry unknown too when it has dated stock. Its product is not scored. A location with no share gets no ranking row. `expiring_unsold` is `null` for a product with no dated lot; `donation_forecast` is `null` with no donation series, whole units otherwise (rounded as demand targets are). — W3-F05.

- **W3-F04 is tests only.** Per W2-06 §3, the projection the danger ranking uses is the solver's `project_v3`, which already counts frozen inbound once. `services/inventory/projection.py` (the P1 projection) is unchanged. The out-of-horizon case is pinned where `ORInputV3` refuses the row (`INBOUND_OUTSIDE_HORIZON`), because that is the only way into `project_v3`. — W3-F04.

- **`bias_pct` = 100 × Σ(prediction − actual) / Σactual** — the frozen field is a percentage, and V5 §7's bias (Σerror / n) is in units. This uses V5's error sign (positive = over-forecast) on WAPE's denominator, so the two metrics read one scored set and are both unavailable when Σactual = 0 (`test_zero_denominator_reports_none`). Both are rounded to 0.01 (half-even). — W3-F02.
- **Origins:** origin k (k = 1 nearest) is the weekly cutoff n − 7k. Its fit sees `history[:n − 7k]` and scores the next seven days. 4 × 7 + 7 prior days = the 35-day minimum, which is checked on the calendar length of the gap-explicit history. — W3-F02.
- **The backtest fit is the network forecast's own chain:** seasonal naive, then the labeled moving average (14-day window, 3 samples) when a prior weekday is missing. When neither can forecast at an origin, that origin is left out of the scored set (it adds nothing to `origins_evaluated`). — W3-F02.
- **`origins_evaluated`** counts the origins that contributed at least one scored pair. For a location roll-up it is the number of distinct origins pooled. A roll-up whose series are all under 35 days is `not_evaluated_insufficient_history`. — W3-F02.
- **No ceiling CR:** S7 measured 10.3 s of 300 s at 50,000 series on the compact path. W3-F06 re-measures on the built path. — W3-F01.

## Known limits for the PR (measured at 50,000 series, W3-F06)

Commands, from `apps/api` with `.env.lane` loaded: `uv run --frozen python scripts/bench_forecast.py --part built --series 50000` (the job, the publish lock, the danger ranking, sizes) and `… --part freeze --series 50000` (the submit's history aggregate). Measured at `23c998d`, on the machine in the evidence file.

- The submit request runs the history aggregate itself: 3.1 s over 4.5 M rows (`--part freeze`), in the API request's REPEATABLE READ transaction.
- Publishing builds the 106 MB `ForecastOutput` and the 9.4 MB backtest inside the publication lock: 4.2 s for the output at `23c998d` on a quiet machine. At `3d03fd1` (load average about 2.5) `build_backtest` adds 1.55–1.58 s, for 7.3–7.9 s in the lock before the INSERT (`--part built`, `publish_in_lock_s_before_insert`, `publish_build_backtest_s`; evidence key `publish_lock_with_backtest`). The INSERT comes on top (S7 `--part db`: 1.65 s for the output alone).
- `create_scenario` re-reads that 106 MB output (S7: about 4.5 s).
- `get_danger` and `get_projection` recompute per request: about 4 s of projection and ranking (`--part built`, `danger_ranking_s`), plus the run read, which re-validates the whole 106 MB output (S7: about 4.5 s), plus the batch SQL. `get_projection` for one location still reads and converts every series. Nothing is cached, and the read paths are not timed end to end (verifier, 2026-11-09).
- `GET /networks/{id}/forecasts/{run}` returns every series (tens of MB). Pagination would be a contract change.

## Gotchas

- **`queue.submit(..., deduplicate=True)` replays an identical frozen input to the existing job**, even after it succeeded, with `replayed=True`. Re-submitting a network forecast without a re-import returns the same run. Pinned in `test_list_forecast_runs_newest_first`.

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
- **Status:** decided 2026-11-09 (Gabriel, via the lead): **option B approved**. The lead lands `ppv1_0014` in its own PR into `v1-local`: `forecast_runs.backtest` JSONB NULL with a CHECK (NULL or a JSON object), and the ORM column `ForecastRun.backtest`. `backtest_scores` stays untouched. The lane asked for nothing else: no NOT NULL rule (v2 site runs stay NULL), no index (read by primary key).

## Escalations

(none)

## PR

PR #127, `lane/w3-forecast` → `v1-local`: https://github.com/gbw30/PantryPulse/pull/127. Its description is the PR body on GitHub (checked with `research-claims-check` on 2026-11-09: no forecast, accuracy or danger statement claims calibration, probability or real-world outcomes).
