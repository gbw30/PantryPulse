# Explicit public benchmark acquisition

This tool prepares a retail observed-sales proxy experiment, not a live pantry
database. Use Python 3.12+ with `pyarrow==22.0.0` installed in a separate tooling
environment (`requirements.txt` here); ordinary API/tests do not need Arrow.
No dependency or model is loaded when importing the benchmark envelope.

```sh
python apps/api/scripts/forecasting_data.py fetch \
  --cache-dir /tmp/pantrypulse-frn50k/c374e85975c82816c495acfa904cc55ab14a47d3
python apps/api/scripts/forecasting_data.py prepare \
  --cache-dir /tmp/pantrypulse-frn50k/c374e85975c82816c495acfa904cc55ab14a47d3 \
  --output-dir /tmp/pantrypulse-forecast-pilot --cohort-size 100
```

`fetch` explicitly downloads the two official upstream files at the pinned
revision in `data/benchmarks/forecasting/freshretailnet50k-source-v1.json`; size
and SHA-256 must match. Existing wrong caches and changed frozen output files
fail rather than being silently replaced. Bulk cache/output stay outside Git.

`prepare` reads training values and only IDs/dates/schema from the final eval
file. It verifies 90 consecutive training days, seven subsequent final days and
matching source series. A seed-20261025 stable ID hash chooses the pilot without
consulting outcomes. Output is `pilot-training.json` plus `manifest.json`, with
four seven-day validation folds ending at training days 62/69/76/83. The manifest
records source/transform/cohort/data hashes and final dates, never final values.

From an API Python environment, `load_dataset(manifest_path)` in
`app.services.forecasting.benchmark_data` validates and loads the training-only
dataset. `series.at_origin(cutoff)` exposes only origin-available observations;
its hash is invariant to changes in later values. Data and masks stay separate
from production requested-demand, donation and inventory contracts.

The source-specific `scripts.forecasting_data.load_final_holdout(...)` requires
`allow_final_holdout=True` before opening any raw file. Only the serialized FC-07
qualification step should call it after recording the frozen settings and
validation report. There is deliberately no casual final-evaluation CLI command.

Attribution: Dingdong-Inc; Wang et al. (2025),
[FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K),
CC BY 4.0. Values retain upstream global normalization and stockout censoring;
neither latent need nor an inverse conversion to pantry units is established.
