# PantryPulse: Windows installation and remote connection

Use PowerShell and run project commands from the repository root. This guide follows the local Windows environment checked on October 24, 2026.

Choose your role:

- **Hosting the API on your computer:** follow steps 1–5.
- **Connecting to someone else's API:** go to step 6. To open the API documentation or check health, you need only a browser and the host's current tunnel URL.
- **Running only your own frontend:** install Git, Node and npm in step 1, clone the repo in step 2, then follow step 6. You do not need Docker, uv, database credentials or cloudflared for that role.

The default path below uses the local PostgreSQL database from `compose.yaml`. Your `apps/api/.env` is local development configuration, **not a Neon connection**.

```text
Teammate's browser or HTTP client
    → https://<current-hostname>.trycloudflare.com
    → cloudflared on the host's Windows computer
    → FastAPI at 127.0.0.1:8000
    → PostgreSQL in Docker
```

**What currently works:** the static frontend, API health endpoint and generated API documentation. The API has no domain endpoints or CORS middleware, and the frontend has no API client yet. Setting an environment variable alone does not connect the frontend to the backend. The steps below establish dependencies and API reachability; they do not enable forecasts or allocation features.

## 1. Install the tools once

Skip tools you already have at the required version. Reopen PowerShell after installations so PATH refreshes.

