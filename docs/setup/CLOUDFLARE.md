# Cloudflare temporary tunnel for the laptop API

Use this when teammates or a Vercel frontend need to reach the API running on the presenter's computer. A local-only presentation does not need a tunnel. The tunnel publishes the API, not the frontend or PostgreSQL.

## Install on the host's Windows computer

Install `cloudflared` using WinGet and verify its version. A common executable location is:

```text
C:\Program Files (x86)\cloudflared\cloudflared.exe
```

For another Windows developer, install and verify with:

```powershell
winget install --id Cloudflare.cloudflared --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
```

Open a new PowerShell terminal, then run `cloudflared --version`. If PATH has not refreshed, use the full executable path above. WinGet may select a newer version later; record the version actually installed. See [official Windows downloads](https://developers.cloudflare.com/tunnel/downloads/#windows).

## Start the backend first

From the repository root, follow [the laptop demo setup](LOCAL-DEMO.md) to prepare the private Neon connection, then:

```powershell
docker compose -f compose.demo.yaml up -d --build --wait api
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health'
```

Expected health: `{"status":"ok","scope":"process"}`. If another API is occupying port 8000, resolve that conflict before starting the demo container. Do not expose port 55432 or the database service.

## Start the tunnel in a separate terminal

```powershell
& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://127.0.0.1:8000
```

Leave this terminal running. Copy the actual HTTPS `trycloudflare.com` address from its output. It is a temporary public address, not a credential or a stable deployment URL. No Cloudflare account, domain, token or router port-forwarding rule is required for this Quick Tunnel. [Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

In a third terminal, replacing the example hostname:

```powershell
Invoke-RestMethod 'https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/api/v1/health'
```

The local and public responses should match. Verify both on the current host. The hostname changes after restart. A tunnel health check does not verify Neon connectivity.

## Connect teammates or Vercel

Give teammates the public API base address ending in `/api/v1`. They do not need the Neon password to call this API. They may use it as `NEXT_PUBLIC_API_BASE_URL` in their local frontend, or configure that variable in the intended Vercel environment and rebuild/redeploy there.

Frontend integration and backend CORS are not implemented yet. Once implemented, allow the exact intended frontend origins and test requests in the browser. A public health response does not establish browser integration. Use only the synthetic demo environment and verify presenter controls before exposing mutation/reset routes.

## Stop, restart and troubleshoot

- Stop the tunnel with **Ctrl+C** in its terminal. This removes public access but leaves Docker running.
- Start it again with the same command; use the new address and update any frontend configuration. Restart local frontend servers or rebuild Vercel when changing browser-embedded API URLs.
- Keep the computer awake, connected and plugged in while others use it.
- Quick Tunnels have no uptime guarantee and do not support Server-Sent Events. A stable hostname requires a separately configured named tunnel.
- If the public address fails, first check local health, then confirm the tunnel process is still connected. A gateway/origin error can indicate that the local API stopped.
- If the executable is not found, use the full path or reopen the terminal after installation.
- If an existing `.cloudflared/config.yml` or `config.yaml` conflicts with Quick Tunnel behavior, consult the provider instructions; do not overwrite an existing named-tunnel configuration.

To stop the demo API separately:

```powershell
docker compose -f compose.demo.yaml stop api
```
