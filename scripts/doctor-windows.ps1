[CmdletBinding()]
param([switch]$RequireDatabase, [switch]$RequireContainerApi)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    foreach ($tool in @('node', 'npm', 'uv', 'docker', 'git')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing $tool" }
        & $tool --version
        if ($LASTEXITCODE -ne 0) { throw "$tool failed." }
    }
    if ((node --version).Trim() -ne 'v24.16.0') { throw 'Expected Node 24.16.0.' }
    if ((npm --version).Trim() -ne '11.13.0') { throw 'Expected npm 11.13.0.' }
    if ((uv --version) -notmatch '^uv 0\.11\.15(?:\s|$)') { throw 'Expected uv 0.11.15.' }
    if (-not (Test-Path apps/api/.venv/Scripts/python.exe)) { throw 'Run setup-windows.ps1 first.' }
    & apps/api/.venv/Scripts/python.exe -c "import sys; print('Python ' + sys.version.split()[0]); raise SystemExit(0 if sys.version_info[:3] == (3, 12, 13) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Expected project Python 3.12.13.' }
    if ($RequireDatabase -or $RequireContainerApi) {
        docker compose exec -T postgres pg_isready -U pantrypulse -d pantrypulse_dev
        if ($LASTEXITCODE -ne 0) { throw 'Development database is unavailable.' }
        docker compose exec -T postgres psql -U pantrypulse -d pantrypulse_test -c 'SELECT current_database();'
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated test database is unavailable.' }
    }
    if ($RequireContainerApi) {
        docker compose exec -T api uv run --frozen python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').read().decode())"
        if ($LASTEXITCODE -ne 0) { throw 'Container API process is not healthy.' }
        docker compose exec -T api uv run --frozen python scripts/check_runtime.py --database
        if ($LASTEXITCODE -ne 0) { throw 'Container solver/database runtime check failed.' }
    }
    Write-Host 'Toolchain check passed. This does not validate allocation or forecasting.'
} finally { Pop-Location }

