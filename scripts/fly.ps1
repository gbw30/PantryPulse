# Repository-local official CLI, installed under ignored artifacts/tools/flyctl.
# All arguments pass through unchanged; no app creation, login or deployment is implicit.
$flyExecutable = Join-Path (Split-Path -Parent $PSScriptRoot) 'artifacts/tools/flyctl/flyctl.exe'
if (-not (Test-Path -LiteralPath $flyExecutable)) {
    throw 'Fly CLI is not installed here. Run scripts/install-fly.ps1; see docs/setup/FLY.md.'
}
& $flyExecutable @args
exit $LASTEXITCODE
