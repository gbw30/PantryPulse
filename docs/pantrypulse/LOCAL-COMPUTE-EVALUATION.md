# Local demo compute evaluation

Date: October 24, 2026. Recommendation only: no model installation, inference benchmark, container restart, or application implementation was performed for this evaluation. V4 and the research-validation gate remain authoritative.

Follow-up: [CHRONOS-LOCAL.md](../../CHRONOS-LOCAL.md) now documents a separate optional model runner for preparation, real synthetic-data inference, timing and shutdown. Its offline safeguards are checked; actual image/model execution and the application integration remain to be verified.

## Decision

Test the **full `amazon/chronos-2` checkpoint on CPU first**, with one resident model instance, fixed input snapshots, cached forecast results, and serialized expensive work. Preserve full demo history and the required seven-day horizon. Demonstrate at least one genuine live forecast refresh, then reuse its immutable output for live classical versus EGP-PI-inspired allocation.

This keeps Chronos functional while avoiding repeated work. A smaller checkpoint is a measured fallback decision, not the first resource optimization. Do not guarantee forecast accuracy or response time without local measurements.

## Evidence and limits

- The initial evaluation used a Windows laptop with a Core Ultra 9 285H and approximately 32 GiB RAM. This is reference hardware, not a minimum requirement or a capacity benchmark. Measure available memory on the actual presentation host.
- Native project metadata shows OR-Tools 9.15.6755; Chronos and PyTorch are not installed there. The lock contains chronos-forecasting 2.3.2 as an optional extra.
- Docker's Linux engine was unavailable during the initial evaluation, so no usable container resource measurements were collected.
- The API exposes process health. Backend primitives for transfer modes, routes, rounding, fixed-point arithmetic, solver outcomes and history alignment are implemented, while complete domain solvers, the forecasting adapter, persistence and UI integration remain pending. No completed-app memory or latency measurements exist.

