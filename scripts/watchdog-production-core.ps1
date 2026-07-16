# Pure/testable behavior shared by the Windows production watchdog. This file
# defines functions only; dot-sourcing it never touches services or processes.

function Test-DeepHealthPayload {
    param([AllowNull()]$Health)

    if ($null -eq $Health -or $null -eq $Health.checks) { return $false }
    return (
        $Health.status -eq "healthy" -and
        $Health.checks.database.status -eq "up" -and
        $Health.checks.redis.status -eq "up" -and
        $Health.checks.celery.status -eq "up" -and
        $Health.checks.storage.status -eq "up" -and
        $Health.checks.storage.writable -eq $true
    )
}

function Repair-NullDeepHealth {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$EnsureContainers,
        [Parameter(Mandatory = $true)][scriptblock]$RestartBackend,
        [Parameter(Mandatory = $true)][scriptblock]$GetDeepHealth,
        [Parameter(Mandatory = $true)][scriptblock]$WaitForBackend
    )

    $containersReady = & $EnsureContainers
    if (-not $containersReady) { return $null }
    $null = & $RestartBackend
    $null = & $WaitForBackend
    return (& $GetDeepHealth)
}

function Test-FrontendActiveBuild {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][scriptblock]$ProbeBuild
    )

    $frontendRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "frontend")).TrimEnd('\')
    $pointer = Join-Path $Root "storage\frontend-active-build.txt"
    if (-not (Test-Path -LiteralPath $pointer)) { return $false }

    $distDir = (Get-Content -LiteralPath $pointer -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($distDir) -or [System.IO.Path]::IsPathRooted($distDir)) {
        return $false
    }

    $buildPath = [System.IO.Path]::GetFullPath((Join-Path $frontendRoot $distDir))
    if (-not $buildPath.StartsWith("$frontendRoot\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }

    $buildIdPath = Join-Path $buildPath "BUILD_ID"
    if (-not (Test-Path -LiteralPath $buildIdPath)) { return $false }
    $buildId = (Get-Content -LiteralPath $buildIdPath -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($buildId)) { return $false }
    return [bool](& $ProbeBuild $buildId)
}

function Test-ClipiaPortOwner {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $commandLine = [string]$Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine) -or
        $commandLine.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }

    switch ($Port) {
        8005 { return $commandLine -match '(?i)(_run-backend\.ps1|uvicorn.+app\.main:app.+--port\s+8005)' }
        3003 { return $commandLine -match '(?i)(_run-frontend\.ps1|(?:next|npm)(?:\.cmd)?(?:\s|\.exe))' }
        default { return $false }
    }
}

function Stop-PortOwnerSafely {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Root,
        [scriptblock]$GetConnections = {
            param($TargetPort)
            @(Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue)
        },
        [scriptblock]$GetProcessById = {
            param($TargetProcessId)
            Get-CimInstance Win32_Process -Filter "ProcessId=$TargetProcessId" -ErrorAction SilentlyContinue
        },
        [scriptblock]$StopProcess = {
            param($TargetProcessId)
            Stop-Process -Id $TargetProcessId -Force -ErrorAction Stop
        }
    )

    foreach ($connection in @(& $GetConnections $Port)) {
        $owner = & $GetProcessById $connection.OwningProcess
        if (-not (Test-ClipiaPortOwner -Process $owner -Port $Port -Root $Root)) {
            throw "Refusing to stop unrelated PID $($connection.OwningProcess) on port $Port"
        }
        & $StopProcess $connection.OwningProcess
    }
}
