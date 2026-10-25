# PantryPulse external services and laptop demo setup

> **Current authority:** [Project specification V5](docs/pantrypulse/SPEC-V5.md). Setup procedure reference. V5 governs current requirements and status, including the selected same-origin Next.js proxy. Direct API/tunnel examples establish reachability only. Backend/model hosting remains paused; only the simulated [Vercel UI preview](docs/setup/VERCEL.md) was separately authorized and deployed.

Updated October 24, 2026. **The selected future integrated demo runs the backend on your laptop in Docker, with Neon as the hosted PostgreSQL database. Fly.io is not required.** That backend/model setup remains paused. This guide records its setup path; local tool installation is in [INSTALLATION.md](INSTALLATION.md).

## 1. What is already done, and what is missing

| Item | Status | Next action |
|---|---|---|
| Neon console setup | Required for the hosted database path | Create or identify the exact project, branch, database, role and Postgres version |
| Local backend container configuration | Prepared in [compose.demo.yaml](compose.demo.yaml) | Supply the dedicated demo database connection and start it |
| Private demo connection file | Developer-specific; excluded from Git | Create `apps/api/.env.demo` from the template if absent and edit privately |
| Laptop-to-Neon connection | Not verified | Run the container runtime/database smoke check below |
| Local frontend environment | No variable needed for current scaffold | Future proxy server-side configuration is still to be designed |
| Full application integration | Not implemented | Add the frontend API client, same-origin proxy, FastAPI authorization, domain persistence and migrations |
| Backend primitives | Implemented | Transfer modes, route eligibility, rounding, fixed-point arithmetic, solver outcomes and history alignment are available; integrate them into the complete workflow |
| Allocation/forecasting demonstration | Not implemented | Complete research validation, both allocation engines, forecasts/fallback and the deterministic comparison fixture |
| Simulated remote UI preview | Deployed from `codex/vercel-prototype-preview` | Open the [branch preview](https://pantrypulse-prototype-preview-git-codex-e82088-gbw30s-projects.vercel.app/); it has no API or database |
| Integrated remote judge access | Not configured | Implement the V5 proxy/auth/backend/database path before claiming a full demo |

Creating a Neon project establishes the database service. It does not create PantryPulse's tables or connect the application automatically. A successful health response alone does not prove the database or allocation workflow works.

## 2. Which services are necessary

| Component | Role | Needed for the chosen presentation setup? |
|---|---|---|
| Your laptop + Docker Desktop | Runs FastAPI and OR-Tools | Yes |
| Neon | Stores the dedicated hosted demo data | Yes for this path; requires internet |
| GitHub | Stores source and supports team collaboration | Existing project repository; no new repository needed |
| Local Next.js frontend | Website opened in your laptop's browser | Yes for the simplest presentation |
| Vercel | Hosts the current simulated frontend preview; could host a later integrated frontend | Preview already configured; integrated use pending |
| Cloudflare Tunnel (`cloudflared`) | Gives the laptop API a public HTTPS address | Optional, paired with the hosted frontend below |
| Hugging Face | Optional Chronos-2 model artifacts | Optional; no paid inference endpoint is required |
| Fly.io / Railway | Alternative hosted backend compute | Not required |
| Object storage, Redis, Kubernetes, extra database provider | Additional infrastructure | Not required for this MVP |

For a presentation on your laptop:

```text
Your browser → Next.js on your laptop → FastAPI in local Docker → Neon PostgreSQL
```

For judges using a hosted website on their own devices:

```text
Judge's browser → Next.js on Vercel with thin same-origin proxy → HTTPS tunnel → FastAPI on your laptop → Neon
```

The second topology is a future integrated-demo design, not the deployed `/design-lab` preview. The current preview serves synthetic UI content without a tunnel or backend. In an integrated laptop demo, allocation calculations run on your laptop. Increasing Neon compute does not give OR-Tools or Chronos more CPU/RAM.

## 3. Confirm the existing Neon environment

Reuse an existing authorized project when available; otherwise create a dedicated synthetic-demo project. In the [Neon console](https://console.neon.tech):

1. Record the project name/ID, region, plan and Postgres major version.
2. Select the intended synthetic-demo branch and database. `pantrypulse_demo` is an example name; use your actual database name rather than renaming or deleting existing resources.
3. Keep any development/test branch separate from the presentation data. Branches have distinct endpoints, even when the database names are the same.
4. In **Connect**, select that exact branch, database and role, then obtain the **pooled** application connection URL.
5. For SQLAlchemy/psycopg 3, change only the URL scheme from `postgresql://` to `postgresql+psycopg://`. Preserve the encoded username/password, host, database and all supplied TLS/security parameters.

Example format only:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:ENCODED_PASSWORD@POOLED_HOST/ACTUAL_DATABASE?sslmode=require
```

The actual endpoint must come from Neon. Do not paste credentials into this guide, Git, screenshots or the frontend. Reserve a direct/unpooled URL for a later controlled migration workflow; the current scaffold does not load `DATABASE_URL_UNPOOLED`.

Keep the existing region unless testing identifies a problem. With a laptop backend there is no Fly region to match. Postgres 16 matches local development; record and test another selected major rather than assuming compatibility. Start with a small primary compute and measure database queries; leave unrelated services disabled. Detailed options: [Neon project settings](docs/setup/NEON.md#recommended-project-settings), [pooled connections](https://neon.com/docs/connect/connection-pooling).

## 4. Store the database secret on the backend laptop

**For this laptop-hosted Neon demo, the connection goes in `apps/api/.env.demo`.** This is different from the original local-only Docker setup, where Compose supplies its own local PostgreSQL URL.

| File/location | Purpose |
|---|---|
| `apps/api/.env.demo` | Private pooled Neon demo connection; explicitly loaded by the demo container |
| `apps/api/.env` | Existing local-development configuration; leave unchanged |
| `compose.yaml` | Existing local PostgreSQL/API setup; leave unchanged |
| `apps/web/.env.local` | Public local API address only; never database credentials |
| Future migration environment | Direct Neon connection, scoped to the intended environment |

From the repository root, copy the template only if the destination is absent:

```powershell
if (-not (Test-Path -LiteralPath apps/api/.env.demo)) {
    Copy-Item -LiteralPath apps/api/demo.env.example -Destination apps/api/.env.demo
}
git check-ignore apps/api/.env.demo
```

Open `apps/api/.env.demo` in your editor and replace its placeholder URL with the real pooled demo connection. The ignore check must identify the file as ignored. Never commit it.

The separate [demo Compose file](compose.demo.yaml) uses `env_file` to inject the values into the container. This does not require the API to implement a dotenv loader. Merely placing a URL in some other `.env` file will not switch the container's database. [Docker environment-file behavior](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

## 5. Run and verify the laptop backend

Install/start Docker Desktop in Linux-container mode and complete the existing local dependency setup. The Linux API container avoids the native Windows OR-Tools dependency restriction found on this computer.

Run these commands from the repository root. If the development API already occupies port 8000, stop only that service first:

```powershell
docker compose --profile api stop api
```

Then validate and start the separate demo API:

```powershell
docker compose -f compose.demo.yaml config --quiet
docker compose -f compose.demo.yaml up -d --build --wait api
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health'
docker compose -f compose.demo.yaml exec -T api uv run --frozen python scripts/check_runtime.py --database
docker compose -f compose.demo.yaml exec -T api uv run --frozen pytest
```

`config --quiet` avoids printing the resolved credentials. Expected health is `{"status":"ok","scope":"process"}`. The separate runtime command checks a trivial CP-SAT solve and a read-only database connection. Confirm its database name matches the intended Neon database. The pytest command runs the implemented scaffold tests, not a complete allocation acceptance suite.

These commands do not create the domain schema, run migrations, seed data or implement algorithms. No migration command is ready yet. The demo Compose project has no local PostgreSQL service and does not delete or replace the original local database volume.

Use commands with `-f compose.demo.yaml` for this environment. Existing npm Docker scripts target the original local-development project. To inspect demo logs or stop its API:

```powershell
docker compose -f compose.demo.yaml logs --tail 100 api
docker compose -f compose.demo.yaml stop api
```

Do not print the connection string while troubleshooting. See [LOCAL-DEMO.md](docs/setup/LOCAL-DEMO.md) for fuller presentation instructions.

## 6. Run the website locally

For the simplest frontend check, keep the website on the same laptop. The current static scaffold needs no `apps/web/.env.local`; earlier `NEXT_PUBLIC_API_BASE_URL` examples are unused and do not implement the V5 proxy.

In another terminal at the repository root:

```powershell
npm run dev:web
```

Open `http://127.0.0.1:3000` and leave the server running. No Vercel account or tunnel is needed for this arrangement. The future integrated frontend must route browser requests through the selected same-origin Next.js proxy.

Before the presentation, rehearse the production frontend build too. Stop the development web server before starting this on port 3000:

```powershell
npm run build
npm run start --workspace @pantrypulse/web
```

The current frontend does not call the backend. Running both processes is infrastructure readiness, not a completed demonstration.

## 7. Future integrated remote access: Vercel plus a tunnel

The current Vercel `/design-lab` preview already works on other devices without this section. Use these tunnel steps only after the V5 proxy, authentication and API/database integration are implemented and reviewed. For that future topology, Vercel hosts the website while your laptop runs backend calculations.

For Windows installation, start/stop commands and teammate access instructions, follow [CLOUDFLARE.md](docs/setup/CLOUDFLARE.md). Verify local and public API health on the current host; this does not verify Neon connectivity or frontend integration.

1. Install `cloudflared` from [Cloudflare's Windows downloads](https://developers.cloudflare.com/tunnel/downloads/#windows) and ensure it is available on PATH.
2. With the local API running, open a separate terminal:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

3. Record the actual HTTPS `trycloudflare.com` URL printed by the tunnel.
4. Implement and test the thin same-origin Next.js proxy, FastAPI authorization and server-side API-origin configuration. Do not put the tunnel URL in `NEXT_PUBLIC_API_BASE_URL` on the current preview.
5. Connect a separately reviewed integrated Preview to the correct synthetic API/database pair. Test the real Vercel page, including authenticated operations and failure states, before claiming judge readiness.

A server-side proxy running on Vercel cannot use `127.0.0.1` to reach the laptop: that address resolves inside Vercel's runtime. Quick Tunnels require no Cloudflare account/domain, change hostname on restart, have no uptime guarantee, and do not support Server-Sent Events. Keep the tunnel terminal open; if the URL changes, update the future server-side proxy configuration and redeploy. [Quick Tunnel reference](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Only expose the API for the synthetic demo. Verify presenter controls before publishing reset/adjustment endpoints; CORS is not authentication. Do not expose PostgreSQL or configure router port forwarding for this tunnel approach.

## 8. Application work still missing

These are development tasks, not additional account signups:

1. Validate the research formulation and bounded adaptation before implementing complex optimization.
2. Implement the domain schema, Alembic migrations and deterministic simulated seed/reset workflow.
3. Connect application persistence to the injected database URL, with deliberate settings parsing and role permissions.
4. Implement shared inventory, FEFO, capacity and feasibility rules, plus both allocation engines and independent comparison metrics.
5. Implement the forecast adapter/fallback and truthful provenance. Chronos remains optional and must be benchmarked on the laptop.
6. Implement the frontend API client, result charts, pending/error states and selected same-origin proxy.
7. Test the full comparison on identical snapshots, protect any exposed mutations, and rehearse the judge journey.

The default image excludes optional Chronos dependencies. Installing the extra in a local Python environment does not modify the Docker image. See [optional model setup](docs/setup/HUGGING-FACE.md) and the [implementation plan](docs/pantrypulse/IMPLEMENTATION-PLAN.md).

## 9. Presentation checklist and fallback

- [ ] Neon project selected and its details confirmed for this environment.
- [ ] Exact demo branch/database/role recorded without passwords.
- [ ] Real pooled connection stored privately in `apps/api/.env.demo`.
- [ ] Laptop API process health, solver smoke, database connection and scaffold tests pass in the demo environment.
- [ ] Frontend is running locally; if claiming integrated remote access, the Vercel proxy/tunnel/API mapping is verified. The existing static preview alone does not satisfy this item.
- [ ] Domain features and full paired comparison are implemented and tested.
- [ ] Laptop remains plugged in, awake and connected; unused applications are closed.
- [ ] Any model artifacts are already downloaded, with measured memory/latency and a labeled fallback.
- [ ] Backup recording/local rehearsal and venue-network checks are complete.

Neon requires internet even when compute runs on your laptop. The original local PostgreSQL setup can be used for an offline fallback once its schema and synthetic dataset are prepared; it does not automatically copy Neon data. See [the offline alternative](docs/setup/LOCAL-DEMO.md#offline-alternative-existing-local-postgresql).

Record the Git commit, laptop/container image, chosen database branch, schema revision, dataset hash, solver settings and forecast provenance for the eventual release. Keep credentials out of that record. [Deployment and recovery](docs/pantrypulse/DEPLOYMENT.md) covers the later application release gates.

If hosted backend compute is needed later, the old Fly.io instructions are retained separately in [FLY.md](docs/setup/FLY.md). They are not steps required for this laptop demo.
