# Exercise the real helper with deterministic command doubles. No Docker daemon,
# process shutdown, model download, credentials or host configuration is involved.
$ErrorActionPreference = 'Stop'
$helper = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'compute-windows.ps1'
$global:TestCalls = New-Object 'System.Collections.Generic.List[string]'

function global:Get-CimInstance { [pscustomobject]@{ FreePhysicalMemory = $global:TestHostGiB * 1MB } }
function global:Get-Item { [pscustomobject]@{ PSDrive = [pscustomobject]@{ Free = 100GB } } }
function global:docker {
    $call = $args -join ' '
    $global:TestCalls.Add($call)
    $global:LASTEXITCODE = 0
    switch -Regex ($call) {
        '^info ' { 'Docker: linux, 16 CPUs, 17179869184 bytes RAM'; return }
        ' ps -q worker api postgres$' { 'worker-fixture'; return }
        '^exec worker-fixture cat /proc/meminfo$' {
            "MemAvailable: $($global:TestVmGiB * 1MB) kB"
            "Cached: $($global:TestCacheGiB * 1MB) kB"
            'Shmem: 0 kB'; 'Dirty: 0 kB'; 'Writeback: 0 kB'
            return
        }
        ' ps -q worker$' { 'worker-fixture'; return }
        ' exec -T worker python -m app.workers.admin status$' {
            @{ state = 'READY'; active_attempt_id = $global:TestActive; recovery_required = $global:TestRecovery } | ConvertTo-Json -Compress
            return
        }
        '^ps -q --filter ' { if ($global:TestModelRunning) { 'existing-model' }; return }
        '^buildx ls ' { 'pantrypulse-compute-build'; return }
        '^buildx inspect [^ ]+$' { "Driver: $global:TestBuilderDriver"; return }
        '^inspect buildx_buildkit_' { $global:TestBuilderLimits | ConvertTo-Json -Compress; return }
        '^history ' { '1000000000'; return }
        ' run ' { $global:LASTEXITCODE = $global:TestRunExit; return }
    }
}

function Reset-Case {
    $global:TestCalls.Clear()
    $global:TestHostGiB = 5
    $global:TestVmGiB = 12
    $global:TestCacheGiB = 11
    $global:TestActive = $null
    $global:TestRecovery = $false
    $global:TestModelRunning = $false
    $global:TestRunExit = 0
    $global:TestBuilderDriver = 'docker-container'
    $global:TestBuilderLimits = @{ quota = 200000; period = 100000; memory = 3GB; swap = 3GB }
}
function Assert-True($condition, $message) { if (-not $condition) { throw $message } }
function Invoke-Case($action, $expectedError) {
    $failure = $null
    try { & $helper $action | Out-Null } catch { $failure = $_.Exception.Message }
    if ($expectedError) {
        Assert-True ($failure -match $expectedError) "Expected '$expectedError', received '$failure'."
        Assert-True (-not ($global:TestCalls -match ' buildx build |^buildx build | run ')) 'A refused command launched expensive work.'
    } else { Assert-True (-not $failure) "Unexpected failure: $failure" }
    Assert-True (-not ($global:TestCalls -match '(^| )(stop|kill|down|rm|prune|update|restart)( |$)')) 'Helper attempted to disrupt an existing task.'
}

Reset-Case
Invoke-Case Status $null
Assert-True (-not ($global:TestCalls -match ' up | run |^buildx ')) 'Status changed runtime state.'

Reset-Case
$global:TestHostGiB = 1; $global:TestVmGiB = 2; $global:TestCacheGiB = 1
Invoke-Case Smoke 'need 4 GiB'

Reset-Case
$global:TestActive = 'existing-attempt'
Invoke-Case Smoke 'lane is active'

Reset-Case
$global:TestRecovery = $true
Invoke-Case Prepare 'lane is active'

Reset-Case
$global:TestModelRunning = $true
Invoke-Case Smoke 'already running'

Reset-Case
$global:TestHostGiB = 1
Invoke-Case Benchmark $null
Assert-True ([bool]($global:TestCalls -match ' run .*--entrypoint timeout .*--kill-after=5s 295s .*benchmark --threads 2 --batch-size 4')) 'Benchmark lost its execution boundary/budget.'

Reset-Case
$global:TestRunExit = 124
$failure = $null
try { & $helper Smoke | Out-Null } catch { $failure = $_.Exception.Message }
Assert-True ($failure -match 'Docker command failed') 'Model timeout was reported as success.'
Assert-True (@($global:TestCalls -match ' run ').Count -eq 1) 'Timed-out model work was retried automatically.'

Reset-Case
Invoke-Case Start $null
Assert-True ([bool]($global:TestCalls -match ' up .*--no-recreate --no-build')) 'Start can replace a running service.'

Reset-Case
$global:TestBuilderLimits.memory = 0
Invoke-Case Build 'builder exceeds'

Reset-Case
$global:TestBuilderDriver = 'docker'
Invoke-Case Build 'resource boundary'

Reset-Case
Invoke-Case Build $null
Assert-True ([bool]($global:TestCalls -match '^buildx build .*--output type=docker,dest=')) 'Build stopped using disk-backed image export.'
Assert-True (-not ($global:TestCalls -match '^buildx build .*--load')) 'Windows build can buffer the full image in RAM.'

Write-Output '11 compute guard cases passed'
