# Hardware requirements

What PantryPulse v1 needs, from measurement (V1-SPEC §9, V1-A09, A17, A19). The [README](../../README.md#quickstart) quotes these figures. Re-measure with `node scripts/bench/run-all.cjs` (see the [testing guide](../testing/README.md#measurements-v1-a09-a17-a19)); it rewrites the table below from its JSON artifact, and `scripts/testing/tests/bench-report.test.cjs` checks that every number in the table is the artifact's own.

## Requirements

| Resource | Requirement | From the measurements |
|---|---|---|
| CPU | **4 cores available to Docker**: V1-SPEC's provisional figure, confirmed | Idle, the stack uses a third of a core. Each heavy step averaged 0.6–1.0 cores under the worker's 6-CPU cap, so one step at a time uses under 2 cores in total. Single-core speed sets how long a comparison takes (see the ceiling margin below). |
| Memory | **8 GiB available to Docker**: provisional figure confirmed, with headroom | Idle stack peak 435 MiB. The largest step (Retail comparison, 100 × 500) peaked at 1,455 MiB, so the measured total is about 1.8 GiB (1,890 MiB). 8 GiB also lets the worker reach its 8 GiB ceiling (V1-SPEC §9). Less memory may work but is untested. The 16 GB machine recommendation is not measured. |
| Disk | **About 15 GB free**: provisional, only partly measured | Images 2.1 GiB (API 1,122 MiB, web 373 MiB, PostgreSQL 607 MiB) and a 101 MiB database after the first start. Not measured: Docker's build cache, the database after a maximum-size import, and the Chronos profile's provisional +10 GB. |
| Time | First run: build 4 min 22 s, then first start 36 s | Base images were already on the machine, so a clean machine adds their download. The build ran while the host's 1-minute load rose from 8 to 43, so treat it as an upper figure for this laptop: the 2026-11-12 run built in 2 min 07 s and started in 27 s. |

**Ceiling margin.** At 100 × 500, the slowest step was the Pantry comparison (every method, in units). It took 3 min 33 s of the 690 s comparison ceiling, all methods together under the 330 s per-method ceiling, on a fast laptop CPU with the host's load at 3–4. On 2026-11-12, with the load near 28, the same step took 5 min 24 s, so load on a shared machine costs about half again. Each step averages about one core, so a CPU with about half this one's single-core speed could approach the ceiling. That is unverified; it is the first thing to check on slower hardware. The forecast used 42 s of its 300 s ceiling, and the import's job steps took 1 min 03 s.

## Measurements

<!-- bench:begin -->
Measured on Intel(R) Core(TM) Ultra 9 285H, 16 logical CPUs, 15.3 GiB RAM, Docker Desktop (kernel 6.18.58.1-microsoft-standard-WSL2); Docker 29.9.2 with 16 CPUs and 15.3 GiB for Docker. Commit `5b56347`. Artifact: [bench-2026-11-15.json](../testing/evidence/bench-2026-11-15.json). Host load is the machine's 1-minute load average, across its 16 logical CPUs (the artifact also has the 5- and 15-minute averages).

| Measure | Result | Started (UTC) | Host load, 1 min (start → end) |
|---|---|---|---|
| First-run build, `docker compose build --no-cache` (base images already downloaded) | 4 min 22 s | 2026-11-15T00:36:58Z | 8 → 43 |
| First start, `docker compose up --wait` (migrate, seed, web ready) | 36 s | 2026-11-15T00:41:19Z | 43 → 27.6 |
| Idle stack, all services | RAM 347 MiB (peak 435 MiB); CPU 33% of one core | 2026-11-15T00:42:56Z | 11.5 → 8.2 |
| Disk after first start | images 2.1 GiB; database 101 MiB | 2026-11-15T00:43:26Z | — |
| A09 import, 100 × 500 × 90 days (4,500,000 demand rows, 200,000 batches) | job steps 1 min 03 s (validate 36 s, prepare 26 s, publish 2 s); run 1 min 10 s; peak RAM 502 MiB; CPU 0.6 cores on average | 2026-11-15T00:43:28Z | 7.8 → 5.2 |
| A17 forecast, 50,000 series × 90 days, through the queue and publisher | 42 s; peak RAM 1078 MiB; CPU 0.8 cores on average | 2026-11-15T00:44:38Z | 5.2 → 4 |
| A17 Pantry comparison, 100 × 500, every method (units 3 min 33 s) | 4 min 10 s; peak RAM 1109 MiB; CPU 1.0 cores on average; 5/5 method results verified; union check passed on 5/5 | 2026-11-15T00:45:20Z | 4 → 3.2 |
| A17 Retail comparison, 100 × 500, every method (units 2 min 44 s, usd 2 min 31 s) | 5 min 47 s; peak RAM 1455 MiB; CPU 1.0 cores on average; 6/6 method results verified; union check passed on 6/6 | 2026-11-15T00:49:30Z | 3.2 → 1.7 |
<!-- bench:end -->

All optimizer products ended `OPTIMAL`. The baselines were verified, and the per-product union check passed on every result: 11 of 11 across the Pantry units run and the Retail units and USD runs. In each mode, 209 of the 500 products were at risk and optimized; the other 291 are "not at risk; not optimized" by design (decisions/W0-optimizer-decomposition.md).

## How these were measured, and their limits

- **One machine:** the reference laptop runs Windows 11 with Docker Desktop on WSL 2. Ubuntu 24.04 and macOS are not measured.
- **The host was shared:** other sessions were running gates and screenshot captures. The table gives the 1-minute load average at each step's start and end (16 logical CPUs). It peaked at 43 during the build and first start, then fell from 7.8 to 1.7 across the benches, so the build and first start are the figures most affected.
- **Build, first start, idle and disk** come from the lane's own stack (`docker compose`, with lane-local image tags), sampled with `docker stats`. `--no-cache` rebuilt every layer; the base images were already downloaded.
- **The benches ran natively, not in the worker container**, because `scripts/or/bench_v1.py` needs `git`, which the API image lacks. They ran pinned to 6 CPUs with `taskset -c 0-5` (the worker's cap), against the lane's `*_test` database. Peak RAM is the bench process's peak RSS; CPU is CPU time divided by wall time. They run the worker's own code paths: `bench_import.py` (validate, prepare, publish), `bench_forecast.py --part lock` (forecast.v1 through the queue, supervisor and publisher), and `bench_v1.py` (`compare_methods` plus the independent verifier and union check). PostgreSQL's own memory during the import was not measured, because that test database's container is shared with other lanes.
- **Commit:** the whole run, runner included, is commit `5b56347` with a clean tree (`dirty_paths` is empty; `bench_v1.py` and `bench_forecast.py` recorded the same commit). The artifact's `bench_versions` names the commit that last changed each bench: `bench_import.py` `09b6aba`, `bench_forecast.py` `86ee346`, `scripts/or/bench_v1.py` `408a86d`.
- **The import bench after w5-data D02.** Hubs carry no demand history (D02). The bench was revised (CR-w5-data-1, revised 2026-11-12, `09b6aba`) to import 100 pantries and no hub, because import validation doesn't require a hub, so it keeps the whole envelope: 100 × 500 × 90 = 4,500,000 demand rows. That keeps it comparable with the 2026-11-12 run, whose bench (`d2c158b`) also generated 4,500,000 rows.
- **The earlier run** ([bench-2026-11-12.json](../testing/evidence/bench-2026-11-12.json), at `083885b` with an uncommitted runner and the load near 28 during the benches) is kept for comparison.
- Timings come from synthetic, seeded data at the maximum envelope. They are never accuracy evidence.
