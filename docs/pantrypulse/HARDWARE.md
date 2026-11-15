# Hardware requirements

What PantryPulse v1 needs, from measurement (V1-SPEC §9, V1-A09, A17, A19). The [README](../../README.md#quickstart) quotes these figures. Re-measure with `node scripts/bench/run-all.cjs` (see the [testing guide](../testing/README.md#measurements-v1-a09-a17-a19)). It rewrites both generated sections below (the requirements and the measurements) from its JSON artifact, and `scripts/testing/tests/bench-report.test.cjs` checks that they match it and that the hand-written text states no measured figure.

## Requirements

<!-- summary:begin -->
| Resource | Requirement | From the measurements |
|---|---|---|
| CPU | **4 cores available to Docker**: V1-SPEC's provisional figure; no step has run under a 4-CPU limit yet | Docker had 16 CPUs, and the benches ran under `taskset` on 6. Idle, the stack's containers used 0.4 of a core in total. Each bench process averaged 0.6–1.0 cores; PostgreSQL's CPU during the benches is not included. Single-core speed sets how long a comparison takes (see the ceiling margin below). |
| Memory | **8 GiB available to Docker**: V1-SPEC's provisional figure; what was measured fits well within it | Idle, the stack's containers peaked at 332 MiB together. The largest bench process (the Retail comparison) peaked at 1,454 MiB, its largest child process's RSS. PostgreSQL's memory during the benches is not included, so these two are not a measured total. 8 GiB also lets the worker reach its 8 GiB ceiling (V1-SPEC §9). Less memory may work but is untested. The 16 GB machine recommendation is not measured. |
| Disk | **About 15 GB free**: provisional, only partly measured | Images 2.1 GiB (PostgreSQL 607 MiB, API 1,122 MiB, web 373 MiB) and a 101 MiB database after the first start. Not measured: Docker's build cache, the database after a maximum-size import, and the Chronos profile's provisional +10 GB. |
| Time | First run: build 1 min 00 s, then first start 24 s | Base images were already on the machine, so a clean machine adds their download. The build has no cache mounts, so `--no-cache` downloads every npm and Python package again; it depends on load and connection speed (the host's 1-minute load went from 1.5 to 9.5 during the build). |

**Ceiling margin.** At 100 × 500, the slowest comparison was Pantry in units: every method together took 3 min 25 s of the 690 s comparison ceiling, so each method stayed under the 330 s per-method ceiling, on this laptop's CPU. Each bench averages about one core, so a CPU with about half this one's single-core speed could approach the ceiling. That is unverified; it is the first thing to check on slower hardware. The forecast used 34 s of its 300 s ceiling, and the import's job steps took 53 s.
<!-- summary:end -->

## Measurements

<!-- bench:begin -->
Measured on Intel(R) Core(TM) Ultra 9 285H, 16 logical CPUs, 15.3 GiB RAM, Docker Desktop (kernel 6.18.58.1-microsoft-standard-WSL2); Docker 29.9.2 with 16 CPUs and 15.3 GiB for Docker. Commit `d92021b`. Artifact: [bench-2026-11-15.json](../testing/evidence/bench-2026-11-15.json). Host load is the machine's 1-minute load average, across its 16 logical CPUs (the artifact also has the 5- and 15-minute averages).

| Measure | Result | Started (UTC) | Host load, 1 min (start → end) |
|---|---|---|---|
| First-run build, `docker compose build --no-cache` (base images already downloaded) | 1 min 00 s | 2026-11-15T01:40:29Z | 1.5 → 9.5 |
| First start, `docker compose up --wait` (migrate, seed, web ready) | 24 s | 2026-11-15T01:41:29Z | 9.5 → 7.1 |
| Idle stack, all services | RAM 313 MiB (peak 332 MiB); CPU 40% of one core | 2026-11-15T01:42:53Z | 4.7 → 3.5 |
| Disk after first start | images 2.1 GiB; database 101 MiB | 2026-11-15T01:43:24Z | — |
| A09 import, 100 × 500 × 90 days (4,500,000 demand rows, 200,000 batches) | job steps 53 s (validate 32 s, prepare 20 s, publish 1 s); run 59 s; peak RAM 501 MiB; CPU 0.6 cores on average | 2026-11-15T01:43:26Z | 3.7 → 2.8 |
| A17 forecast, 50,000 series × 90 days, through the queue and publisher | 34 s; peak RAM 1066 MiB; CPU 0.8 cores on average | 2026-11-15T01:44:25Z | 2.8 → 2.1 |
| A17 Pantry comparison, 100 × 500, every method (units 3 min 25 s) | 3 min 52 s; peak RAM 1000 MiB; CPU 1.0 cores on average; 5/5 method results verified; union check passed on 5/5 | 2026-11-15T01:44:59Z | 2.1 → 1.9 |
| A17 Retail comparison, 100 × 500, every method (units 2 min 26 s, usd 2 min 31 s) | 5 min 33 s; peak RAM 1454 MiB; CPU 1.0 cores on average; 6/6 method results verified; union check passed on 6/6 | 2026-11-15T01:48:50Z | 1.9 → 1.8 |

All optimizer products ended `OPTIMAL`. Every method result, baselines included, was verified, and the per-product union check passed on 11 of 11 results across the Pantry units run and the Retail units and USD runs. In each optimizer run, 209 of the 500 products were at risk and optimized; the other 291 are "not at risk; not optimized" by design (decisions/W0-optimizer-decomposition.md).

- **Host load:** the 1-minute load average was at most 9.5 during the build, first start and idle sampling, and at most 3.7 during the benches.
- **Bench versions** (the commit that last changed each): `bench_import.py` `09b6aba`, `bench_forecast.py` `86ee346`, `bench_v1.py` `408a86d`. The import bench generated 100 locations × 500 products × 90 days.
<!-- bench:end -->

## How these were measured, and their limits

- **One machine:** the reference laptop runs Windows 11 with Docker Desktop on WSL 2. Ubuntu 24.04 and macOS are not measured.
- **A shared host:** other sessions on this machine held their gates, stacks and captures during the run. The table gives the host's 1-minute load average at each step's start and end, across all its logical CPUs.
- **Build, first start, idle and disk** come from the lane's own stack (`docker compose`, with lane-local image tags), sampled with `docker stats`. `--no-cache` rebuilt every layer; the base images were already downloaded.
- **The benches ran natively, not in the worker container**, because `scripts/or/bench_v1.py` needs `git`, which the API image lacks. They ran pinned to 6 CPUs with `taskset` (the worker's cap), against the lane's `*_test` database. Peak RAM is the largest child process's peak RSS (`getrusage`); CPU is CPU time divided by wall time. They run the worker's own code paths: `bench_import.py` (validate, prepare, publish), `bench_forecast.py --part lock` (forecast.v1 through the queue, supervisor and publisher), and `bench_v1.py` (`compare_methods` plus the independent verifier and union check). PostgreSQL's own memory and CPU during the benches were not measured, because that test database's container is shared with other lanes.
- **Commit:** the whole run, runner included, is the commit named above the table, with a clean tree; `bench_v1.py` and `bench_forecast.py` record the same commit in the artifact.
- **The import bench after w5-data D02.** Hubs carry no demand history (D02), so the bench was revised (CR-w5-data-1, revised 2026-11-12) to import pantries only, with no hub; import validation doesn't require one, so the bench still fills the whole V1 envelope of locations, products and days.
- **Earlier runs:** [bench-2026-11-12.json](../testing/evidence/bench-2026-11-12.json) (an uncommitted runner, on a much busier host) is kept for comparison. A loaded run earlier on 2026-11-15 was replaced by this one; its artifact is in Git at `d1d9800`.
- Timings come from synthetic, seeded data at the maximum envelope. They are never accuracy evidence.
