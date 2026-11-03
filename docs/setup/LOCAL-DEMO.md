# Laptop demo: choose and preserve the correct runtime

Updated October 25, 2026 for main `647f6a8`. The connected application has `/overview`, `/data`, `/recommendations`, `/scenarios` and `/methodology`. `/optimization` redirects to Scenario Lab. Shared presenter sign-in is in the sidebar. For exact machine-specific video paths, restart commands and recovery, use [LOCAL-LAUNCH-GUIDE.md](LOCAL-LAUNCH-GUIDE.md).

## Existing video demo

Resume the prepared `presenter_demo_20261025_135726` project using its saved `compose.yaml` and website launcher. At the recorded setup its web/API URLs were 3020/8021; read `project.json` rather than assuming ports. It contains three added VIDEO datasets and saved genuine computations. Its earlier copied API image is not automatically upgraded with current main, and its retired `/optimization` video-shortcut component is not an active route on current main.

Do not create a new demo or import CSVs merely to resume its database. Do not mix credentials/proxy settings from the older `133505` environment. Saved data can outlive its video labels or its planning date; historical results must remain labelled.

## Tracked local launcher

After installing dependencies, inspect Docker and selected ports. When the `pp-local-*` lane is idle:

```powershell
pwsh -File scripts/demo-local.ps1 -WebPort 3030 -ApiPort 8030 -DbPort 55434
```

Those ports are examples and must be free. The launcher uses its own network, PostgreSQL volume and API/worker, explicitly seeds once, generates private presenter credentials, enables saved visitor reads, and queues a baseline forecast unless `-NoForecast` is selected. `-NoWeb` omits website startup. `-Products 4` selects the supplied four-product fixture; default 2. Planner contracts accept at most eight products, not an eight-product launcher switch.

**Operational behavior:** the launcher rebuilds its image and removes/recreates its own API/worker every invocation. The database volume persists. `--restart unless-stopped` preserves container startup behavior. Do not rerun during active work. `-Reset` deletes this launcher's database volume and credentials and is only for an intentional disposable-demo reset, never port cleanup.

## Explicit compute/Neon alternative

Use `compose.yaml` + `compose.compute.yaml` for the bounded local compute image/worker and local PostgreSQL; use `compose.forecast.yaml` with selected private `apps/api/.env` for an isolated Neon schema. `compose.demo.yaml` is only an API/database probe and does not start a worker. The opt-in compute helper uses `--no-recreate`; it intentionally may preserve older running images. These procedures have different adoption semantics from `demo-local.ps1`.

The explicit loader `apps/api/scripts/load_optimization_demo.py` requires direct `DATABASE_URL_UNPOOLED`, a new `ppor_demo_*` schema, and an output path. `--spec` may select a checked-in fixture, including the four-product example. It migrates and loads fictional history/stock/assumptions; never fake forecast/solver output. API/worker must select that exact schema and organization. Current migration head: `ppvp_0007`.

For manual configuration set presenter username/hash/organization, Origin/CSRF/proxy settings, optional visitor organization, and matching Next server-only API origin/token. For local HTTP use loopback and `PP_COOKIE_SECURE=false`; hosted HTTPS requires secure cookies. Existing schemas are not migrated or reset by startup.

## Forecasts and model qualification

Baselines require no optional model packages. Chronos application jobs are integrated under `forecast.chronos.v1` but disabled by default and experimental. They need explicit pin/profile/cache and live matching worker capability; follow [CHRONOS-JOBS.md](../forecasting/CHRONOS-JOBS.md). Standalone model tools are separate. Invalid donation quantiles are rejected; an explicitly permitted whole-batch moving-average fallback can be planning-ready and is labelled as such. The [retail experiment](../forecasting/QUALIFICATION.md) does not establish pantry accuracy or calibration.

## Verification, shutdown and offline use

Verify process health, schema/catalog, presenter access, real forecast publication and a verified paired scenario. Optional visitors can read only the saved catalog/dashboard/shortage subset. Health alone does not qualify a worker/model or a release.

The shared lane allows one active and two waiting jobs. Default solver/method/comparison ceilings are 120/150/330 seconds; maxima 300/330/690. Forecast ceilings are 270/300. Wait for work to finish, stop only this website with Ctrl+C, and stop only the selected demo containers. Worker grace is 725 seconds. Preserve volumes and schema.

Cache dependencies/images and seed a local database before an offline event; using local PostgreSQL does not copy Neon. Record commit/image/schema/dataset/settings, confirm current date and save a backup recording. Five clean rehearsals, human visual acceptance and actual presentation-target checks remain release requirements. Supplier planning and real purchasing/reservation/dispatch remain separate.
