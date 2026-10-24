# Presentation backend on a personal computer

Reviewed October 24, 2026. This is the selected demo-only alternative to Fly.io. The same backend container runs on the presenter's computer. No Fly account or compute is required. The current app is still a scaffold: domain features, CORS and frontend API integration remain pending.

For installing, starting, benchmarking and stopping the optional Chronos model itself, use [CHRONOS-LOCAL.md](../../CHRONOS-LOCAL.md). That standalone runner does not require the database or API integration described here.

## Recommended arrangement

For a presentation on one laptop:

```text
Your browser → Next.js on your laptop → FastAPI in local Docker → Neon demo database
```

Use `http://127.0.0.1:3000` for the website. No tunnel or Vercel deployment is necessary when only the presenter accesses it. Neon still requires internet. A fully local PostgreSQL alternative is described below for an offline rehearsal.

If judges need to open the deployed Vercel website on their own devices, add the optional HTTPS tunnel described later.

## Hardware and prerequisites

Follow [INSTALLATION.md](../../INSTALLATION.md) first and start Docker Desktop in Linux-container mode. Docker avoids the OR-Tools native Windows Application Control issue already found on this machine.

Check available RAM before enabling Chronos; installed memory alone does not establish usable headroom. Close unused applications and measure the workload on the presentation laptop. Use the separate Chronos guide's resource envelope as an initial experiment, not a measured performance guarantee. Do not treat page-file capacity as equivalent to free RAM.

Run the core demo with seasonal-naive forecasting first when that adapter is implemented. For the intended Chronos-enabled demonstration, follow the [local compute evaluation](../pantrypulse/LOCAL-COMPUTE-EVALUATION.md): test the full model first with one resident instance and reuse unchanged forecasts. Chronos supports CPU inference, but its model load time, peak memory and forecast latency need separate testing; see the [model card](https://huggingface.co/amazon/chronos-2). The current default image excludes its dependencies. Keep the laptop plugged in and awake, and benchmark on that same device before presenting.

## 1. Put the Neon demo connection on the backend computer

Because this computer replaces Fly, it now needs the database credential that Fly would otherwise hold. This differs from the existing local-development setup, where Compose supplies a local PostgreSQL URL.

Use a dedicated synthetic-demo Neon branch/database. Do not use an unrelated production database. From the repository root, copy the template only if the private destination is absent:

```powershell
if (-not (Test-Path -LiteralPath apps/api/.env.demo)) {
    Copy-Item -LiteralPath apps/api/demo.env.example -Destination apps/api/.env.demo
}
git check-ignore apps/api/.env.demo
```

In your editor, replace the placeholder `DATABASE_URL` in `apps/api/.env.demo` with that branch's pooled Neon URL, using the `postgresql+psycopg://` scheme. Preserve encoded credentials and the supplied TLS parameters. Keep this file private and out of screenshots. Nothing in this guide fetches or invents your credentials.

`compose.demo.yaml` explicitly passes this file into the container using `env_file`. This works without an application dotenv loader. `apps/api/.env` remains the local-development template/configuration; `apps/web/.env.local` contains only the public local API address. Source: [Compose environment files](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

## 2. Start the API container

Both the development API and demo API use local port 8000. If the development API is running, stop just that API service first:

```powershell
docker compose --profile api stop api
```

This does not delete the local database or its volume. Start the separate demo project:

```powershell
docker compose -f compose.demo.yaml config --quiet
docker compose -f compose.demo.yaml up -d --build --wait api
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health'
docker compose -f compose.demo.yaml exec -T api uv run --frozen python scripts/check_runtime.py --database
docker compose -f compose.demo.yaml exec -T api uv run --frozen pytest
```

`config --quiet` validates without printing the resolved secrets. Expected health is `{"status":"ok","scope":"process"}`. The runtime command separately checks a trivial CP-SAT solve and the selected database connection. It does not validate allocation behavior or a domain schema. Do not run migrations or seed/reset commands until implemented and tested.

Use the explicit `-f compose.demo.yaml` commands for this project. Existing npm Docker commands target the development Compose project, not this demo container.

## 3. Start the website on the same computer

Confirm `apps/web/.env.local` has the public address only:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

In a second PowerShell terminal at the repository root:

```powershell
npm run dev:web
```

Open `http://127.0.0.1:3000`. Leave the terminal running. Restart Next.js after changing environment values. This currently displays the scaffold; once the API client exists, it must read the configured URL. Even on one computer, ports 3000 and 8000 are different browser origins, so settings/CORS or a same-origin proxy must be implemented for the full workflow.

For final presentation polish, rehearse a production frontend build rather than relying only on the development server:

```powershell
npm run build
npm run start --workspace @pantrypulse/web
```

Stop the development web server first so port 3000 is free. The current workspace start command binds to loopback, appropriate for a presentation on this computer.

## 4. Optional: let the Vercel website reach your laptop

Skip this section when presenting only in your own browser. Install `cloudflared` from the official [Windows downloads](https://developers.cloudflare.com/tunnel/downloads/#windows), add the installed executable to PATH if necessary, and verify `cloudflared --version` in a new terminal.

With the API running, keep a separate terminal open:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints an HTTPS `trycloudflare.com` address. Use the actual address, not this placeholder. Quick Tunnels need no account/domain, provide no uptime guarantee, and change hostname after restart. They do not support Server-Sent Events, so use a different tunnel arrangement if that later becomes necessary. See [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

In the intended Vercel environment set:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://YOUR-TUNNEL.trycloudflare.com/api/v1
```

Rebuild/redeploy Vercel after that change. Configure the exact Vercel origin in the backend CORS allowlist once parsing/middleware exist. This must be tested in the browser; a tunnel health request alone proves only reachability. Never point a shared Vercel site to `127.0.0.1`: that address refers to each visitor's own computer.

The tunnel publishes the API to people who know the URL. Use synthetic demo data and implement/verify the intended presenter boundary for reset or other mutations before exposing those routes. Do not tunnel PostgreSQL or port 55432. No router port forwarding is needed for this method. On a tunnel restart, update the Vercel API URL and redeploy, or use a configured stable tunnel for repeat demonstrations.

## 5. Rehearse and stop

- Close unused applications, keep AC power connected and prevent sleep for the presentation.
- Verify Docker memory limits allow the measured workload; leave enough for Windows, the browser and the web server.
- Test API health, database connectivity and the eventual complete comparison workflow separately.
- Download any optional model in advance; verify provenance/cache and retain a labeled fallback.
- Keep the backend/tunnel running while remote viewers use the website. Restarting the laptop interrupts access.
- Keep a backup recording and clearly label it if used. Test venue networking before the presentation.

To stop only the demo API:

```powershell
docker compose -f compose.demo.yaml stop api
```

Stop the web server and optional tunnel with Ctrl+C in their terminals. The Neon data is hosted separately; stopping the container does not delete it. No destructive cleanup is needed.

## Offline alternative: existing local PostgreSQL

For an offline presentation, use the original development Compose project instead of the Neon demo project. Stop the demo API first to free port 8000, then:

```powershell
npm run dev:api:docker
npm run check:runtime:docker
npm run dev:web
```

This selects the original **local** database, not Neon. Its domain schema and synthetic demo seed still need to be prepared before a full offline workflow can work. It does not copy hosted data automatically. No Neon credentials or tunnel are required for this arrangement once dependencies/images are available locally.
