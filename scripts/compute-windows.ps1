[CmdletBinding()]
param(
    [ValidateSet('Status', 'Build', 'Start', 'Prepare', 'Smoke', 'Benchmark', 'Session')]
    [string]$Action = 'Status'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeArgs = @('compose', '-f', 'compose.yaml', '-f', 'compose.compute.yaml')

function Invoke-Docker {
    param([string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}

Push-Location $repoRoot
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $freeGiB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    $freeDiskGiB = [math]::Round((Get-Item $repoRoot).PSDrive.Free / 1GB, 2)
    Write-Host "Available host RAM: $freeGiB GiB; available checkout disk: $freeDiskGiB GiB."
    Invoke-Docker @('info', '--format', 'Docker: {{.OSType}}, {{.NCPU}} CPUs, {{.MemTotal}} bytes RAM')
    Invoke-Docker ($composeArgs + @('--profile', 'api', '--profile', 'compute', '--profile', 'model-tools', 'config', '--quiet'))
    # Image imports can leave WSL RAM full of reclaimable file cache. A container
    # can reuse those already-resident pages without growing the VM on Windows.
    $vmAvailableGiB = 0
    $vmCleanCacheGiB = 0
    $runningIds = @(& docker @composeArgs ps -q worker api postgres)
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect local service containers.' }
    if ($runningIds.Count -gt 0) {
        $meminfo = & docker exec $runningIds[0] cat /proc/meminfo
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Docker VM memory.' }
        $memoryKiB = @{}
        foreach ($line in $meminfo) {
            if ($line -match '^(\w+):\s+(\d+) kB') { $memoryKiB[$matches[1]] = [double]$matches[2] }
        }
        $vmAvailableGiB = [math]::Round($memoryKiB['MemAvailable'] / 1MB, 2)
        $vmCleanCacheGiB = [math]::Round([math]::Max(0, ($memoryKiB['Cached'] - $memoryKiB['Shmem'] - $memoryKiB['Dirty'] - $memoryKiB['Writeback'])) / 1MB, 2)
        Write-Host "Docker VM available RAM: $vmAvailableGiB GiB; clean file cache: $vmCleanCacheGiB GiB."
    }

    if ($Action -eq 'Status') {
        Invoke-Docker @('ps', '--format', '{{.Names}} | {{.Status}} | {{.Ports}}')
        Invoke-Docker @('stats', '--no-stream', '--format', '{{.Name}} | {{.CPUPerc}} | {{.MemUsage}}')
        Write-Host 'Resource limits are ceilings, not reserved host RAM. Source supports baseline forecasts and OR comparisons; verify the installed worker image. Chronos tools remain standalone.'
        return
    }
    if ($Action -eq 'Build') {
        if ($freeDiskGiB -lt 30 -or ($freeGiB -lt 4 -and ($vmAvailableGiB -lt 6 -or $vmCleanCacheGiB -lt 6))) {
            throw 'Build needs 30 GiB free disk and either 4 GiB free host RAM or 6 GiB reusable Docker VM cache/headroom. Existing tasks were left untouched.'
        }
        $builderName = 'pantrypulse-compute-build'
        $builderNames = & docker buildx ls --format '{{.Name}}'
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect builders.' }
        if ($builderName -notin $builderNames) {
            Invoke-Docker @('buildx', 'create', '--name', $builderName, '--driver', 'docker-container', '--driver-opt', 'memory=3g,memory-swap=3g,cpu-period=100000,cpu-quota=200000')
        }
        $builderInspection = & docker buildx inspect $builderName
        if ($LASTEXITCODE -ne 0 -or -not ($builderInspection -match '^Driver:\s+docker-container\s*$')) {
            throw 'Existing builder does not provide the expected container resource boundary; it was left unchanged.'
        }
        Invoke-Docker @('buildx', 'inspect', $builderName, '--bootstrap')
        $builderContainer = "buildx_buildkit_${builderName}0"
        $builderLimitsJson = & docker inspect $builderContainer --format '{"quota":{{.HostConfig.CpuQuota}},"period":{{.HostConfig.CpuPeriod}},"memory":{{.HostConfig.Memory}},"swap":{{.HostConfig.MemorySwap}}}'
        if ($LASTEXITCODE -ne 0) { throw 'Could not establish builder resource limits; refusing the build.' }
        $builderLimits = $builderLimitsJson | ConvertFrom-Json
        if ($builderLimits.quota -le 0 -or $builderLimits.period -le 0 -or
            $builderLimits.quota / $builderLimits.period -gt 2 -or
            $builderLimits.memory -le 0 -or $builderLimits.memory -gt 3GB -or
            $builderLimits.swap -lt $builderLimits.memory -or $builderLimits.swap -gt 3GB) {
            throw 'Existing builder exceeds the 2-CPU/3-GiB boundary; it was left unchanged.'
        }
        $imageDirectory = Join-Path $repoRoot 'artifacts/compute-setup'
        New-Item -ItemType Directory -Force -Path $imageDirectory | Out-Null
        $imageTar = Join-Path $imageDirectory 'compute-image.tar'
        # On Windows --load can buffer the entire tar in docker-buildx.exe.
        # Export to disk, then stream it into the engine with docker image load.
        Invoke-Docker @('buildx', 'build', '--builder', $builderName, '--output', "type=docker,dest=$imageTar", '--tag', 'pantrypulse-compute:local', '--file', 'apps/api/Dockerfile.compute', 'apps/api')
        Invoke-Docker @('image', 'load', '--input', $imageTar)
        # Docker's containerd image-store Size includes stored compressed content;
        # Fly's rootfs limit concerns uncompressed layers. Sum exact history bytes.
        $layerSizes = @(& docker history --human=false --format '{{.Size}}' pantrypulse-compute:local)
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect compute image layers.' }
        $rootfsBytes = ($layerSizes | ForEach-Object { [long]$_ } | Measure-Object -Sum).Sum
        if ($rootfsBytes -ge 8000000000) { throw 'Compute image exceeds Fly''s 8 GB rootfs envelope.' }
        Write-Host "Uncompressed compute image layers: $rootfsBytes bytes; below Fly's 8 GB ceiling."
        return
    }
    if ($Action -eq 'Start') {
        # Never recreate running services, migrate, reset data or launch test handlers here.
        # Existing containers retain their current image/config; first setup applies caps separately.
        Invoke-Docker ($composeArgs + @('--profile', 'api', '--profile', 'compute', 'up', '-d', '--no-recreate', '--no-build', '--wait', 'api', 'worker'))
        Write-Host 'API: http://127.0.0.1:8000/api/v1/health. Worker heartbeat does not establish model/domain readiness.'
        return
    }
    if ($freeGiB -lt 4 -and ($vmAvailableGiB -lt 10 -or $vmCleanCacheGiB -lt 10)) {
        throw 'Model tools need 4 GiB free host RAM or 10 GiB reusable Docker VM cache/headroom. Existing tasks were left untouched.'
    }
    # The standalone tools bypass the job queue. Refuse to overlap any owned compute attempt.
    $workerIds = & docker @composeArgs ps -q worker
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect worker.' }
    if ($workerIds) {
        $statusText = & docker @composeArgs exec -T worker python -m app.workers.admin status
        if ($LASTEXITCODE -ne 0) { throw 'Could not establish lane status; refusing standalone compute.' }
        $status = $statusText | ConvertFrom-Json
        if ($status.active_attempt_id -or $status.recovery_required -or $status.state -ne 'READY') {
            throw 'Compute lane is active or needs recovery; standalone tools were not started.'
        }
    }
    $modelIds = & docker ps -q --filter 'label=com.docker.compose.service=chronos'
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect standalone model containers.' }
    if ($modelIds) { throw 'A standalone Chronos task is already running; it was left untouched.' }
    $modelCommand = $Action.ToLowerInvariant()
    if ($Action -eq 'Session') {
        Invoke-Docker ($composeArgs + @('run', '--rm', '--no-deps', 'chronos', 'session', '--threads', '2', '--batch-size', '4'))
    } else {
        # Primary process and descendants stay in this one container. Bound offline exercises;
        # preparation downloads have their own 15-minute setup budget, outside job execution.
        $budget = if ($Action -eq 'Prepare') { '895s' } else { '295s' }
        $toolArgs = @('python', 'scripts/chronos_local.py', $modelCommand)
        if ($Action -ne 'Prepare') { $toolArgs += @('--threads', '2', '--batch-size', '4') }
        Invoke-Docker ($composeArgs + @('run', '--rm', '-T', '--no-deps', '--entrypoint', 'timeout', 'chronos', '--signal=TERM', '--kill-after=5s', $budget) + $toolArgs)
    }
} finally {
    Pop-Location
}
