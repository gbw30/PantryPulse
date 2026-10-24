# Optional Hugging Face / Chronos-2 setup

Purpose: obtain versioned Amazon Chronos-2 model artifacts if we validate live inference. This is optional. The research allocation engine and seasonal-naive forecast path must not depend on a hosted model API.

**For this Windows laptop, start with [CHRONOS-LOCAL.md](../../CHRONOS-LOCAL.md).** It provides the separate model-enabled Docker image and runnable preparation/session/benchmark commands. The native commands below remain a reference for compatible hosts; they are not the recommended path for the original machine's blocked native libraries.

No Hugging Face account, token, checkpoint download, inference endpoint, GPU service or model subscription has been created by this guide.

## Decide whether to enable it

1. Complete the core setup in [INSTALLATION.md](../../INSTALLATION.md).
2. Establish available RAM/disk and measure model download, load and inference time on the intended host.
3. Retain a labeled seasonal-naive fallback. Cached verified forecast results are another prepared-demo option.
4. Review the [amazon/chronos-2 model card](https://huggingface.co/amazon/chronos-2), including its license and supported interface.
5. Use the native environment only on hosts that allow its binary dependencies. The original Windows host has an Application Control restriction affecting pandas, so Linux/container inference should be validated separately.

## Install the declared optional dependencies

From the repository root:

```powershell
uv sync --frozen --project apps/api --python 3.12.13 --extra forecast
```

This uses the existing uv.lock; do not pip-install a parallel model stack. The extra includes chronos-forecasting and its ML dependencies. Default setup later removes unselected extras.

The default API Dockerfile explicitly excludes forecast. The command above does not modify that image. The optional Dockerfile.chronos and compose.chronos.yaml now supply a separate standalone model exercise using the existing lock. It is not the application's forecasting adapter; integration and acceptance tests remain pending.

## Account and access

Public model artifacts may be downloaded without authentication. If Hugging Face requires authentication for the intended artifact or account limits, sign in at https://huggingface.co and configure the backend download environment.

After installing the extra, an interactive native login can use:

```powershell
uv run --frozen --directory apps/api --extra forecast hf auth login
```

Enter any token interactively; do not place it in a command argument, Git, browser configuration or screenshots. A hosted backend can receive HF_TOKEN through its service secrets if needed. Review the [Hub CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli).

A paid Inference Endpoint is not part of this plan. Downloading model artifacts does not send our observation data to a hosted inference API.

## Pin and cache the model

Record a full model commit SHA from the model repository. A dependency lockfile does not pin model weights.

Illustrative download command, only after selecting the actual revision:

```powershell
uv run --frozen --directory apps/api --extra forecast hf download amazon/chronos-2 --revision FULL_MODEL_COMMIT_SHA
```

Replace the placeholder. Keep the cache in a persistent backend location with sufficient disk space, outside source control. The Hub supports revision-specific downloads; see [download/caching documentation](https://huggingface.co/docs/huggingface_hub/guides/download). Hosted restarts can otherwise trigger repeat downloads if storage is ephemeral.

## Verify before integration

- Verify dependency imports and CPU/GPU availability in the intended runtime.
- Load the pinned checkpoint with the supported Chronos API.
- Test a small dated series and confirm output dates, shape, finite nonnegative values and actual quantile provenance.
- Measure time/memory, contain timeouts, and test unavailable-model/fallback behavior.
- Preserve requested-demand versus donation target identity and prevent future-data leakage.
- Store checkpoint SHA, provider, cutoff, dataset hash and cache status with each forecast result.

These are application-adapter acceptance tasks; the repository has no integrated Chronos adapter or acceptance command for them yet. The standalone helper exercises real inference separately and does not complete those integration requirements. Model download success alone is not forecast validation. The qualifying PantryPulse contribution remains the EGP-PI-inspired allocation model, not the availability of this supporting checkpoint.
