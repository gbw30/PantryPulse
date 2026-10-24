# Run Chronos-2 on your Windows laptop

> **Current authority:** [Project specification V5](docs/pantrypulse/SPEC-V5.md). Standalone model-exercise guide, not an integrated forecast service. V5 records its unverified execution status, distinct scope and setup pause; reading this guide does not resume heavy model work.

A step-by-step guide for PantryPulse · Updated October 24, 2026

**What you will get:** real Chronos-2 forecasts running on your CPU, a reusable model download, an interactive session that keeps the model loaded, and saved forecasts/timing records.

**Current boundary:** this is a standalone model runner using simulated data. It does not start a forecast API, connect to Neon, or complete the PantryPulse user interface or allocation engines. Those integrations are still pending. The commands below reference supporting files included in this repository; none is a fictional future endpoint.

**Verification status (October 24, 2026):** helper lint/format checks and eight offline safeguard tests pass. The standard `npm run check` passes web typechecking/lint, API lint and all 437 API tests, including those eight safeguards. All 17 configuration tests pass. Compose configuration, local documentation links and PowerShell syntax were checked. The optional image has **not** been built and the model has **not** been downloaded or executed. Complete the first forecast and benchmark steps on the actual laptop before claiming model readiness or performance.

## Contents

1. [What you need](#1-what-you-need)
2. [First-time setup](#2-first-time-setup)
3. [Download and pin the model](#3-download-and-pin-the-model)
4. [Run your first forecast](#4-run-your-first-forecast)
5. [Start a presentation session](#5-start-a-presentation-session)
6. [Measure performance](#6-measure-performance)
7. [Close down safely](#7-close-down-safely)
8. [Optimizations and considerations](#8-optimizations-and-considerations)
9. [Troubleshooting](#9-troubleshooting)
10. [Connect this to PantryPulse](#10-connect-this-to-pantrypulse)
11. [Presentation-day checklist](#11-presentation-day-checklist)

## 1. What you need

| Item | What to do |
|---|---|
| Windows x64 laptop | Evaluate CPU inference with enough available memory for the envelope below; actual latency still needs measurement |
| Docker Desktop | Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/), finish its setup and use **Linux containers** |
| WSL 2 / virtualization | Follow Docker's prerequisites; enabling them may need administrator access and a reboot |
| PantryPulse checkout | Use the existing repository, or clone it using Git for Windows |
| Free memory | Close unused applications; aim for roughly **10–12 GiB available before starting** as operating headroom, not a published model minimum |
| Free disk | Allow **30 GB or more** initially for Docker images, dependency downloads, build cache and model files; actual usage varies |
| Internet | Needed for first-time image/dependency/model downloads; prepared model inference uses downloaded files only |

You do **not** need a GPU, CUDA driver, paid model endpoint, Fly.io, DigitalOcean, or database credentials for these model exercises. Public model download normally needs no Hugging Face login. Do not enter Neon credentials here.

Docker installs the required Python and uv environment inside the image. You do not need to install a second Python/PyTorch stack on Windows. The complete web/API project has additional prerequisites in [INSTALLATION.md](INSTALLATION.md).

> **Why Docker?** Native Windows Application Control previously blocked a pandas library required by our backend. This guide uses the Linux container path without changing Windows security policy.

## 2. First-time setup

### Step 2.1 — Open the repository

Open PowerShell and substitute the location of your checkout:

```powershell
Set-Location 'C:\path\to\PantryPulse'
```

Stay in the repository root for **every PowerShell command in this guide**.

Confirm the supporting files exist:

```powershell
Test-Path compose.chronos.yaml
Test-Path apps/api/Dockerfile.chronos
Test-Path apps/api/scripts/chronos_local.py
```

**Expected:** all three return `True`.

### Step 2.2 — Start Docker Desktop

Open Docker Desktop and wait for its engine to report ready. Then run:

```powershell
docker --version
docker compose version
docker info --format '{{.OSType}}'
```

**Expected:** versions are printed and the final command returns `linux`. A missing-pipe/engine connection error means Docker is not ready; do not continue until that is resolved.

### Step 2.3 — Check resource headroom

Open **Task Manager → Performance → Memory**. Close unused browsers, development servers and other memory-heavy work. Keep the laptop plugged in and prevent sleep during the presentation.

The supplied Compose file limits this runner to **6 CPUs and 8 GiB RAM**. This is a starting envelope, not reserved memory and not proof that enough host RAM is free. Docker/WSL must have access to at least those resources. WSL resource settings can affect other Linux workloads: review them deliberately rather than overwriting an existing configuration.

For the first model check, leave unrelated API containers and builds stopped if they are not needed. Do not run an image build and model benchmark at the same time.

### Step 2.4 — Build the optional model image

```powershell
docker compose -f compose.chronos.yaml config --quiet
docker compose -f compose.chronos.yaml build chronos
```

**Expected:** validation succeeds, then the image builds without errors. The first build can download several GB. Later builds reuse Docker's cache when dependencies are unchanged.

This image installs the existing locked `forecast` extra, including Chronos 2.3.2. It does not change `apps/api/Dockerfile`, the API's default dependencies, or the native Windows environment.

**Packaging consideration:** the current lock selects Linux PyTorch packages with CUDA-related dependencies even though this runner uses CPU inference. These increase download/disk use; they do not require using a GPU. A smaller CPU-only image needs a separately reviewed uv source/lock change. Do not replace locked packages manually with unrelated pip commands.

Inspect installed model-library versions:

```powershell
docker compose -f compose.chronos.yaml run --rm chronos status
```

**Expected:** package versions and `No checkpoint pin yet` on a fresh setup. This proves package availability only, not model inference.

## 3. Download and pin the model

Do this **once while online**, before the presentation:

```powershell
docker compose -f compose.chronos.yaml run --rm chronos prepare
```

The helper:

1. Resolves `amazon/chronos-2` to an actual full commit SHA on its first run.
2. Downloads that exact checkpoint into a persistent Docker volume.
3. Saves the model ID and revision only after the download succeeds.
4. Reuses that same pin on subsequent preparation runs instead of silently upgrading it.

**Expected:** `Download complete` and a JSON model ID/revision. Record that revision with the demo release. A dependency lock alone does not pin model weights.

If a download is interrupted, rerun `prepare`. If you already have a completed pin, the command retains it. Do not delete the volume just to retry a network error.

Verify the saved pin:

```powershell
docker compose -f compose.chronos.yaml run --rm chronos status
```

**Expected:** the package versions and the same full revision SHA. The volume is named `pantrypulse-chronos-model-cache`.

Source: [Hugging Face revision-specific downloads](https://huggingface.co/docs/huggingface_hub/guides/download).

## 4. Run your first forecast

```powershell
docker compose -f compose.chronos.yaml run --rm chronos smoke
```

This command loads the downloaded model on CPU and runs **actual neural inference**. It does not download missing model files automatically. If preparation is incomplete, it fails with an actionable error.

The exercise uses a reproducible simulated input:

| Input | Value |
|---|---|
| Beneficiary demand | Six institutions × two categories = 12 series |
| Hub donations | Two hubs × two categories = 4 additional series |
| History | 90 daily observations per series |
| Historical cutoff | October 24, 2026; fixed for reproducibility |
| Forecast horizon | Seven days: October 25–31, 2026 |
| Model settings | Full Chronos-2, CPU, float32, four inference threads |
| Grouping | Independent series; cross-learning explicitly disabled for this exercise |

**Expected:** `Model loaded on CPU`, then `REAL INFERENCE: 112 rows`, a measured duration and an output location. All required series/dates, finite quantiles and quantile ordering are checked. This is not an accuracy evaluation or proof of working allocation features.

### Find the results

Open the repository's `artifacts/chronos` folder:

- `synthetic-history.csv` — the simulated historical inputs.
- `forecast-....csv` — one genuine inference result per command.
- `forecast-....json` — checkpoint, input hash, settings, timing, cumulative process-memory high-water mark and warnings.

In a CSV, **`0.5` is the median forecast**. The `predictions` column is not to be relabeled as the median. `0.1` and `0.9` are raw model quantiles, not calibrated confidence intervals. Negative raw quantiles are retained and warned about; no silent clipping or invented uncertainty is applied.

The helper keeps demand and donation labels separate. Donation predictions are not confirmed inventory. Files are local outputs, not records inserted into Neon. `artifacts/` is Git-ignored.

## 5. Start a presentation session

After first-time setup, this is the normal way to start the model:

```powershell
docker compose -f compose.chronos.yaml run --rm --name pantrypulse-chronos-session chronos session
```

Wait until you see:

```text
Model loaded on CPU ...
Commands: forecast (real inference), benchmark, quit. Model stays loaded.
chronos>
```

You are now inside the model runner. **The commands below are typed at `chronos>`, not in PowerShell.**

| Type | What happens |
|---|---|
| `forecast` | Runs a fresh forecast and saves new CSV/JSON files |
| `benchmark` | Runs one warm-up plus ten measured forecasts by default |
| `quit` | Exits and releases the model process |

The model stays loaded between commands. A forecast command always runs real inference: **this helper does not yet implement application forecast-result caching**. Its persistent cache stores model files, not an automatic substitute for fresh calculations.

For a presentation, start the session early, run one `forecast` to warm the execution path, then keep the session open. Mark any already-generated results as such; do not describe them as newly calculated. This command-line session does not expose an HTTP service.

## 6. Measure performance

### Step 6.1 — Run a repeatable benchmark

Close the interactive session first by typing `quit`. Then, in PowerShell:

```powershell
docker compose -f compose.chronos.yaml run --rm chronos benchmark --threads 4 --repeats 10
```

**Expected:** one warm-up, ten measured runs, then median and maximum prediction time. A `benchmark-....json` summary and individual forecast files appear in `artifacts/chronos`.

Model loading time is reported separately from prediction time. Process memory is a cumulative high-water mark; it is not the whole laptop's memory and does not isolate each individual prediction's peak.

### Step 6.2 — Compare CPU thread counts

Run the same benchmark sequentially with two and six threads:

```powershell
docker compose -f compose.chronos.yaml run --rm chronos benchmark --threads 2 --repeats 10
docker compose -f compose.chronos.yaml run --rm chronos benchmark --threads 6 --repeats 10
```

Choose the lowest-contention setting with acceptable latency, not automatically the largest number. Keep batch size, data, checkpoint, grouping and precision fixed during this comparison. Then use the chosen setting when starting a session, for example:

```powershell
docker compose -f compose.chronos.yaml run --rm --name pantrypulse-chronos-session chronos session --threads 4
```

### Step 6.3 — Watch resource usage

While that session is running, open a **second PowerShell terminal**:

```powershell
docker stats pantrypulse-chronos-session
```

Press Ctrl+C in this monitoring terminal to stop monitoring; the model session continues. Also check Windows Task Manager for available RAM and paging pressure.

**Initial target:** warm prediction preferably under ten seconds for this exercise, without sustained paging or an unresponsive desktop. That is a target to evaluate, not a promised or previously measured result. Rehearse the integrated application separately once implemented.

## 7. Close down safely

### Normal shutdown

1. Finish the current forecast.
2. Type `quit` at `chronos>`.
3. Wait for `Session finished` and the PowerShell prompt to return.

The process exits, model memory is released, and `--rm` removes the stopped session container. The disk cache and saved results remain for next time. WSL may retain filesystem cache afterward; that is different from a still-running model process.

Confirm the session has ended:

```powershell
docker ps --filter name=pantrypulse-chronos-session
```

**Expected:** no running session row. You do not need to delete Docker volumes or prune images.

### Interrupted or stuck session

Ctrl+C in the model session interrupts the process. A cancelled run may have no completed result. If it does not exit, use another PowerShell terminal:

```powershell
docker stop --time 10 pantrypulse-chronos-session
```

This targets only the named model-session container. Do not stop unrelated database/API containers to end a model exercise. Stop one-off benchmark containers by their actual name from `docker ps` if needed.

### What to keep

- Keep `pantrypulse-chronos-model-cache`: it avoids another model download.
- Keep selected CSV/JSON results and the checkpoint SHA for evidence.
- Do **not** run `docker compose down -v`, volume deletion, or broad Docker cleanup as routine shutdown.
- Quit Docker Desktop only when other projects no longer need it. Avoid `wsl --shutdown` while other WSL/Docker work is running.

## 8. Optimizations and considerations

| Recommendation | Why / limitation |
|---|---|
| Keep one model session | Avoids duplicate model copies; never start several sessions to make the demo appear faster |
| Start at four CPU threads | Leaves capacity for the frontend, API, Windows and browser; compare timings before choosing |
| Download once and keep the volume | Removes network downloads from the presentation path |
| Keep full selected history and seven-day horizon | Preserves the task before considering quality-changing optimizations |
| Keep float32 initially | Avoids unverified CPU precision/quantization trade-offs |
| Reduce batch size only if memory requires it | Try `--batch-size 8` or `4`; compare speed and outputs, with grouping held fixed |
| No fine-tuning | The demo needs pretrained inference, not training |
| Build everything before presenting | Compilation/builds compete with inference for CPU and memory |
| Use the full checkpoint first | Evaluate Chronos-2 Small separately only if measured full-model results miss targets |
| Keep laptop on AC power | Reduces power-saving and sleep interruptions; observe cooling during repeated runs |

The runner fixes context length at 128, retaining its complete 90-day input. This is an exercise setting, not permission to truncate longer real histories without evaluation. It fixes cross-learning off; production grouping must be chosen and validated explicitly. Lower batch size is not guaranteed to improve speed.

Later, the application should reuse an immutable forecast when only inventory, routes or fairness weights change, and recompute allocation live. Changed historical data/covariates/model settings need a new forecast. See the [local compute evaluation](docs/pantrypulse/LOCAL-COMPUTE-EVALUATION.md) for cache correctness, timeouts and quality gates.

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| `docker` is not recognized | Install Docker Desktop, then reopen PowerShell |
| Docker Linux pipe/engine connection error | Start Docker Desktop and select Linux containers; wait for readiness |
| Build/download looks slow | First-time locked ML dependencies are large; check connectivity and disk space rather than repeatedly restarting |
| Build ends with a failed download | Read the error and retry the build; do not replace lockfile versions blindly |
| `No prepared model` or offline cache error | Run `prepare` successfully while online, with the same Compose project/volume |
| Model repository requires authentication | Use the optional container login below; do not place a token in command arguments or this guide |
| Container exits with code 137 | Often memory exhaustion; inspect Docker status/memory, close unused workloads, reduce batch size, then reassess the limit |
| Named session already exists | Finish the previous session or inspect/stop that exact container before starting another |
| `forecast` is not recognized in PowerShell | Start `session` first; type it at the `chronos>` prompt |
| No website or API starts | Expected: this runner is a command-line model tool; application integration is separate |
| Output dates look old | The simulated cutoff is intentionally fixed for reproducibility |
| UI claims Chronos while runner is not connected | Integration is incomplete; do not treat these standalone results as a live UI response |

Do not disable Windows Application Control or grant broad system permissions to fix native library errors. Use the documented container path.

If the public download requires authentication for your account/rate limits, run this **only when needed**:

```powershell
docker compose -f compose.chronos.yaml run --rm --entrypoint hf chronos auth login
```

Enter the token interactively. The Hugging Face login is retained inside the private cache volume; do not share/export that volume as a public artifact. Then retry `prepare`. A hosted paid inference endpoint is not required.

## 10. Connect this to PantryPulse

The model runner establishes local model execution, not the research contribution. After the forecasting service and research-validation gates are completed, the application must:

1. Convert validated demand and donation snapshots into the model's supported format, preserving missing data and cutoff rules.
2. Reuse a single controlled model process and persist actual checkpoint/configuration/provenance with forecasts.
3. Apply a tested timeout that actually contains/terminates failed inference; report fallback or failure truthfully.
4. Run classical and EGP-PI-inspired allocation against **the same forecast and operational inputs**, with the required inventory, FEFO and capacity constraints.
5. Display the actual results, uncertainty labels and deprivation/fulfillment trade-offs.
6. Rehearse the full browser workflow and measure it separately from this synthetic model exercise.

Do not run this standalone session alongside a future integrated model process: that would load two copies. Use [personal-computer demo setup](docs/setup/LOCAL-DEMO.md) for the API/frontend/database steps, keeping their pending integration status in mind. The standalone model exercise itself needs no `.env` or Neon connection.

## 11. Presentation-day checklist

### Before leaving

- [ ] Image built and checkpoint downloaded/pinned.
- [ ] A real `smoke` run completed and output files inspected.
- [ ] The chosen thread/batch settings benchmarked on this laptop.
- [ ] Complete application integration tested separately, or the standalone scope clearly stated.
- [ ] Saved evidence/backup recording available and honestly labeled.

### Before presenting

- [ ] Laptop plugged in, adequate free RAM, no unnecessary builds or model sessions.
- [ ] Docker ready; start the model session and warm it with one real forecast.
- [ ] Model, data, timings and cache status described accurately.
- [ ] Internet verified if the full app uses Neon or a public tunnel.

### After presenting

- [ ] Type `quit`; verify the model session has ended.
- [ ] Stop any separately started frontend/API/tunnel processes when no longer needed.
- [ ] Keep the model cache and chosen evidence; avoid destructive cleanup.

Official references: [Chronos-2](https://huggingface.co/amazon/chronos-2), [pinned pipeline interface](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/src/chronos/chronos2/pipeline.py), [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/).
