# Fly.io compute configuration — prepared October 25, 2026

The user resumed local compute setup and requested Fly hosting configuration. The checked-in `apps/api/fly.toml` and `Dockerfile.compute` now define separate API and worker process groups. No app, paid Machine, volume, secret or deployment has been created. [V5](../pantrypulse/SPEC-V5.md#154-pauses-and-release-controls) and [local compute setup](LOCAL-COMPUTE.md) define the current authorization and remaining product gates.

## Current configuration

| Process | Size | Service/storage |
|---|---|---|
| `api` | 1 shared vCPU, 1 GiB | HTTPS to port 8000; process-only health; kept warm |
| `worker` | 4 shared vCPUs, 8 GiB | No public service; persistent 10 GB `chronos_cache` volume at `/cache` |

Fly documents vCPU counts 1/2/4/8/16, so four is used within V5's six-CPU ceiling. The supervisor receives the same four-CPU runtime profile. Library thread counts are four; no GPU is provisioned. API memory is separate from the worker budget. Process groups run in separate Machines, and only `api` receives HTTP traffic. The worker has no HTTP service and is not governed by request-driven autostop. See [configuration](https://docs.fly.io/reference/configuration) and [process groups](https://docs.fly.io/launch/processes).

The shared image installs the existing frozen forecast extra. A final build stage excludes dependency-download caches to stay within Fly's 8 GB image/rootfs envelope; verify actual image size before deployment. It has no model-specific ENTRYPOINT, so Fly commands can start the API or supervisor directly. It uses the empty **production** handler registry. There is no automatic migration, seed, download, benchmark or test-job execution during deployment. The persistent volume holds weights/pin/output files; authoritative application results and queue state belong in PostgreSQL. [Volume behavior](https://docs.fly.io/volumes/overview), [image size limit](https://docs.fly.io/getting-started/troubleshooting).

`SIGTERM` requests drain and Fly's maximum 300-second shutdown window is configured. Shutdown remains best-effort: a last-moment 300-second job plus cleanup may exceed the platform window. Plan deployments only after draining/confirming an idle worker; interrupted work requires explicit recovery/manual retry. Do not use a deployment to interrupt current work.

## Installed local CLI

The official Windows CLI v0.4.122 is installed at ignored `artifacts/tools/flyctl/flyctl.exe`. Its archive SHA-256 was verified against the official GitHub release asset digest:

```text
e96e1568f6f22f6f5248538918dae7a542d319fc36ba6d8e362e16ca5714549b
```

From the repository root, the pass-through wrapper is:

```powershell
./scripts/fly.ps1 version
./scripts/fly.ps1 auth login
./scripts/fly.ps1 auth whoami
```

Global PATH and Windows/WSL settings were not changed. Login is interactive and remains outstanding. Even `config validate` and `config show --local` in this CLI require an access token; no platform-validation pass is claimed without that login. TOML parsing and the process commands can be checked offline separately. [Official release](https://github.com/superfly/flyctl/releases/tag/v0.4.122), [CLI installation](https://docs.fly.io/flyctl/install).

## When hosting is explicitly approved

1. Sign in, select the intended organization and an exact app name. Reuse the intended existing app, or explicitly create it with `fly apps create YOUR_APP --org YOUR_ORG`. Creating resources and deploying incur provider charges and were not performed by this setup.
2. Choose the region beside the dedicated Neon demo database. `iad` is an editable East-US candidate. Use a **different database/lane from any running local worker**: cross-host takeover is not qualified. Keep the current research, auth/proxy and domain-integration gates visible.
3. Put `DATABASE_URL` privately in ignored `apps/api/.env.fly`. Use the actual runtime connection, retaining its TLS settings. Use a separately controlled direct connection for migrations. Verify ignore rules and import secrets via stdin, never as shell-history arguments. No secrets belong in TOML or `NEXT_PUBLIC_*` values.

```powershell
git check-ignore apps/api/.env.fly
Get-Content -LiteralPath apps/api/.env.fly | ./scripts/fly.ps1 secrets import --stage --app YOUR_APP --config apps/api/fly.toml
./scripts/fly.ps1 config validate --strict --app YOUR_APP --config apps/api/fly.toml
```

4. Review the existing jobs-only migration, confirm the isolated target, and apply it once from a controlled migration environment before starting the worker. Do not add an unconditional `release_command` against an unverified database. The current schema contains jobs/attempts/control/audit only; domain data and fixture publication are not implemented.
5. Run the deployment **with `apps/api` as the build context**. The root-relative configuration path alone does not change Docker's build context:

```powershell
Push-Location apps/api
../../scripts/fly.ps1 deploy --remote-only --ha=false --app YOUR_APP --config fly.toml
../../scripts/fly.ps1 machine list --app YOUR_APP
../../scripts/fly.ps1 checks list --app YOUR_APP
Pop-Location
```

`--ha=false` avoids an automatic spare; it does not remove existing Machines. Confirm exactly **one worker**, one API Machine, the intended sizes and a single worker volume. Do not scale out the queue or blindly scale down pre-existing work. A volume is tied to one host/Machine; recovery after replacement remains a separately qualified operator workflow.

6. Select the **worker** Machine explicitly when preparing the model or inspecting its cache. Inside that Machine, run `python scripts/chronos_local.py prepare`, then a bounded offline smoke while its lane is idle. The API Machine does not mount the cache. Keep test handlers private. A heartbeat or HTTP health response never proves Chronos readiness.
7. Verify the actual HTTPS health URL, runtime solver/database connectivity, worker heartbeats/effective resources, persistent checkpoint SHA, real bounded inference and unchanged saved data. Complete presenter authentication and the same-origin Next.js proxy before exposing mutation/job routes. No public model endpoint has been implemented by these files.

## Historical API-only guide

The guide below is retained as history. Its `fly launch` generation and 2-CPU/2-GB snippet predate the checked-in compute configuration; **do not replace the current files with that example**.

The selected presentation setup runs the backend on the laptop. Follow [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md) or [LOCAL-DEMO.md](LOCAL-DEMO.md) for that path. Fly.io is not required for the current demo.

The previously documented Fly workflow is retained below if hosted compute is needed later. It has not been executed against an account. Complete [GitHub](GITHUB.md) and [Neon](NEON.md) setup first.

### Install flyctl and sign in

Create/sign in to a [Fly.io account](https://fly.io), select the intended organization, and complete its current billing/access requirements. In PowerShell, install the official CLI:

```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

Open a new terminal if needed for PATH, then run:

```powershell
fly version
fly auth login
```

Record the CLI version used. Installer source: [Install flyctl](https://fly.io/docs/flyctl/install/). If the app already exists, reuse its configuration and confirm the target instead of launching a duplicate.

### Create the application without deploying

Starting at the outer repository root:

```powershell
Set-Location apps/api
fly launch --no-deploy
```

Choose a globally available app name and a region near Neon. Skip database, Redis and other optional add-ons. Reuse the existing `Dockerfile` and `.dockerignore`; inspect the generated diff before accepting replacements. This creates hosted app configuration even though it postpones deployment.

Keep the generated configuration at `apps/api/fly.toml`. All remaining Fly commands in this section run from `apps/api`. Its contents are the Docker build context required by the existing relative `COPY` statements. See [Dockerfile deployment](https://fly.io/docs/languages-and-frameworks/dockerfile/) and [monorepo paths](https://fly.io/docs/launch/monorepo/).

### Configure fly.toml

Merge the following settings into the generated file. Replace the app placeholder and use the actual chosen region; `iad` is an illustrative East US choice, not a verified deployment target. Do not duplicate generated service sections.

```toml
app = "REPLACE_WITH_YOUR_UNIQUE_API_APP"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1

[[http_service.checks]]
  grace_period = "20s"
  interval = "30s"
  method = "GET"
  timeout = "5s"
  path = "/api/v1/health"

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory = "2gb"
```

Port 8000 matches the existing Docker command, which binds to `0.0.0.0`. No platform `PORT` override is needed here. Two shared CPUs/2 GB is an initial benchmark candidate for the API/solver scaffold, not a measured Chronos capacity requirement. Update this file when resizing so the next deployment retains the intended resources.

One machine stays warm in the primary region under this policy. The minimum is not a maximum or a guarantee against restarts; inspect the actual machine count. For later cost-saving experiments, setting the minimum to zero permits scale-to-zero and introduces startup delay. Configuration references: [fly.toml](https://fly.io/docs/reference/configuration/) and [autostop/autostart](https://fly.io/docs/launch/autostop-autostart/).

### Store the database secret

Create `apps/api/.env.fly` in your local editor and put only the real pooled `DATABASE_URL=...` line there. The repository ignores `.env.*`, and the API Docker context excludes them. Verify the ignore rule without printing the file:

```powershell
git check-ignore .env.fly
```

If that command does not identify the file as ignored, fix the ignore rule before proceeding. Import it through stdin so credentials are not literal shell-history arguments:

```powershell
Get-Content -LiteralPath .env.fly | fly secrets import --stage
fly secrets list
```

Keep the local plaintext file private or remove it after import. Do not store secrets in `fly.toml`, build arguments, screenshots, or Vercel browser variables. The staged secret takes effect on deployment. See [Fly secrets](https://fly.io/docs/apps/secrets/) and [secrets import](https://fly.io/docs/flyctl/secrets-import/).

The direct migration connection should remain in the controlled migration environment until that workflow exists. No other secret is required for the scaffold.

### Deploy and verify

Inspect the local source/configuration and validate the file, then deploy:

```powershell
fly config validate
fly deploy --remote-only --ha=false
fly status
fly machine list
fly checks list
```

`--ha=false` avoids automatically adding a spare machine on this deployment. Verify that the app has the intended **one** API machine; this flag does not remove pre-existing machines. Review and explicitly scale an existing app if necessary. Remote building uses Fly's builder; Docker Desktop remains useful for local reproduction. See [deploy options](https://fly.io/docs/flyctl/deploy/).

Record the actual HTTPS hostname from deployment output/dashboard; do not use the placeholder below unchanged:

```powershell
Invoke-RestMethod 'https://YOUR-API-APP.fly.dev/api/v1/health'
```

Expected response: `{"status":"ok","scope":"process"}`. Open `/docs` to inspect currently implemented routes. Then enter the deployed container:

```powershell
fly ssh console
```

Inside that Linux shell:

```sh
cd /app
uv run --frozen python scripts/check_runtime.py --database
uv run --frozen pytest
exit
```

These independently check a trivial CP-SAT solve, the configured database connection and existing scaffold tests. They do not validate allocation correctness. A process-health response alone is insufficient. Inspect logs with `fly logs` if a check fails; avoid logging connection strings. [SSH console reference](https://fly.io/docs/flyctl/ssh-console/).

The image currently includes test tooling and is a development scaffold. It does not install Chronos, apply migrations or seed domain data. No Fly volume is needed for the initial API/solver scaffold; durable application data belongs in Neon. Evaluate a deliberate model-cache/storage strategy only if enabling live Chronos inference.
