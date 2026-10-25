# Project-local official CLI; no global PATH, account or deployment changes.
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$version = '0.4.122'
$archiveDigest = 'e96e1568f6f22f6f5248538918dae7a542d319fc36ba6d8e362e16ca5714549b'
$toolDirectory = Join-Path $repoRoot 'artifacts/tools/flyctl'
$executable = Join-Path $toolDirectory 'flyctl.exe'
if (Test-Path -LiteralPath $executable) {
    $installed = & $executable version
    if ($LASTEXITCODE -ne 0 -or $installed -notmatch "v$([regex]::Escape($version))\s") {
        throw 'An existing local Fly CLI has a different version or cannot run; it was left untouched.'
    }
    Write-Output $installed
    return
}
New-Item -ItemType Directory -Force -Path $toolDirectory | Out-Null
$archiveName = "flyctl_${version}_Windows_x86_64.zip"
$archive = Join-Path $toolDirectory $archiveName
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/superfly/flyctl/releases/download/v$version/$archiveName" -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archiveDigest) {
    throw 'Official Fly CLI archive checksum mismatch; nothing was extracted or executed.'
}
Expand-Archive -LiteralPath $archive -DestinationPath $toolDirectory -Force
& $executable version
if ($LASTEXITCODE -ne 0) { throw 'Fly CLI could not run after extraction.' }
