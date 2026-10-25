# Fly.io compute configuration — prepared October 25, 2026

The user resumed local compute setup and requested Fly hosting configuration. The checked-in `apps/api/fly.toml` and `Dockerfile.compute` now define separate API and worker process groups. No app, paid Machine, volume, secret or deployment has been created. [V5](../pantrypulse/SPEC-V5.md#154-pauses-and-release-controls) and [local compute setup](LOCAL-COMPUTE.md) define the current authorization and remaining product gates.

## Current configuration

| Process | Size | Service/storage |
|---|---|---|
| `api` | 1 shared vCPU, 1 GiB | HTTPS to port 8000; process-only health; kept warm |
| `worker` | 4 shared vCPUs, 8 GiB | No public service; persistent 10 GB `chronos_cache` volume at `/cache` |

Fly documents vCPU counts 1/2/4/8/16, so four is used within V5's six-CPU ceiling. The supervisor receives the same four-CPU runtime profile. Library thread counts are four; no GPU is provisioned. API memory is separate from the worker budget. Process groups run in separate Machines, and only `api` receives HTTP traffic. The worker has no HTTP service and is not governed by request-driven autostop. See [configuration](https://docs.fly.io/reference/configuration) and [process groups](https://docs.fly.io/launch/processes).

The shared image installs the existing frozen forecast extra. A final build stage excludes dependency-download caches to stay within Fly's 8 GB image/rootfs envelope; verify actual uncompressed layer size before deployment. It has no model-specific ENTRYPOINT, so Fly commands can start the API or supervisor directly. Main's **production** registry runs `forecast.v1` and `or-comparison.v2`; it does not run Chronos. There is no automatic migration, seed, download, benchmark or test-job execution during deployment. The persistent volume holds weights/pin/output files; authoritative application results and queue state belong in PostgreSQL. [Volume behavior](https://docs.fly.io/volumes/overview), [image size limit](https://docs.fly.io/getting-started/troubleshooting).

`SIGTERM` requests drain and Fly's maximum 300-second shutdown window is configured. Main now permits a 690-second comparison, 720-second supervisor drain and 725-second local container grace. Fly cannot supply that whole drain window. Deliberately drain/confirm an idle lane BEFORE deploying; interrupted work requires explicit cleanup/recovery and manual retry. Do not use a deployment to interrupt current work.

## Installed local CLI

The official Windows CLI v0.4.122 is installed at ignored `artifacts/tools/flyctl/flyctl.exe`. Its archive SHA-256 was verified against the official GitHub release asset digest:

```text
e96e1568f6f22f6f5248538918dae7a542d319fc36ba6d8e362e16ca5714549b
```

From the repository root, the pass-through wrapper is:

```powershell
./scripts/install-fly.ps1
./scripts/fly.ps1 version
./scripts/fly.ps1 auth login
./scripts/fly.ps1 auth whoami
```

Global PATH and Windows/WSL settings were not changed. Login is interactive and remains outstanding. Even `config validate` and `config show --local` in this CLI require an access token; no platform-validation pass is claimed without that login. TOML parsing and the process commands can be checked offline separately. [Official release](https://github.com/superfly/flyctl/releases/tag/v0.4.122), [CLI installation](https://docs.fly.io/flyctl/install).

## When hosting is explicitly approved

1. Sign in, select the intended organization and an exact app name. Reuse the intended existing app, or explicitly create it with `fly apps create YOUR_APP --org YOUR_ORG`. Creating resources and deploying incur provider charges and were not performed by this setup.
2. Choose the region beside the dedicated Neon demo database. `iad` is an editable East-US candidate. Use a **different database/lane from any running local worker**: cross-host takeover is not qualified. Keep the current research, auth/proxy and domain-integration gates visible.
3. Configure the connected API privately in ignored `apps/api/.env.fly`: `DATABASE_URL`, `PP_DATABASE_SCHEMA`, `PP_PRESENTER_USERNAME`, `PP_PRESENTER_PASSWORD_HASH`, `PP_PRESENTER_ORGANIZATION_ID`, `PP_ALLOWED_ORIGINS` and `PP_TRUSTED_PROXY_TOKEN`. Use the selected synthetic organization and actual frontend origin, retaining the database TLS settings. Keep the same proxy token in the Next.js server environment. `PP_COOKIE_SECURE=true` is explicit in TOML; do not import the local HTTP exception. Use a separately controlled direct connection for migrations. Verify ignore rules and import secrets via stdin, never as shell-history arguments. No secrets belong in TOML or `NEXT_PUBLIC_*` values.

```powershell
git check-ignore apps/api/.env.fly
Get-Content -LiteralPath apps/api/.env.fly | ./scripts/fly.ps1 secrets import --stage --app YOUR_APP --config apps/api/fly.toml
./scripts/fly.ps1 config validate --strict --app YOUR_APP --config apps/api/fly.toml
```

4. Review the complete operational/queue/forecast/presenter-session migration graph, confirm the isolated target/schema, and apply it once from a controlled direct-connection migration environment before starting the worker. Use the deliberate migration/demo-loader procedures in [forecast flow](../pantrypulse/FORECAST-API-FLOW.md). Do not add an unconditional `release_command` against an unverified database or migrate an active local queue during this PR's validation.
5. Run the deployment **with `apps/api` as the build context**. The root-relative configuration path alone does not change Docker's build context:

```powershell
Push-Location apps/api
../../scripts/fly.ps1 deploy --remote-only --ha=false --app YOUR_APP --config fly.toml
../../scripts/fly.ps1 machine list --app YOUR_APP
../../scripts/fly.ps1 checks list --app YOUR_APP
Pop-Location
```

`--ha=false` avoids an automatic spare; it does not remove existing Machines. Confirm exactly **one worker**, one API Machine, the intended sizes and a single worker volume. Do not scale out the queue or blindly scale down pre-existing work. A volume is tied to one host/Machine; recovery after replacement remains a separately qualified operator workflow.

6. Select the **worker** Machine explicitly when preparing the model or inspecting its cache. Inside that Machine, run `python scripts/chronos_local.py prepare`, then a bounded offline smoke only during a deliberate idle maintenance window with no new job submissions. The API Machine does not mount the cache. The standalone tool bypasses queue admission; it must never overlap an active production operation. Keep test handlers private. A heartbeat or HTTP health response never proves Chronos readiness.
7. Verify the actual HTTPS health URL, runtime solver/database connectivity, worker heartbeats/effective resources, persistent checkpoint SHA, real bounded inference and unchanged saved data. Verify the existing presenter/CSRF controls and same-origin Next.js proxy against the selected origins and secure cookies. Visitor access, broader scenarios/data-management, real operations and actual hosted-target qualification remain separate. These files do not add a public Chronos endpoint.