| Tool | Local version / requirement | Installation |
|---|---|---|
| Git for Windows | Git 2.x | [Windows installer](https://git-scm.com/install/windows); enable Git on PATH |
| Node.js | **24.16.0** | [Windows x64 MSI](https://nodejs.org/download/release/v24.16.0/); includes npm |
| npm | **11.13.0** | Verify after installing Node; use the command below if needed |
| uv | **0.11.15** | Versioned installer below |
| Docker Desktop | Linux containers; local engine 29.9.2, Compose 5.6.1 | [Windows installation instructions](https://docs.docker.com/desktop/setup/install/windows-install/); complete first-run setup and start Docker |
| cloudflared | Local version **2026.10.3** | WinGet command below; needed only on the host publishing the API |

Install npm at the project's version if yours differs:

```powershell
npm install --global npm@11.13.0
```

Install uv using the [Astral versioned installer](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
irm https://astral.sh/uv/0.11.15/install.ps1 | iex
```

Install the tunnel client:

```powershell
winget install --id Cloudflare.cloudflared --exact --source winget
```

WinGet may install a newer cloudflared release. The official [Windows downloads](https://developers.cloudflare.com/tunnel/downloads/#windows) are an alternative.

Open a new PowerShell terminal and check:

```powershell
git --version
node --version
npm --version
uv --version
docker --version
docker compose version
docker info --format '{{.OSType}}'
cloudflared --version
```

Expected project pins: `v24.16.0`, `11.13.0`, `uv 0.11.15`. Docker must report `linux`. If Docker asks for WSL 2 or virtualization, complete its documented setup and restart if requested.

You do not need a separate PostgreSQL, Python, pip, OR-Tools or CUDA installation. uv manages Python 3.12.13 and the locked Python packages; Docker supplies PostgreSQL 16. The default setup excludes optional Chronos dependencies. For that separate model exercise, see [CHRONOS-LOCAL.md](../../CHRONOS-LOCAL.md).

## 2. Open the repository and install dependencies

For a new checkout:

```powershell
git clone https://github.com/gbw30/PantryPulse.git
Set-Location PantryPulse
```

For an existing checkout, substitute its actual location:

```powershell
Set-Location 'C:\path\to\PantryPulse'
```

Confirm you see `package.json`, `compose.yaml`, `apps` and `scripts`. Use the root checkout rather than a nested historical copy.

With Docker Desktop running, install dependencies and start the API/database:

```powershell
.\scripts\setup-windows.ps1 -WithContainerApi -WithBrowser
.\scripts\doctor-windows.ps1 -RequireContainerApi
```

The setup script runs `npm ci`, creates the Python environment from `uv.lock`, installs Playwright Chromium, builds the API container and starts PostgreSQL. It also checks a trivial solver run and database connectivity. Leave `-WithBrowser` off if you do not need browser tests.

If local policy blocks PowerShell scripts, run the equivalent commands individually without changing system security policy:

```powershell
npm ci --no-audit --no-fund
uv sync --frozen --project apps/api --python 3.12.13 --no-extra forecast
npm run test:e2e:install
npm run dev:api:docker
npm run check:runtime:docker
```

## 3. Prepare local configuration

Copy the examples only when your private files do not already exist:

```powershell
if (-not (Test-Path -LiteralPath apps/api/.env)) {
    Copy-Item apps/api/.env.example apps/api/.env
}
if (-not (Test-Path -LiteralPath apps/web/.env.local)) {
    Copy-Item apps/web/.env.example apps/web/.env.local
}
```

In `apps/api/.env`, replace `YOUR_USERNAME` and `YOUR_PASSWORD` in `DATABASE_URL` with the local values from `compose.yaml`. Keep the host address `127.0.0.1:55432` and database name `pantrypulse_dev`. Retain the `postgresql+psycopg://` scheme. Other settings can stay at the example defaults.

The API does **not** load this `.env` file yet. The Docker route works because Compose supplies its own environment, including a database URL using `postgres:5432` inside the Docker network. Do not replace that container hostname with `127.0.0.1`.

For the website on the host computer, `apps/web/.env.local` should contain:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

This is the intended API client configuration for future integration. Keep database passwords out of frontend files; `NEXT_PUBLIC_` values are public. Confirm private files are ignored:

```powershell
git check-ignore apps/api/.env apps/web/.env.local
```

If you deliberately want Neon instead of the local database, use the separate [personal-computer demo guide](LOCAL-DEMO.md). Its private `.env.demo` and `compose.demo.yaml` form a different configuration; do not combine both API containers on port 8000.

## 4. Check the server locally

After setup, the API and database run in the background. Check them:

```powershell
docker compose ps
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health'
npm run check:runtime:docker
```

Health should return `status: ok` and `scope: process`. It checks that the API process responds. The separate runtime command checks the database and a trivial CP-SAT solve.

Open [local API documentation](http://127.0.0.1:8000/docs). The current documented application route is `/api/v1/health`.

To run the static website too, open another terminal at the repository root:

```powershell
npm run dev:web
```

Open [the local website](http://127.0.0.1:3000). Leave this terminal open. The API tunnel in the next step publishes port 8000; it does not publish this website on port 3000.

## 5. Host: publish the API through Cloudflare

Keep the API running. Open a separate PowerShell terminal:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

If `cloudflared` is not found, the executable on the existing host is:

```powershell
& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://127.0.0.1:8000
```

Wait for the HTTPS address ending in `.trycloudflare.com`. Copy the actual address printed in your terminal. Leave the terminal running.

Cloudflare [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) provide temporary public URLs without a Cloudflare account or domain. Anyone with the URL can reach the published service. Use the synthetic development/demo data. This connection gives access to the HTTP API; it does not provide a Windows desktop or shell session.

In another terminal, replace the placeholder with the printed address:

```powershell
$apiOrigin = 'https://YOUR-ACTUAL-TUNNEL.trycloudflare.com'
Invoke-RestMethod "$apiOrigin/api/v1/health"
```

Expect the same health response as step 4. Share these three addresses with teammates:

| Purpose | Address to share |
|---|---|
| API base for clients | `https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/api/v1` |
| Health check | `https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/api/v1/health` |
| Interactive API docs | `https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/docs` |

Keep the host awake, online and plugged in. No router port forwarding is needed. Publish the HTTP API on port 8000; leave PostgreSQL port 55432 private.

## 6. Teammate: connect from another computer

Ask the host for the **current** tunnel address. Open its `/api/v1/health` and `/docs` URLs in a browser. At `/docs`, expand the health route, select **Try it out**, then **Execute**; expect HTTP 200. You do not need database credentials or cloudflared on your computer.

You can also check from PowerShell:

```powershell
Invoke-RestMethod 'https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/api/v1/health'
```

To develop the frontend against that API, install the Git/Node/npm tools from step 1, clone/open the repository, then:

```powershell
npm ci --no-audit --no-fund
if (-not (Test-Path -LiteralPath apps/web/.env.local)) {
    Copy-Item apps/web/.env.example apps/web/.env.local
}
```

Edit `apps/web/.env.local` with the host's actual address:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://YOUR-ACTUAL-TUNNEL.trycloudflare.com/api/v1
```

Start your own frontend:

```powershell
npm run dev:web
```

Open `http://127.0.0.1:3000` on your computer. In this file, use the tunnel URL for the remote API: `127.0.0.1:8000` would point to your own computer.

**Current integration limit:** this still shows the static scaffold. Before frontend API requests can work, the application needs an API client that reads this variable and backend CORS middleware that allows the exact frontend origin, such as `http://127.0.0.1:3000`. The `CORS_ALLOWED_ORIGINS` setting is not consumed yet. A successful PowerShell or `/docs` request does not verify cross-origin browser requests. Do not disable browser security to work around this.

For an existing Vercel frontend, set the same public API base in the intended Vercel environment and rebuild/redeploy. It has the same integration/CORS requirements; see [VERCEL.md](VERCEL.md).

## 7. Everyday restart and shutdown

After the first installation, the host starts the local API/database with:

```powershell
npm run dev:api:docker
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health'
```

Start cloudflared again using step 5 and share the newly printed URL. Update each frontend's environment and restart its dev server after a URL change; rebuild deployed frontends. Quick Tunnel addresses are temporary.

To finish:

1. Press **Ctrl+C** in the cloudflared terminal to end public access.
2. Press **Ctrl+C** in any frontend terminal to stop that website.
3. Stop the local API/database if no longer needed:

```powershell
docker compose stop api postgres
```

This preserves database data. Do not use `down -v` or delete volumes for routine shutdown.

## Troubleshooting

| Problem | Next step |
|---|---|
| `node`, `uv` or `cloudflared` is not recognized | Reopen PowerShell after installation; for cloudflared try the full host path in step 5 |
| Setup rejects a version | Match Node 24.16.0, npm 11.13.0 and uv 0.11.15; the script checks these exact versions |
| Docker engine connection fails | Start Docker Desktop, wait until ready and check that it uses Linux containers |
| Port 8000 is already in use | Check whether a native API or the separate demo container is running; stop the identified conflicting service before starting this API |
| Native Python reports a blocked DLL | Use the Docker API route; this host has previously blocked a pandas DLL used by OR-Tools |
| Local health fails | Check `docker compose ps` and `docker compose logs --tail 50 api`; get the local API working before checking the tunnel |
| Public URL fails or returns a gateway error | Recheck local health, confirm cloudflared is connected and ask the host for the latest URL |
| Quick Tunnel fails with an existing cloudflared configuration | Consult Cloudflare's Quick Tunnel instructions about `.cloudflared/config.yaml`; preserve any existing named-tunnel configuration |
| Browser reports CORS while PowerShell works | Browser integration is pending; implement the API client and exact-origin CORS handling before testing it as a full app |
| Changing `.env` has no API effect | Expected currently: the API has no dotenv/settings loader; Compose supplies container environment directly |
| Teammate opens the tunnel root and sees 404 | Use `/docs` or `/api/v1/health`; there is no API root page |

For the full dependency reference and optional verification commands, see [INSTALLATION.md](../../INSTALLATION.md). For more tunnel operations, see [CLOUDFLARE.md](CLOUDFLARE.md).
