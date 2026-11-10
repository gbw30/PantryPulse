# S7 — forecast and backtest volume at 50,000 series (W3-F01)

**Question (V1-SPEC §12 item 7):** can one forecast run produce 50,000 series × 7 points, plus the 4-origin backtest, inside the 300 s forecast ceiling (270/300 s) and the 6-CPU / 8-GiB worker? What does it write, and how much storage does it use?

**Verdict: fits, with a compact network input. The existing per-day input does not fit.**

- **Compact path:** each series is frozen as a value array, run through the same adapters (seasonal naive, then the moving average), and backtested at 4 origins. 50,000 series take **10.4 s of compute** at a **1.7 GB peak RSS**, about 3.5 % of the ceiling. The output row is **8.7 MB** in PostgreSQL.
- **Existing `forecast.v1` input** (one `DemandRevision` per history day, re-prepared by every `validate_input`): **~10,700 s** and a **~4.5 GB** frozen input, extrapolated linearly from a 500-series sample. That is a lower bound. Its worker bounds (800 series, 60,000 observations) already refuse a network this size.
- **No ceiling change is needed.** W3-F06 does not file a CR to raise the 300 s ceiling.
- **Needed inside this lane, built by W3-F03:**
  1. Network runs use a compact frozen input: the last 42 days per series (the most any method reads, which is the moving average at origin 4) plus each series' observed and missing day counts. That is 8.5 MB at 50,000 series, under `forecast.v1`'s 16 MB input bound. **Corrected in W3-F06:** the shipped schema (named fields, the package around it) is 11.9 MB with these small synthetic quantities and 20.6 MB at the envelope's worst case (every day 100,000 units, 64-character IDs). 4-digit daily quantities already passed 16 MB, so W3-F06 raised `max_input_bytes` to 24 MB ([evidence](../../../forecasting/evidence/v1-forecast-scale.json)).
  2. The step returns compact points and backtest sums. The verbose `ForecastOutput` (106 MB of JSON at 50,000 series) is built only when publishing. The stored `forecast_runs.output` keeps the shape that `create_scenario` reads.
  3. `forecast.v1`'s `max_output_bytes` (4 MB, in this lane's `workers/forecasting.py`) is raised to fit the compact step output. The verbose output passes 4 MB at about 2,000 series.

Synthetic data: these numbers are timings and sizes, never accuracy evidence.

## Method

`apps/api/scripts/bench_forecast.py` (commit `94737e5` tree, plus this script). Synthetic, seeded history: N series × 90 days, a weekly pattern with Gaussian noise, and ~5 % blank days (unknown, never zero). Each part runs in its own process, so its peak RSS is its own.

```bash
cd apps/api && set -a && . ../../.env.lane && set +a
uv run --frozen python scripts/bench_forecast.py --part compact  --series 50000
uv run --frozen python scripts/bench_forecast.py --part existing --series 50000 --sample 500
uv run --frozen python scripts/bench_forecast.py --part db       --series 50000   # pantrypulse_forecast_test, scratch schema bench_s7_test, dropped after
```

Machine: Intel Core Ultra 9 285H, 16 logical CPUs, 15 GiB RAM, WSL2 (kernel 6.18.54.1), Python 3.12.13. Run 2026-11-08. Each process is single-threaded.

## Results

### Compact path, 50,000 series × 90 days

| Stage | Seconds |
|---|---|
| Freeze the 42-day window + counts (JSON) | 0.32 |
| Forecast: 7 points per series, seasonal naive then moving average | 1.25 |
| Backtest: 4 weekly origins per series, plus per-location roll-ups | 5.44 |
| Build the `ForecastOutput` model (what `forecast_runs.output` stores) | 2.78 |
| Serialize it | 0.48 |
| **Compute total** | **10.27** (wall 15.2 including data generation) |
| Re-read it, as `create_scenario` does on every freeze (outside the job) | 3.42 |

| Size | Value |
|---|---|
| Frozen input, 42-day window + counts | 8.5 MB |
| Frozen input, all 90 days (values only, for comparison) | 13.3 MB |
| `ForecastOutput` JSON | 106.0 MB |
| Peak RSS (everything in one process) | 1,714 MB |
| Series with a gap in the last 7 days (the moving average answers) | 15,006 |

### Storage on PostgreSQL (`--part db`, 50,000 series)

| Write | Rows | Seconds | On disk |
|---|---|---|---|
| One `forecast_runs`-shaped row, `output` JSONB (TOAST-compressed) | 1 | insert 1.65, read 1.13 | 8.7 MB |
| One backtest row per series (`backtest_scores` columns) | 50,000 | insert 0.48 | 8.5 MB |

Rows written: 50,001, about 17 MB in total. No `forecast_series` or `forecast_points` rows: their foreign keys point at the v2 `sites` and `products` tables, so a network run can't write them. `create_scenario` reads only `forecast_runs.output`.

### Publication lock after the #127 verifier's F1 (`--part lock`, 50,000 series, commit `6214126`)

`forecast.v1` runs through the real queue, supervisor and publisher in a scratch schema. The step runs in process, through the integration tests' fake driver. "Before" is the same harness with the publisher's `prepare` turned into a pass-through, so `publish` builds the run inside the lock, as at `e12fdc1`. The runs went back to back, alternating, at load 2.3–3.3 while another lane's full gate ran. Evidence key: `publish_lock_after_f1`.

| Run | Built | Lock held (`_lock_claimed` → COMMIT) | of which `publish` | `prepare`, outside the lock |
|---|---|---|---|---|
| after 1 | in `prepare` | 4.59 s | 3.93 s (the INSERT) | 6.44 s |
| before 1 | in `publish` | 9.85 s | 9.23 s (build + INSERT) | — |
| after 2 | in `prepare` | 3.68 s | 3.06 s (the INSERT) | 5.60 s |
| before 2 | in `publish` | 9.44 s | 8.81 s (build + INSERT) | — |

The lock time halves. What remains is the INSERT of the run row: a 106 MB output, the frozen input (12 MB here, 20.6 MB at the worst case) and the 9.4 MB backtest. PostgreSQL parses that JSONB and TOAST-compresses it inside the transaction. That is 3–4 s, close to the queue's 5 s lock timeout, and it is not removable without changing what the row stores.

### Existing `forecast.v1` path, 500-series sample × 90 days (42,794 history rows)

| Stage | Seconds (sample) |
|---|---|
| Build the `HistoryBundle` | 0.79 |
| `prepare` | 15.61 |
| `validate_input` (prepares again and compares) | 18.04 |
| `forecast` (seasonal naive) | 18.41 |

The handler validates the frozen input four times: at admission, in the step, and twice at publish. Extrapolated linearly to 50,000 series, that is **10,700 s** of compute, a **4,544 MB** frozen input and a 107 MB output. The sample alone peaked at 996 MB RSS. Linear extrapolation flatters it, because preparation keys every revision.

## Consequences for W3-F03 and W3-F06

- W3-F03 builds the compact network path described above. The existing v2 `POST /forecasts` path stays as it is (A22).
- `forecast_runs.output` at 50,000 series costs `create_scenario` about 4.5 s (read + validate). That is acceptable, and disclosed as a known limit.
- `GET /networks/{id}/forecasts/{run}` returns every series, as frozen (CR-w1-web-4). At 50,000 series the body is tens of MB. Pagination would be a contract change, recorded as a known limit for W4/W5.
- W3-F06 re-runs `--series 50000` on the built path and commits `docs/forecasting/evidence/v1-forecast-scale.json`.
