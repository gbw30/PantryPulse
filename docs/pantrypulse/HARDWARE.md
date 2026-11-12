# Hardware requirements

What PantryPulse v1 needs, from measurement (V1-SPEC §9, V1-A09, A17, A19). The [README](../../README.md#quickstart) quotes these figures. Re-measure with `node scripts/bench/run-all.cjs` (see the [testing guide](../testing/README.md#measurements-v1-a09-a17-a19)); it rewrites the table below from its JSON artifact, and `scripts/testing/tests/bench-report.test.cjs` checks that every number in the table is the artifact's own.

## Requirements

| Resource | Requirement | From the measurements |
|---|---|---|
| CPU | **4 cores available to Docker**: V1-SPEC's provisional figure, confirmed | Idle, the stack uses 0.7 of a core. Each heavy step averaged 0.7–1.0 cores under the worker's 6-CPU cap, so one step at a time uses under 2 cores in total. Single-core speed sets how long a comparison takes (see the ceiling margin below). |
| Memory | **8 GiB available to Docker**: provisional figure confirmed, with headroom | Idle stack peak 458 MiB. The largest step (Retail comparison, 100 × 500) peaked at 1,423 MiB, so the measured total is about 1.9 GiB. 8 GiB also lets the worker reach its 8 GiB ceiling (V1-SPEC §9). Less memory may work but is untested. The 16 GB machine recommendation is not measured. |
| Disk | **About 15 GB free**: provisional, only partly measured | Images 2.1 GiB (API 1,122 MiB, web 373 MiB, PostgreSQL 607 MiB) and a 101 MiB database after the first start. Not measured: Docker's build cache, the database after a maximum-size import, and the Chronos profile's provisional +10 GB. |
| Time | First run: build 2 min 07 s, then first start 27 s | Base images were already on the machine, so a clean machine adds their download. |

**Ceiling margin.** At 100 × 500, the slowest step was the Pantry comparison (every method, in units). It took 5 min 24 s of the 690 s comparison ceiling, all methods together under the 330 s per-method ceiling, on a fast laptop CPU. Each step averages about one core, so a CPU with about half this one's single-core speed could approach the ceiling. That is unverified; it is the first thing to check on slower hardware. The forecast used 52 s of its 300 s ceiling, and the import's job steps took 1 min 22 s.

## Measurements

<!-- bench:begin -->
Measured on Intel(R) Core(TM) Ultra 9 285H, 16 logical CPUs, 15.3 GiB RAM, Docker Desktop (kernel 6.18.58.1-microsoft-standard-WSL2); Docker 29.9.2 with 16 CPUs and 15.3 GiB for Docker. Commit `083885b` plus 9 uncommitted paths, none under `apps/` (listed in the artifact). Artifact: [bench-2026-11-12.json](../testing/evidence/bench-2026-11-12.json).

| Measure | Result | Started (UTC) |
|---|---|---|
| First-run build, `docker compose build --no-cache` (base images already downloaded) | 2 min 07 s | 2026-11-12T08:24:52Z |
| First start, `docker compose up --wait` (migrate, seed, web ready) | 27 s | 2026-11-12T08:26:59Z |
| Idle stack, all services | RAM 420 MiB (peak 458 MiB); CPU 66% of one core | 2026-11-12T08:28:26Z |
| Disk after first start | images 2.1 GiB; database 101 MiB | 2026-11-12T08:28:59Z |
| A09 import, 100 × 500 × 90 days (4,500,000 demand rows, 200,000 batches) | job steps 1 min 22 s (validate 1 min 07 s, prepare 13 s, publish 2 s); run 1 min 39 s; peak RAM 503 MiB; CPU 0.7 cores on average | 2026-11-12T08:29:02Z |
| A17 forecast, 50,000 series × 90 days, through the queue and publisher | 52 s; peak RAM 1092 MiB; CPU 0.8 cores on average | 2026-11-12T08:30:41Z |
| A17 Pantry comparison, 100 × 500, every method (units 5 min 24 s) | 6 min 11 s; peak RAM 1076 MiB; CPU 1.0 cores on average; 5/5 method results verified; union check passed on 5/5 | 2026-11-12T08:31:33Z |
| A17 Retail comparison, 100 × 500, every method (units 5 min 20 s, usd 3 min 30 s) | 9 min 36 s; peak RAM 1423 MiB; CPU 0.9 cores on average; 6/6 method results verified; union check passed on 6/6 | 2026-11-12T08:37:45Z |
<!-- bench:end -->

All optimizer products ended `OPTIMAL`. The baselines were verified, and the per-product union check passed on every result: 11 of 11 across the Pantry units run and the Retail units and USD runs. In each mode, 209 of the 500 products were at risk and optimized; the other 291 are "not at risk; not optimized" by design (decisions/W0-optimizer-decomposition.md).

## How these were measured, and their limits

- **One machine:** the reference laptop runs Windows 11 with Docker Desktop on WSL 2. Ubuntu 24.04 and macOS are not measured.
- **The host was shared:** other sessions were running tests. The 1-minute load average was 28 at the forecast's start (on 16 logical CPUs), so these timings are from a busy machine, not an idle one.
- **Build, first start, idle and disk** come from the lane's own stack (`docker compose`, with lane-local image tags), sampled with `docker stats`. `--no-cache` rebuilt every layer; the base images were already downloaded.
- **The benches ran natively, not in the worker container**, because `scripts/or/bench_v1.py` needs `git`, which the API image lacks. They ran pinned to 6 CPUs with `taskset -c 0-5` (the worker's cap), against the lane's `*_test` database. Peak RAM is the bench process's peak RSS; CPU is CPU time divided by wall time. They run the worker's own code paths: `bench_import.py` (validate, prepare, publish), `bench_forecast.py --part lock` (forecast.v1 through the queue, supervisor and publisher), and `bench_v1.py` (`compare_methods` plus the independent verifier and union check). PostgreSQL's own memory during the import was not measured, because that test database's container is shared with other lanes.
- **Commits:** the run started at `083885b`. While it ran, `016b429` was committed, which changes only `docs/`, so `bench_forecast.py` and `bench_v1.py` recorded `016b429` as their commit. No file under `apps/` differs between the two. The uncommitted paths at the start are listed in the artifact; none is under `apps/`.
- **The import bench predates w5-data D02.** `bench_import.py` (last changed in `d2c158b`) generates demand history for all 100 locations: 4,500,000 rows. After D02 (CR-w5-data-1, approved 2026-11-12), hubs carry no demand history, so the bench's maximum becomes 4,455,000 rows (1 hub and 99 pantries with demand). The A09 import should be re-measured on the post-D02 bench.
- Timings come from synthetic, seeded data at the maximum envelope. They are never accuracy evidence.
