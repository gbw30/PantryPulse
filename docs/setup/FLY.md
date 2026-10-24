# Fly.io setup — optional hosted alternative

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
