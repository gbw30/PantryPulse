# Launch the prepared PantryPulse demo

Updated October 25, 2026. The Vercel website uses the laptop API, worker and local PostgreSQL through Cloudflare Tunnel. Chronos is enabled; the latest recorded live run used a labeled moving-average fallback. Use the [two-minute walkthrough](../pantrypulse/DEMO.md) to present.

## Resume

Open Docker Desktop and wait for its Linux engine. Keep the laptop plugged in and awake. In PowerShell:

```powershell
$demoFolder = 'C:\Users\gabri\.codex\worktrees\pr58-pr74-review\PantryPulse\artifacts\presenter_demo_20261025_135726'
if (-not (Test-Path -LiteralPath "$demoFolder\compose.yaml")) { throw 'Check the demo folder path.' }
$demoInfo = Get-Content -LiteralPath "$demoFolder\project.json" -Raw | ConvertFrom-Json
docker compose -f "$demoFolder\compose.yaml" up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Backend startup failed; inspect the error.' }
docker compose -f "$demoFolder\compose.yaml" ps
Invoke-RestMethod "$($demoInfo.api_url)/api/v1/health"
```

Expected: database/API healthy, worker running. The recorded API is `http://127.0.0.1:8021`; use `project.json` if its port changed. Startup preserves the database, saved scenes and Chronos settings.

Keep the existing tunnel terminal running. **Only if the tunnel stopped**, start it in another PowerShell window:

```powershell
cloudflared tunnel --url http://127.0.0.1:8021
```

A restarted Quick Tunnel gets a new HTTPS address. Update Vercel's **Production** `PANTRYPULSE_API_ORIGIN` with it, preserve the matching private `PP_TRUSTED_PROXY_TOKEN`, and redeploy. Use the actual API port if changed.

Open [PantryPulse](https://pantrypulse-prototype-preview.vercel.app/overview). Sign in from the sidebar as `presenter` with your existing password, then open the [saved comparisons](../pantrypulse/DEMO.md#prepared-comparisons).

The hosted website needs no local Next.js terminal. The current configuration uses secure cookies; present through HTTPS rather than the old HTTP localhost launcher.

## Quick fixes

| Problem | Check |
| --- | --- |
| Docker connection error | Wait for Docker Desktop's Linux engine. |
| Website cannot reach API | Local API health, tunnel terminal, Vercel Production API origin and redeployment after a tunnel URL change. Check [proxy health](https://pantrypulse-prototype-preview.vercel.app/api/v1/health). |
| Sign-in fails | Use the HTTPS production URL and existing password; confirm backend allowed origins include this URL. |
| Health passes but calculation fails | Worker status/logs below. API health alone does not prove compute readiness. |
| Scene missing | Use the folder ending `135726` and the saved comparison links. A new database has different records. |
| Overview says Static fixture | Confirm sign-in and a planning-ready forecast; the fixture is fallback display. |
| Port occupied | Check `docker ps`; reuse this demo if already running. Preserve its configuration and database. |
| Old date/result | Present it as historical; new planning needs fresh history, forecasts and a revised frozen scenario. |

```powershell
docker compose -f "$demoFolder\compose.yaml" logs --tail 80 api worker
```

Keep the private demo folder out of Git and screenshots. Do not rerun `setup_demo.py` to reopen it or delete its volumes. A new demo does not copy the saved scenes.

## Stop

Wait for calculations to finish. In the terminal where `$demoFolder` is set:

```powershell
docker compose -f "$demoFolder\compose.yaml" stop
```

Stop the tunnel with Ctrl+C when remote access is finished. Data stays in its volume; the website loses backend access while the laptop is stopped. On restart, repeat the steps above and update the tunnel address if changed.

Source: [recorded hosting and Chronos test status](../../artifacts/vercel-laptop-setup/status.md). These instructions do not certify a new live calculation.
