# Windows setup and teammate connection

Updated October 25, 2026. Use PowerShell from the repository root. [Current status](../pantrypulse/CURRENT-STATUS.md) describes the merged source; older running images and the separate Vercel preview may differ.

## Install and inspect

Follow [INSTALLATION.md](../../INSTALLATION.md) for Git, Node 24.16.0, npm 11.13.0, uv 0.11.15, Python 3.12.13 and Docker Desktop/Linux containers. Do not disable Windows Application Control, alter global WSL limits, reboot or stop another task as part of routine setup.

```powershell
git status --short
node --version
npm --version
uv --version
docker ps
```

Preserve dirty files and existing services. Check ports before starting another API/web pair. PostgreSQL development uses loopback 55432; the normal API/web pair uses 8000/3000. A teammate needs a reachable frontend URL and the configured demo presenter access, not database credentials.

## Host bounded local compute

```powershell
./scripts/compute-windows.ps1 Status
./scripts/compute-windows.ps1 Build
```

The opt-in helper uses a separate two-CPU/three-GiB builder and disk-backed export. It does not make itself the default builder or change global settings. Follow [LOCAL-COMPUTE.md](LOCAL-COMPUTE.md) to deliberately migrate/seed a selected isolated schema and configure private API settings before `Start`. `Start` preserves existing containers; adopting new images requires a later controlled update after jobs finish.

For a connected demo, use the NEW `ppor_demo_*` loader procedure in [CONNECTED-INTEGRATION.md](../optimization/CONNECTED-INTEGRATION.md), not a reset of an existing database. Configure presenter username/password hash/organization, schema, allowed origins and proxy token privately. For Neon use the separately selected `compose.forecast.yaml` environment; the local compute overlay deliberately fixes its database to local development.

## Run the connected frontend

Create private `apps/web/.env.local` from its tracked example when absent, using the server-only values:

```dotenv
PANTRYPULSE_API_ORIGIN=http://127.0.0.1:8000
PP_TRUSTED_PROXY_TOKEN=YOUR_PRIVATE_MATCHING_TOKEN
```

The backend token must match, its allowed origins must include the actual browser origin, and local HTTP alone can use `PP_COOKIE_SECURE=false`. Hosted HTTPS requires secure cookies. Do not place these values in `NEXT_PUBLIC_*` variables or commit them.

```powershell
npm run dev:web
```

Open `http://127.0.0.1:3000/optimization`. Main redirects `/` there. Log in, generate a real baseline forecast, create an explicit-mode frozen scenario and submit a durable comparison. Saved results show native status, verification, partial failures and provenance. This source path is implemented; environment variables alone do not prove that a particular runtime is correctly migrated/configured.

## Chronos tools

```powershell
./scripts/compute-windows.ps1 Prepare
./scripts/compute-windows.ps1 Smoke
./scripts/compute-windows.ps1 Session
```

Use only after the headroom/lane guards allow and the operator has excluded concurrent domain jobs. The full pinned model has standalone CPU evidence, but application forecasting remains baseline-only. Type `quit` to end your own interactive model session; persistent weights remain cached.

## Remote access and checks

The old branch-scoped Vercel `/design-lab` preview is synthetic and needs no backend. For a separately authorized connected frontend, use the implemented same-origin proxy and [Cloudflare procedure](CLOUDFLARE.md) with actual HTTPS API origin, trusted ingress and presenter/cookie settings. Never expose PostgreSQL or stop another service to free a port.

Health `/api/v1/health` proves process liveness only. Verify database/schema, fresh capability-version-2 supervisor, authenticated browser requests and completed saved results on the chosen runtime. Source CI is active and rejects skipped backend/browser evidence. See [worker recovery](WORKER-QUEUE.md) and [deployment/recovery](../pantrypulse/DEPLOYMENT.md).

| Symptom | Check |
|---|---|
| Model/helper refuses work | Available host/VM headroom, existing model container, active/recovering queue; leave those tasks intact |
| New computation returns 503 | Correct schema, migrations and fresh version-2 worker capability; saved reads are separate |
| Login/origin/CSRF fails | Browser origin, matching server-only proxy token, secure-cookie policy and external Host/protocol |
| Port already occupied | Identify the owner; use an isolated target/ports rather than stopping it automatically |
| Native Windows library blocked | Use the documented Linux container, preserving security policy |
| Source updated but behavior unchanged | Inspect actual image/commit; `--no-recreate` intentionally preserves older running containers |
