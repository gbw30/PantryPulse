<#
.SYNOPSIS
  One-command local connected demo: isolated Postgres + API + worker in Docker, seeded once, then the
  web app with the real proxy. The Overview shows database values (visitors read-only, presenter
  sign-in at /optimization for data entry).

.DESCRIPTION
  Separate from the developer `pantrypulse` compose stack: its own containers (pp-local-*), network,
  volume and ports. Data persists in the `pp-local-pgdata` volume between runs; pass -Reset to start
  over. Throwaway presenter credentials are generated once into artifacts/local-demo/presenter.env
  (gitignored) and never printed.

.EXAMPLE
  pwsh -File scripts/demo-local.ps1
  pwsh -File scripts/demo-local.ps1 -Reset -WebPort 3100
#>
param(
  [int]$WebPort = 3000,
  [int]$ApiPort = 8010,
  [int]$DbPort = 55433,
  [switch]$Reset,
  [switch]$NoForecast,
  [switch]$NoWeb
)
# Continue: Windows PowerShell 5.1 turns redirected native stderr into terminating errors under Stop.
# Failures are checked explicitly (Invoke-Docker throws; web calls use -ErrorAction Stop).
$ErrorActionPreference = "Continue"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$state = Join-Path $root "artifacts/local-demo"
$schema = "ppor_demo_local"
$net = "pp-local-net"
$image = "pp-local-api"
$dbInside = "postgresql+psycopg://pp:pp_local_only@pp-local-pg:5432/pp_local"
$origin = "http://127.0.0.1:$WebPort"
# Run from the repo layout (read-only mount), as CI does: some scripts resolve repo-root data/demo.
# The image only supplies the locked Python environment.
$repoMount = @("-v", "${root}:/repo:ro", "-w", "/repo/apps/api", "-e", "UV_PROJECT_ENVIRONMENT=/app/.venv", "-e", "PYTHONDONTWRITEBYTECODE=1")

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Invoke-Docker { & docker.exe @args; if ($LASTEXITCODE -ne 0) { throw "docker $($args -join ' ') failed" } }

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop and rerun." }
New-Item -ItemType Directory -Force $state | Out-Null

if ($Reset) {
  Step "Resetting the local demo (containers, volume, generated credentials)"
  foreach ($name in "pp-local-worker", "pp-local-api", "pp-local-pg") { docker rm -f $name *> $null }
  docker volume rm pp-local-pgdata *> $null
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $state "demo.json"), (Join-Path $state "presenter.env")
}

Step "Network and database"
docker network inspect $net *> $null; if ($LASTEXITCODE -ne 0) { Invoke-Docker network create $net | Out-Null }
$running = docker ps --filter "name=^pp-local-pg$" --format "{{.Names}}"
if (-not $running) {
  docker rm -f pp-local-pg *> $null
  Invoke-Docker run -d --name pp-local-pg --network $net -p "127.0.0.1:${DbPort}:5432" -v pp-local-pgdata:/var/lib/postgresql/data `
    -e POSTGRES_USER=pp -e POSTGRES_PASSWORD=pp_local_only -e POSTGRES_DB=pp_local postgres:16 | Out-Null
}
for ($i = 0; $i -lt 60; $i++) { docker exec pp-local-pg pg_isready -U pp -d pp_local *> $null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 1 }

Step "API image (apps/api)"
Invoke-Docker build -q -t $image (Join-Path $root "apps/api") | Out-Null

$demoFile = Join-Path $state "demo.json"
if (-not (Test-Path $demoFile)) {
  Step "Seeding the fictional demo schema $schema (first run only)"
  Invoke-Docker run --rm --network $net @repoMount -v "${state}:/out" -e DATABASE_URL_UNPOOLED=$dbInside $image `
    uv run --frozen python scripts/load_optimization_demo.py --schema $schema --output /out/demo.json | Out-Null
}
$demo = Get-Content $demoFile -Raw | ConvertFrom-Json
$org = $demo.organization_id

