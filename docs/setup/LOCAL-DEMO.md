# Laptop demo: local compute with isolated data

Updated October 25, 2026. The selected compute host remains the laptop; Fly is optional. Source now includes the connected baseline forecast/OR workflow at `/optimization`, presenter/CSRF controls, same-origin proxy and durable jobs. See [current status](../pantrypulse/CURRENT-STATUS.md). Existing running images and the old Vercel preview are separate from this source state.

## Preserve existing work

Inspect Docker/services and loopback ports before choosing an environment. Do not stop a running API/worker, overwrite its private environment, migrate its database or clear a queue merely to follow this guide. A new image needs a later controlled adoption after active work finishes; the opt-in helper uses `--no-recreate`.

Use [LOCAL-COMPUTE.md](LOCAL-COMPUTE.md) for the bounded local API/worker image, resource checks and standalone Chronos tools. Use `compose.forecast.yaml` with explicitly selected private `apps/api/.env` for the laptop-to-Neon path. `compose.demo.yaml` is an API/database probe and does not start a worker.

## Prepare a new isolated connected demo

1. Choose the dedicated local or Neon database and direct migration connection. Preserve provider TLS settings. Do not reset an existing schema.
2. Run the deliberate `load_optimization_demo.py --schema ppor_demo_YOUR_NAME --output PRIVATE_PATH` procedure in [CONNECTED-INTEGRATION.md](../optimization/CONNECTED-INTEGRATION.md). It creates a new migrated schema and fictional history, stock and assumptions; it never fabricates forecast/comparison results.
3. Configure the exact schema and fictional organization in private API settings. Set presenter username/password hash, allowed origins and a matching trusted proxy token. See [forecast/auth flow](../pantrypulse/FORECAST-API-FLOW.md).
4. Configure `apps/web/.env.local` using the tracked example: server-only `PANTRYPULSE_API_ORIGIN` and `PP_TRUSTED_PROXY_TOKEN`. No secret or backend URL is needed in `NEXT_PUBLIC_API_BASE_URL`.
5. Start only that selected API/worker environment. Its production registry contains `forecast.v1` and `or-comparison.v2`; Linux capability version 2 is required. Configure/review ports so existing work stays running.
6. Open `/optimization`, log in, generate a real baseline forecast, freeze an explicit-mode scenario and submit a paired comparison. Review native statuses, independent verification, partial outcomes and immutable provenance. Editing assumptions requires a new saved version/scenario.

Windows native library restrictions on this computer are handled by Linux containers, not by weakening security policy. Demo-loading scripts read repository fixtures; when running them in Docker, mount the complete checkout and run from `/repo/apps/api`, as in the compute runbook.

## Resource and shutdown policy

The local worker ceiling is six CPU equivalents/eight GiB, separate from API/database needs. Model tools run only when the queue/operator checks allow, and never concurrently with active domain work. Source defaults are 120 seconds native search, 150 seconds per method and 330 seconds per comparison; maxima are 300/330/690. Queue expiry is 1,800 seconds, with one active and two waiting operations.

SIGTERM drains without claiming another job. Supervisor drain allows up to 720 seconds; local container grace is 725 seconds. Never use broad process kills, delete data volumes or clear ownership rows to force availability. Follow [worker recovery](WORKER-QUEUE.md).

## Chronos and public access

The pinned full Chronos-2 model has passed a separate real CPU smoke and ten warm synthetic runs; see the dated [compute evidence](LOCAL-COMPUTE.md#verification-record). It remains outside the application provider registry. Raw quantiles are not calibrated intervals, synthetic timings are not predictive-accuracy evidence, and donation predictions are not physical stock.

The existing `/design-lab` Vercel preview needs no API/tunnel. A separately authorized connected release can use the implemented proxy and [Cloudflare tunnel](CLOUDFLARE.md), after actual target/origin/cookie checks. Do not expose PostgreSQL. [Fly](FLY.md) remains configuration-only and requires login/platform validation/deployment.

## Offline alternative: existing local PostgreSQL

Use the local database and a newly seeded isolated demo schema while venue network is unavailable. Preparing a local schema does not copy Neon automatically. Keep dependencies and weights cached before the event; an offline model exercise does not make every application operation model-backed.

Verify process health, database/schema, fresh worker capability, authenticated browser actions, real forecast publication and sequential comparison on that exact runtime. Preserve a release manifest, backup recording and rollback plan. See [deployment/recovery](../pantrypulse/DEPLOYMENT.md). Supplier planning, broad import UI, visitor access, production reset and real purchasing/dispatch remain outside this demo.
