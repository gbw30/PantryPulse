[CmdletBinding()]
param([switch]$WithDatabase, [switch]$WithBrowser, [switch]$WithContainerApi)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    foreach ($tool in @('node', 'npm', 'uv')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing $tool. See INSTALLATION.md in the repository root." }
    }
    if ((node --version).Trim() -ne 'v24.16.0') { throw 'Use Node 24.16.0.' }
    if ((npm --version).Trim() -ne '11.13.0') { throw 'Use npm 11.13.0.' }
    if ((uv --version) -notmatch '^uv 0\.11\.15(?:\s|$)') { throw 'Use uv 0.11.15.' }
    if ($WithDatabase -or $WithContainerApi) {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop; see INSTALLATION.md.' }
        docker compose version
        if ($LASTEXITCODE -ne 0) { throw 'The Docker Compose plugin (docker compose) is required.' }
        $dockerOsType = docker info --format '{{.OSType}}'
        if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers before setup.' }
        if ($dockerOsType.Trim() -ne 'linux') { throw 'Switch Docker Desktop to Linux containers.' }
    }
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    uv sync --frozen --project apps/api --python 3.12.13 --no-extra forecast
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    if ($WithBrowser) {
        npm exec --workspace @pantrypulse/web -- playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed.' }
    }
    if ($WithDatabase) {
        docker compose up -d --wait postgres
        if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers and retry.' }
    }
    if ($WithContainerApi) {
        docker compose --profile api up -d --build --wait api
        if ($LASTEXITCODE -ne 0) { throw 'Container API startup failed.' }
        docker compose exec -T api uv run --frozen python scripts/check_runtime.py --database
        if ($LASTEXITCODE -ne 0) { throw 'Container backend runtime check failed.' }
    }
    Write-Host 'Dependencies ready. See INSTALLATION.md for verification and startup commands.'
    if ($WithContainerApi) { Write-Host 'API and PostgreSQL are already running; start the web app with npm run dev:web.' }
    Write-Host 'Domain migrations, forecasting and optimization are not implemented.'
} finally { Pop-Location }