$envFile = Join-Path $state "presenter.env"
if (-not (Test-Path $envFile)) {
  Step "Generating throwaway presenter credentials (artifacts/local-demo/presenter.env)"
  $gen = @'
import hashlib, secrets, sys
password = secrets.token_urlsafe(18); salt = secrets.token_bytes(16)
digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64).hex()
print("PP_PRESENTER_USERNAME=presenter")
print("PP_E2E_PASSWORD=" + password)
print(f"PP_PRESENTER_PASSWORD_HASH=scrypt$16384$8$1${salt.hex()}${digest}")
print("PP_TRUSTED_PROXY_TOKEN=" + secrets.token_urlsafe(32))
'@
  $gen | docker run --rm -i $image uv run --frozen python - | Set-Content -Encoding ascii $envFile
  if ($LASTEXITCODE -ne 0) { throw "credential generation failed" }
}
$creds = @{}; Get-Content $envFile | ForEach-Object { $k, $v = $_ -split "=", 2; if ($k) { $creds[$k] = $v } }

$apiEnv = @(
  "-e", "DATABASE_URL=$dbInside", "-e", "PP_DATABASE_SCHEMA=$schema",
  "-e", "PP_ALLOWED_ORIGINS=$origin", "-e", "PP_COOKIE_SECURE=false",
  "-e", "PP_PRESENTER_USERNAME=$($creds.PP_PRESENTER_USERNAME)", "-e", "PP_PRESENTER_PASSWORD_HASH=$($creds.PP_PRESENTER_PASSWORD_HASH)",
  "-e", "PP_PRESENTER_ORGANIZATION_ID=$org", "-e", "PP_TRUSTED_PROXY_TOKEN=$($creds.PP_TRUSTED_PROXY_TOKEN)",
  "-e", "PP_VISITOR_ORGANIZATION_ID=$org"
)

Step "API (127.0.0.1:$ApiPort) and worker"
foreach ($name in "pp-local-worker", "pp-local-api") { docker rm -f $name *> $null }
Invoke-Docker run -d --name pp-local-api --network $net -p "127.0.0.1:${ApiPort}:8000" @repoMount @apiEnv $image `
  uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000 | Out-Null
Invoke-Docker run -d --name pp-local-worker --network $net @repoMount @apiEnv $image `
  uv run --frozen python -m app.workers.supervisor --registry production --schema $schema | Out-Null
$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop "http://127.0.0.1:$ApiPort/api/v1/health" | Out-Null; $healthy = $true; break } catch { Start-Sleep 1 }
}

if (-not $healthy) { throw "API did not become healthy; see: docker logs pp-local-api" }

if (-not $NoForecast) {
  Step "Submitting one forecast so the Overview has planning-ready statuses"
  $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $login = Invoke-RestMethod -ErrorAction Stop -Method Post -WebSession $session -ContentType "application/json" -Headers @{ Origin = $origin } `
    -Uri "http://127.0.0.1:$ApiPort/api/v1/presenter/login" `
    -Body (@{ username = $creds.PP_PRESENTER_USERNAME; password = $creds.PP_E2E_PASSWORD } | ConvertTo-Json)
  $body = $demo.request | ConvertTo-Json -Depth 20
  try {
    Invoke-RestMethod -ErrorAction Stop -Method Post -WebSession $session -ContentType "application/json" `
      -Headers @{ Origin = $origin; "X-CSRF-Token" = $login.csrf_token; "Idempotency-Key" = [guid]::NewGuid().ToString() } `
      -Uri "http://127.0.0.1:$ApiPort/api/v1/forecasts" -Body $body | Out-Null
    Write-Host "    forecast queued; the worker publishes it in a minute or so"
  } catch { Write-Warning "Forecast submission failed ($($_.Exception.Message)); submit one from /optimization." }
}

Write-Host ""
Write-Host "Local connected demo is up." -ForegroundColor Green
Write-Host "  Overview:   $origin/overview   (visitors see saved data read-only)"
Write-Host "  Sign in:    $origin/optimization  (username 'presenter'; password: PP_E2E_PASSWORD in artifacts/local-demo/presenter.env)"
Write-Host "  API docs:   http://127.0.0.1:$ApiPort/docs"
Write-Host "  Stop:       docker rm -f pp-local-worker pp-local-api pp-local-pg   (data stays in volume pp-local-pgdata)"

if (-not $NoWeb) {
  Step "Web app on $origin (Ctrl+C to stop)"
  $env:PANTRYPULSE_API_ORIGIN = "http://127.0.0.1:$ApiPort"
  $env:PP_TRUSTED_PROXY_TOKEN = $creds.PP_TRUSTED_PROXY_TOKEN
  Push-Location $root
  try { npm run dev --workspace @pantrypulse/web -- --port $WebPort } finally { Pop-Location }
}
