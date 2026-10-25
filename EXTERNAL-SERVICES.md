# External services and deployment paths

Updated October 25, 2026. [Current status](docs/pantrypulse/CURRENT-STATUS.md) and [SPEC-V5](docs/pantrypulse/SPEC-V5.md) distinguish source functionality, running images and deployment evidence. Local backend/Chronos preparation was explicitly resumed; supplier planning and public/paid deployment were not authorized by setup alone.

## Choose the environment

| Path | Runtime/configuration | Purpose |
|---|---|---|
| Fully local | `compose.yaml` plus opt-in `compose.compute.yaml`; private `apps/api/.env.compute` | Laptop API/worker and local PostgreSQL; persistent model cache |
| Laptop with Neon | `compose.forecast.yaml`; explicit private `apps/api/.env` | Existing baseline/OR worker and API using a deliberately selected isolated hosted schema |
| Process-only Neon probe | `compose.demo.yaml`; private `apps/api/.env.demo` | API/DB reachability; this file alone does not start a worker or establish a connected demo |
| Fly alternative | `apps/api/fly.toml`, `Dockerfile.compute`, private Fly secrets | Prepared API/worker hosting; no Fly resources or deployment were created by local setup |
| Vercel preview | Existing `codex/vercel-prototype-preview` project/branch | Historical synthetic `/design-lab` preview, independent of current main's connected workspace |

These paths can collide on loopback port 8000. Inspect existing tasks and ports; do not stop them or switch database targets automatically. Use an isolated environment/alternate ports for additional verification.

## What runs where

```text
Browser → Next.js /optimization and same-origin proxy
        → FastAPI presenter/CSRF validation
        → PostgreSQL saved inputs/jobs/results
        → one supervised forecast or sequential OR comparison
```

PostgreSQL stores durable state. It does not run Python/OR-Tools/Chronos; increasing Neon database compute does not increase the laptop worker's resources. No Redis, Kubernetes, object store or paid model endpoint is required by this design.

## Local setup

Follow [INSTALLATION.md](INSTALLATION.md), then [LOCAL-COMPUTE.md](docs/setup/LOCAL-COMPUTE.md). The opt-in API and worker share the locked compute image and use direct Python startup/health commands. The worker is capped at six CPU equivalents/eight GiB; the separate builder at two CPUs/three GiB. The helper preserves existing containers with `--no-recreate` and performs no automatic migration or seed.

Current source includes presenter access, baseline forecasts, immutable scenarios, durable comparisons and the connected UI. The application policies still offer baselines, while real Chronos is a separate offline model exercise. Installing weights does not register a live model handler.

## Hosted database and connected demo

1. Reuse the intended dedicated synthetic-demo Neon project/branch/database and runtime role; retain TLS parameters on the pooled runtime URL.
2. Keep a separately controlled direct `DATABASE_URL_UNPOOLED` for deliberate migrations/loading. The migration and loader scripts now support this variable explicitly; no startup migration occurs.
3. Follow [CONNECTED-INTEGRATION.md](docs/optimization/CONNECTED-INTEGRATION.md) to create a NEW `ppor_demo_*` schema with `load_optimization_demo.py`. It refuses schema reuse and creates no fake computed results.
4. Privately configure `PP_DATABASE_SCHEMA`, presenter username/password hash/organization, allowed browser origins, secure-cookie policy and `PP_TRUSTED_PROXY_TOKEN`. Configure the Next.js server's `PANTRYPULSE_API_ORIGIN` and matching proxy token from `apps/web/.env.example`.
5. Start only the selected API/worker environment after schema/configuration review. Old capability-version-1 supervisors cannot accept the new OR contract; replacing them is a controlled operation after active work finishes.

`compose.forecast.yaml` injects `apps/api/.env`; `compose.compute.yaml` injects optional `.env.compute` but deliberately fixes the runtime database to local development. A dotenv file in another location does not switch an environment. Never copy private credentials automatically between checkouts.

## Remote frontend and compute

The same-origin proxy is implemented. For a separately authorized hosted frontend, point its server-only API origin at the actual HTTPS API/tunnel, preserve trusted external Host/protocol, configure matching allowed origins/proxy secret and use secure cookies. A Vercel server cannot reach the laptop through its own `127.0.0.1`. Do not put backend credentials or the old direct API variable in browser-exposed environment values.

[Cloudflare](docs/setup/CLOUDFLARE.md) provides optional temporary API reachability; it publishes no PostgreSQL port. The old Vercel preview remains branch-scoped and is not updated by merging main. Verify a separately selected connected release against its real URL; process health or an ignored build is insufficient.

For Fly, follow [FLY.md](docs/setup/FLY.md). It configures separate API and worker Machines and a persistent model volume. Login, target selection, platform validation and deployment remain pending. Keep local and Fly workers on different queues; cross-host takeover is not qualified.

## Verification and release

Active [Linux CI](.github/workflows/pantrypulse-ci.yml) runs PostgreSQL/process-control tests, web lint/types/unit/contracts/build and the connected browser journey, rejecting skipped backend/browser evidence. Local commands are recorded in the [worker](docs/setup/WORKER-QUEUE.md) and [connected integration](docs/optimization/CONNECTED-INTEGRATION.md) guides. A current-source pass does not update an already-running container.

Forecast boundaries remain 270/300 seconds. Solver search defaults/maxima are 120/300 seconds, method walls 150/330, comparisons 330/690 and queue expiry 1,800. Local shutdown grace is 725 seconds. Fly's 300-second stop window requires an already-idle lane before deployment.

Record the exact commit/image, schema, dataset/input hashes, model revision, solver settings, URLs and rollback pair without secrets. Follow [deployment/recovery](docs/pantrypulse/DEPLOYMENT.md). Venue-network readiness, representative forecast accuracy, integrated Chronos, supplier planning, visitor access and real operational dispatch remain separate gates.