The standard model has about 120 million parameters. At four bytes per float32 parameter, nominal weight storage is about **0.45 GiB**, before runtime libraries, intermediate tensors, data and other allocations. The earlier 12–16 GB suggestion was a conservative whole-demo headroom budget, not a published minimum for Chronos itself. Sources: [standard checkpoint](https://huggingface.co/amazon/chronos-2), [local API manifest](../../apps/api/pyproject.toml), [Dockerfile](../../apps/api/Dockerfile).

## Optimizations in priority order

| Priority | Recommendation | Expected benefit | Forecast-quality implications |
|---|---|---|---|
| 1 | Cache completed forecasts by exact input/model/configuration identity | Removes duplicate inference entirely | Reuses the same completed result; correct invalidation is essential |
| 2 | Replan inventory/fairness changes against the existing forecast run | Avoids forecasting whenever only allocation inputs change | No forecast approximation; identical forecasts improve method-comparison validity |
| 3 | One API worker and one controlled model process | Prevents multiple resident model copies and overlapping requests | No intended reduction in model capability |
| 4 | Download a pinned checkpoint once, retain its cache, and prewarm deliberately before presenting | Removes network download and cold-load work from ordinary interactions | Same checkpoint; record the warm/cache state |
| 5 | Run the built Next.js frontend, not the development compiler | Avoids development compilation/reload overhead | Production rendering must still pass browser tests |
| 6 | Benchmark PyTorch with 2, 4 and 6 CPU threads; start at 4 | Limits contention and can improve small-workload latency | Compare outputs within a documented numerical tolerance |
| 7 | Forecast only the required seven days, keeping all selected historical observations | Avoids unused future-output work | Preserves the intended task; do not remove necessary history |
| 8 | Tune batching while holding series grouping/cross-learning policy fixed | Can reduce peak inference memory | Changing groups can change forecasts; verify rather than assuming equivalence |

Prewarming is an explicit presenter preparation step, not a model download on API startup, a dashboard GET, or a fabricated successful forecast. Never silently treat a cached result as newly computed.

Only one expensive job should run at a time initially: forecast, classical solve, then research-inspired solve. HTTP reads/polling must remain responsive. Run model work outside the API's event loop, in a controlled process that can actually be terminated on timeout; a cancelled HTTP request or abandoned future does not necessarily stop inference. On process death, record job failure and restart/reload deliberately. This is a proposed implementation pattern, not another service or queue product to provision.

The pinned pipeline already uses a no-gradient prediction path. Do not claim a new speedup simply for wrapping it in another no-gradient context. Use inference/evaluation mode appropriately in the adapter and verify behavior. Thread counts must be configured before computation in the model process. Sources: [Chronos 2.3.2 pipeline](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/src/chronos/chronos2/pipeline.py), [PyTorch thread control](https://docs.pytorch.org/docs/2.14/generated/torch.set_num_threads.html).

## Proposed first benchmark profile

These values are experiment settings and operating targets, not implemented environment variables or measured requirements.

| Area | Starting profile |
|---|---|
| Runtime | Existing Linux Docker path; retain native Windows policy protections |
| Checkpoint | Full `amazon/chronos-2`, pinned to an actual full revision SHA |
| Precision/device | Float32 on CPU; no fine-tuning |
| Docker/WSL envelope | Start with access to 6 logical CPUs and up to 8 GiB memory; verify effective limits and actual host headroom |
| API processes | One API worker, with no development reload during the final demo |
| Model execution | One supervised model process, one model instance, one inference job at a time |
| PyTorch threads | Start with 4 intra-op threads and 1 inter-op thread; compare 2/4/6 intra-op in separate runs |
| Solver | One CP-SAT worker per method, same settings/time limits, sequential comparison |
| Forecast inputs | Six beneficiaries × two categories: 12 demand series, plus the separately specified donation series; do not drop donation functionality to fit a target |
| History | All valid history selected for the demo, typically the planned 90–120 daily points; preserve missing-value and cutoff rules |
| Forecast horizon | Seven daily points, with the required uncertainty outputs |
| Batching | Measure a complete compatible demand group first, then smaller groups only as a controlled experiment; include covariates when counting effective series |
| Cross-learning | Explicit, fixed policy in every run and cache key; evaluate changes independently |
| Storage | Forecast outputs/provenance in PostgreSQL; downloaded model artifacts in a persistent local cache outside source control |

Free host memory before starting. Aim for roughly 10–12 GiB available before a Chronos-enabled rehearsal so an 8 GiB VM envelope does not force Windows into heavy paging. This is a practical cushion, not a hard model requirement. An 8 GiB cap does not reserve or prove 8 GiB is currently available. Do not change global WSL settings without considering other workloads. Docker's WSL backend allocates memory dynamically; verify effective limits rather than assuming a setting took effect. [Docker WSL documentation](https://docs.docker.com/desktop/features/wsl/).

No GPU/NPU acceleration is assumed from the laptop's product name. Do not add AutoGluon merely to call Chronos; the declared direct chronos-forecasting adapter is sufficient. CPU-specific PyTorch packaging may reduce install/image size, but it requires deliberate uv dependency/index configuration and a reviewed lock update; do not install a conflicting second stack manually.

## Cache correctness and scenarios

A forecast cache key should include organization and series identity, demand versus donation target, immutable observation and covariate content hashes, cutoff/as-of dates, horizon, model checkpoint/revision, package/preprocessing versions, precision, grouping/cross-learning/batch policy and relevant inference configuration. Record actual provider, timings and cache status with the output.

| Change in the demonstration | Correct action |
|---|---|
| Refresh page or revisit a chart | Read the saved forecast/result; no model inference |
| Change inventory, route capacity or fairness weights | Recompute allocation from the selected forecast and operational snapshot |
| Apply a disclosed demand scenario multiplier | Apply it to an immutable scenario; do not imply Chronos generated the multiplier |
| Import changed observations, change cutoff, covariates, checkpoint or forecast settings | Generate a new forecast run; do not reuse the old cache entry |
| Switch classical/research comparison views | Display paired saved outputs; do not forecast separately for each method |

Do not recompute only one series without considering its full model input group. With cross-learning, changing a series can require invalidating the group's forecasts. Demand and donation remain distinct targets; forecasted donations must not become confirmed inventory.

## Changes to defer unless measurements justify them

- **Shorter history:** may remove seasonal information. Retain all selected demo history first. Reducing a maximum context setting provides no assured benefit if the actual input is already short.
- **Chronos-2 Small:** official 28M-parameter alternative, with nominal float32 weight storage about 0.10 GiB. This is roughly 77% fewer parameters, not a promise of 77% less process memory or equal accuracy. Pin and evaluate it before replacing the standard checkpoint. [Small checkpoint](https://huggingface.co/autogluon/chronos-2-small).
- **BF16/FP16 or quantization:** hardware/runtime-specific compatibility, accuracy and speed must be measured. Keep float32 as the reference; a smaller dtype is not automatically faster on CPU.
- **GPU/NPU integration, ONNX conversion or compilation:** additional setup/startup risk is not justified until the direct CPU path misses its measured target.
- **Fewer quantiles:** smaller responses may help presentation, but do not assume they remove most neural inference work. Preserve the quantiles needed for the project's uncertainty views.
- **Parallel solvers/model runs:** can improve throughput while worsening peak memory and interactive latency. The demo needs reliable single-user response first.

## Acceptance experiment

Before making any performance claim, test an implemented standalone adapter and then the integrated workflow on the actual demo laptop. Do not benchmark a health endpoint as evidence about forecasting or allocation.

1. Freeze the exact six-beneficiary dataset, series grouping, forecast cutoff/horizon, checkpoint SHA and package versions. Include donation series and required covariates. Use no future observations.
2. Measure imports/download separately from cold model load, first prediction and warm predictions. Run at least ten warm forecasts per chosen configuration; report median, maximum, and memory high-water mark, not a misleading precise percentile from a tiny sample.
3. Compare thread counts with the same inputs and grouping. Adjust batch size only as a separate experiment. Monitor host available RAM, VM memory, model-process RSS, swapping, CPU contention and API responsiveness.
4. Initial UX targets: saved/cached reads under 1 second; a warm complete forecast refresh preferably under 10 seconds; each seeded solver under the project's 5-second target. These are acceptance targets, not observed results. Use a separately bounded forecast timeout based on measured behavior.
5. Verify cache hits avoid model calls, changed forecast inputs invalidate cache, queued jobs do not duplicate, and failed/timed-out work terminates with truthful state. Retain the last valid result visibly marked while recalculation is pending.
6. Check identical-input forecast outputs within a declared tolerance after runtime-only changes. For a changed model/context/grouping/precision, use chronological holdouts, WAPE/MAE and bias per category, and quantile checks. Report raw quantiles without claiming calibration.
7. For considering a smaller checkpoint, an initial decision rule is no more than 5% relative degradation in primary holdout error versus full Chronos, with an agreed absolute tolerance when reference error is near zero. Also inspect per-institution errors, shortage dates and allocations: an average score must not hide a worse result for vulnerable beneficiaries. This is a proposed gate, not an established research standard or a guarantee.
8. Rehearse the full sequence at least five times with the same successful configuration. Ensure independently checked inventory conservation, FEFO/capacity constraints and honest solver status. Equation-level research validation must precede implementing the allocation engines.

## Demonstrating project value

Show one real live Chronos forecast run and its provenance. Use that same immutable run and operational dataset to calculate both allocation methods live. Change a fairness setting and show the allocation difference without rerunning an unchanged forecast. Then, if useful, import a prepared alternate historical snapshot and show a genuine forecast cache miss and refreshed results.

Display per-institution fulfillment, absolute/relative deprivation, constraints, and objective trade-offs. Preserve the six beneficiaries, both resource categories, both real solvers and required operational constraints. Do not invent a research-method result if that method fails, and do not present seasonal-naive or cached output as a newly executed Chronos prediction.

Chronos supports demand estimation; the central research demonstration remains whether the EGP-PI-inspired priorities change feasible allocation decisions on identical data. More attractive forecasts alone do not prove that contribution. If forecasting does not beat seasonal naive on the chosen holdout, disclose it and follow the project's provider-selection rule rather than claiming an accuracy gain.
