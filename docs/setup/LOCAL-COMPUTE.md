# Local backend and Chronos compute

User-authorized setup resumed October 25, 2026; [V5 section 15.4](../pantrypulse/SPEC-V5.md#154-pauses-and-release-controls) records the scope. Existing running tasks must remain running. No Windows security policy, global WSL configuration, power setting, firewall rule or other application's runtime is changed by these files.

## Configuration

From the repository root, use the opt-in `compose.compute.yaml` overlay with `compose.yaml`. The existing project, PostgreSQL data and loopback ports are retained.

| Component | CPU ceiling | RAM ceiling | Address/storage |
|---|---:|---:|---|
| API | 1 | 1 GiB | `http://127.0.0.1:8000`, process health `/api/v1/health` |
| Development PostgreSQL 16 | 1 | 1 GiB | `127.0.0.1:55432`; existing `pantrypulse_pgdata` |
| Supervisor | 6 | 8 GiB | No public port; durable queue in `pantrypulse_dev` |
| Standalone model tools | 6 | 8 GiB | No public port; shared persistent model cache, ignored local outputs |
| Separate image builder | 2 | 3 GiB | `pantrypulse-compute-build`; existing default builder is unchanged |

Memory and swap are both capped at the stated container RAM size. CPU quota is distinct from library thread counts. Model smoke/benchmark commands use two inference threads and batch size four to reduce contention. The model tool and worker ceilings are not an invitation to run two expensive operations: the standalone runner bypasses the queue and must stay separate from active domain computation.

The preflight reports Windows free RAM separately from Docker VM `MemAvailable` and clean file cache. Following a large image import, WSL can hold many GiB of reusable file pages while Windows reports little free RAM. Heavy commands require either 4 GiB free host RAM, or sufficient already-resident clean cache **and** VM headroom (6 GiB for the 3-GiB builder, 10 GiB for model tools). The script does not drop kernel caches, alter WSL limits, stop workloads or equate container limits with reserved capacity.

The compute image uses Python 3.12.13, uv 0.11.15 and the existing frozen `forecast` dependency extra. No dependency lock or package source was changed. The Linux lock includes CUDA packages even for CPU use; this increases image/build storage. Downloaded model weights live in `pantrypulse-chronos-model-cache`, outside Git; forecasts and timings go to ignored `artifacts/chronos/`. No GPU is required or configured.

## Commands

```powershell
./scripts/compute-windows.ps1 Status
./scripts/compute-windows.ps1 Build
```

The build uses a separate bounded Docker builder without selecting it as the default. It exports through ignored `artifacts/compute-setup/compute-image.tar` and then loads that file, avoiding Windows Buildx's large in-memory `--load` buffer. A final Docker stage copies only the installed environment and application, leaving uv's dependency cache behind; the script checks the resulting image against Fly's 8 GB rootfs ceiling. The lock and package versions remain unchanged. Before starting a first supervisor, explicitly apply the existing jobs-only migration to the dedicated local development database:

```powershell
docker compose -f compose.yaml -f compose.compute.yaml --profile api up -d --no-recreate --no-build --wait api
docker compose -f compose.yaml -f compose.compute.yaml run --rm --no-deps worker python -m alembic upgrade head
./scripts/compute-windows.ps1 Start
```

`Start` preserves already-created services (`--no-recreate`), does not automatically build/migrate/seed, and never runs the test handler registry. Existing containers retain their actual resource settings; inspect them instead of assuming the overlay retroactively changed them. On this machine the previously stopped API/database containers were capped before they were started.

```powershell
./scripts/compute-windows.ps1 Prepare
./scripts/compute-windows.ps1 Smoke
./scripts/compute-windows.ps1 Benchmark
./scripts/compute-windows.ps1 Session
```

Preparation pins a full Hugging Face checkpoint SHA and reuses that pin. Inference runs offline with that cached checkpoint. Smoke/benchmark have a 295-second process budget plus at most five seconds for forced cleanup; model download has a separate setup budget. The interactive session remains open until `quit`. The script refuses standalone tools when a known worker attempt is active, needs recovery, or another Compose Chronos container is running. This is an operator guard, not transactional queue admission: do not submit jobs concurrently or launch a second runner from another terminal. It also refuses heavy setup/model commands when measured headroom is too low, without closing tasks.

## Product boundary

The API currently exposes process health only. The supervisor's `production` registry is empty: installing Chronos does not register a forecasting handler or expose a model HTTP API. Keep the internal test registry private. Job integration, presenter authentication, the Next.js same-origin proxy, domain migrations/seed, end-to-end behavior and the research gate remain required before public product release. In particular the current child environment allowlist does not forward model-cache configuration; review that deliberately when implementing the real forecast handler.

Do not point a local worker and a Fly worker at the same queue. Initial containment/recovery is single-host; cross-host takeover is not qualified. Never clear a quarantined lane or attest cleanup without independent evidence. Follow [worker recovery](WORKER-QUEUE.md).

## Verification record

Measured on October 25, 2026 against the working tree based on `e39f643a8f47471943980bfdb507bbc10cc7c962`:

| Check | Result |
|---|---|
| Laptop | Intel Core Ultra 9 285H, 16 logical CPUs, 31.36 GiB RAM; more than 570 GiB disk free after setup |
| Existing tasks | Preserved; no pre-existing container/process was stopped or reconfigured |
| Backend | HTTP health passed; PostgreSQL connection passed; OR-Tools 9.15.6755 native smoke OPTIMAL |
| Local worker | Production registry, generation 1, fresh persisted heartbeat, no active attempt/recovery; kernel CPU quota `600000/100000`, memory `8589934592` bytes |
| Jobs migration | `0001_jobs_foundation` applied only to local `pantrypulse_dev` |
| Image | Uncompressed layer total **6,112,538,624 bytes**, below Fly's 8 GB ceiling; Docker containerd's stored-image accounting includes additional compressed content |
| Checkpoint | Full `amazon/chronos-2`, SHA `29ec3766d36d6f73f0696f85560a422f50e8498c`, downloaded into persistent volume |
| Real offline smoke | **112 valid rows**: 16 simulated series × seven days; two threads, batch four, float32; no forecast-output warnings |
| Smoke prediction/RSS | 0.313 seconds prediction; cumulative process RSS high-water 1,227.6 MiB; Python/library imports are additional startup time |
| Ten warm predictions | Median **0.312 seconds**, maximum **0.331 seconds**, same resident model after one warm-up |
| Safeguard tests | 182 Linux health/model-helper/job/process-containment tests passed; API ruff passed |
| Configuration checks | All 17 configuration tests passed outside the restricted sandbox; Compose, PowerShell syntax and diff whitespace checks passed |
| Fly | Official CLI v0.4.122 installed/checksum verified; TOML and quoted worker profile checked offline; platform validation requires login |

See `artifacts/compute-setup/verification.json` and `artifacts/chronos/` for the local evidence. These are private, ignored operational outputs, not source-controlled fixtures. The model exercise uses 90 synthetic observations per series and the fixed October 24 cutoff. It is not a chronological accuracy/calibration evaluation, a real demand forecast, a complete resource-stress qualification or integrated application acceptance. The model is not kept resident after smoke/benchmark; use the explicit `Session` command when needed. No Fly resources were created or deployed, and no dependency lock was changed.
