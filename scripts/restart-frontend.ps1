# Build and promote the ClipIA frontend without overwriting the build in use.
#
# Rebuild flow:
#   1. Build a versioned NEXT_DIST_DIR while port 3003 keeps serving.
#   2. Start the candidate on port 3004 and smoke home/login/chunks/API/health.
#   3. Atomically update the active-build pointer, then restart port 3003.
#   4. Roll back to the preserved previous build if the production smoke fails.
#
# This is process-level blue/green only. A permanent reverse-proxy switch is a
# separate infrastructure change and is intentionally not implemented here.

[CmdletBinding()]
param(
    [switch]$Rebuild,
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [int]$ProductionPort = 3003,
    [int]$CandidatePort = 3004,
    [int]$StartupTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$frontendRoot = Join-Path $Root "frontend"
$storageRoot = Join-Path $Root "storage"
$releaseRoot = Join-Path $frontendRoot ".next-releases"
$activePointer = Join-Path $storageRoot "frontend-active-build.txt"
$productionLog = Join-Path $storageRoot "frontend.log"
$candidateLog = Join-Path $storageRoot "frontend-candidate.log"

function Resolve-BuildPath {
    param([Parameter(Mandatory = $true)][string]$DistDir)

    if ([System.IO.Path]::IsPathRooted($DistDir)) {
        throw "NEXT_DIST_DIR must be relative to frontend: $DistDir"
    }
    $resolvedFrontend = [System.IO.Path]::GetFullPath($frontendRoot).TrimEnd('\')
    $resolvedBuild = [System.IO.Path]::GetFullPath((Join-Path $frontendRoot $DistDir))
    if (-not $resolvedBuild.StartsWith("$resolvedFrontend\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Build path escaped frontend root: $DistDir"
    }
    return $resolvedBuild
}

function Get-ActiveBuild {
    $distDir = ".next"
    if (Test-Path -LiteralPath $activePointer) {
        $distDir = (Get-Content -LiteralPath $activePointer -Raw).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($distDir)) {
        throw "Active frontend build pointer is empty: $activePointer"
    }
    $buildPath = Resolve-BuildPath -DistDir $distDir
    if (-not (Test-Path -LiteralPath (Join-Path $buildPath "BUILD_ID"))) {
        throw "Active frontend build is incomplete: $distDir"
    }
    return $distDir
}

function Get-BuildId {
    param([Parameter(Mandatory = $true)][string]$DistDir)

    $buildPath = Resolve-BuildPath -DistDir $DistDir
    $buildIdPath = Join-Path $buildPath "BUILD_ID"
    if (-not (Test-Path -LiteralPath $buildIdPath)) {
        throw "Missing BUILD_ID in $DistDir"
    }
    return (Get-Content -LiteralPath $buildIdPath -Raw).Trim()
}

function Write-ActiveBuildPointer {
    param([Parameter(Mandatory = $true)][string]$DistDir)

    [void](Get-BuildId -DistDir $DistDir)
    New-Item -ItemType Directory -Path $storageRoot -Force | Out-Null
    $tempPointer = "$activePointer.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        # ASCII is intentional: release names are ASCII and Windows PowerShell
        # 5.1 does not support the newer utf8NoBOM encoding name.
        Set-Content -LiteralPath $tempPointer -Value $DistDir -Encoding ascii
        Move-Item -LiteralPath $tempPointer -Destination $activePointer -Force
    } finally {
        if (Test-Path -LiteralPath $tempPointer) {
            Remove-Item -LiteralPath $tempPointer -Force
        }
    }
}

function Stop-FrontendPort {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in @($connections)) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
        $commandLine = [string]$owner.CommandLine
        if ($commandLine -notlike "*$frontendRoot*" -or $commandLine -notmatch "(?i)(next|npm)") {
            throw "Refusing to stop unrelated PID $($connection.OwningProcess) on port $Port"
        }
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
    }
}

function Stop-FrontendLauncher {
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $PID -and
            $_.CommandLine -like "*_run-frontend.ps1*" -and
            $_.CommandLine -like "*$Root*"
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }
}

function Stop-FrontendProduction {
    Stop-FrontendLauncher
    Stop-FrontendPort -Port $ProductionPort
}

function Start-FrontendProcess {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$DistDir,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [switch]$Loop
    )

    [void](Get-BuildId -DistDir $DistDir)
    $launcher = if ($Loop) { "_run-frontend.ps1" } else { "_run-frontend-once.ps1" }
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$(Join-Path $PSScriptRoot $launcher)`"",
        "-Root", "`"$Root`""
    )
    if (-not $Loop) {
        $arguments += @("-DistDir", "`"$DistDir`"", "-Port", "$Port", "-LogPath", "`"$LogPath`"")
    }
    return Start-Process powershell.exe -WindowStyle Hidden -ArgumentList $arguments -PassThru
}

function Wait-FrontendPort {
    param([Parameter(Mandatory = $true)][int]$Port)

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "Frontend did not listen on port $Port within $StartupTimeoutSeconds seconds"
}

function Invoke-SmokeRequest {
    param([Parameter(Mandatory = $true)][string]$Url)

    return Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
}

function Test-FrontendSmoke {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$ExpectedBuildId
    )

    $baseUrl = "http://127.0.0.1:$Port"
    try {
        $home = Invoke-SmokeRequest -Url "$baseUrl/"
        $login = Invoke-SmokeRequest -Url "$baseUrl/auth/login"
        $health = Invoke-SmokeRequest -Url "$baseUrl/health"
        $packages = Invoke-SmokeRequest -Url "$baseUrl/api/v1/credits/packages"
        if (@($home.StatusCode, $login.StatusCode, $health.StatusCode, $packages.StatusCode) -contains 0) {
            return $false
        }
        if ($home.StatusCode -ne 200 -or $login.StatusCode -ne 200 -or $health.StatusCode -ne 200 -or $packages.StatusCode -ne 200) {
            return $false
        }

        $manifest = Invoke-SmokeRequest -Url "$baseUrl/_next/static/$ExpectedBuildId/_buildManifest.js"
        if ($manifest.StatusCode -ne 200 -or $manifest.Headers["Content-Type"] -notmatch "javascript") {
            return $false
        }

        $chunks = [regex]::Matches($login.Content, '/_next/static/chunks/[^"''\s]+\.js') |
            ForEach-Object { $_.Value } | Select-Object -Unique -First 20
        if (@($chunks).Count -eq 0) {
            return $false
        }
        foreach ($chunk in $chunks) {
            $response = Invoke-SmokeRequest -Url ($baseUrl + $chunk)
            if ($response.StatusCode -ne 200 -or $response.Headers["Content-Type"] -notmatch "javascript") {
                return $false
            }
        }
        return $true
    } catch {
        Write-Warning "Smoke failed on port ${Port}: $($_.Exception.Message)"
        return $false
    }
}

function Start-ProductionAndSmoke {
    param([Parameter(Mandatory = $true)][string]$DistDir)

    $buildId = Get-BuildId -DistDir $DistDir
    [void](Start-FrontendProcess -Port $ProductionPort -DistDir $DistDir -LogPath $productionLog -Loop)
    Wait-FrontendPort -Port $ProductionPort
    return Test-FrontendSmoke -Port $ProductionPort -ExpectedBuildId $buildId
}

New-Item -ItemType Directory -Path $storageRoot -Force | Out-Null

if (-not $Rebuild) {
    $activeDistDir = Get-ActiveBuild
    Stop-FrontendProduction
    if (-not (Start-ProductionAndSmoke -DistDir $activeDistDir)) {
        throw "Active frontend failed smoke after restart: $activeDistDir"
    }
    Write-Host "Frontend restarted successfully from $activeDistDir"
    exit 0
}

$previousDistDir = Get-ActiveBuild
$gitSha = (& git -C $Root rev-parse --short=12 HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitSha)) { $gitSha = "unknown" }
$releaseName = "$(Get-Date -Format 'yyyyMMdd-HHmmss')-$gitSha"
$candidateDistDir = ".next-releases/$releaseName"
$candidateBuildPath = Resolve-BuildPath -DistDir $candidateDistDir
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
if (Test-Path -LiteralPath $candidateBuildPath) {
    throw "Candidate build already exists: $candidateDistDir"
}

Write-Host "Building candidate $candidateDistDir while port $ProductionPort remains active..."
$previousNextDistDir = $env:NEXT_DIST_DIR
$tsconfigPath = Join-Path $frontendRoot "tsconfig.json"
$tsconfigBytes = [System.IO.File]::ReadAllBytes($tsconfigPath)
try {
    Push-Location $frontendRoot
    $env:NEXT_DIST_DIR=$candidateDistDir
    & npm.cmd run build
    $buildExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:NEXT_DIST_DIR = $previousNextDistDir
    # Next 16 appends each custom distDir to tsconfig.include. The build is
    # valid, but deployment must not dirty or continuously grow tracked source.
    [System.IO.File]::WriteAllBytes($tsconfigPath, $tsconfigBytes)
}
if ($buildExit -ne 0) {
    throw "Candidate build failed with exit $buildExit; active frontend was not touched"
}
$candidateBuildId = Get-BuildId -DistDir $candidateDistDir

$candidateProcess = $null
$cutoverStarted = $false
$promotionSucceeded = $false
try {
    # Candidate process uses -Port 3004 by default and never replaces 3003.
    $candidateProcess = Start-FrontendProcess -Port $CandidatePort -DistDir $candidateDistDir -LogPath $candidateLog
    Wait-FrontendPort -Port $CandidatePort
    if (-not (Test-FrontendSmoke -Port $CandidatePort -ExpectedBuildId $candidateBuildId)) {
        throw "Candidate smoke failed; active frontend was not touched"
    }

    # Stop only the watchdog first. The old node process keeps serving until the
    # pointer is durable, reducing the cutover window and preventing a restart race.
    $cutoverStarted = $true
    Stop-FrontendLauncher
    Write-ActiveBuildPointer -DistDir $candidateDistDir
    Stop-FrontendPort -Port $ProductionPort

    if (-not (Start-ProductionAndSmoke -DistDir $candidateDistDir)) {
        throw "Candidate failed production smoke"
    }

    $promotionSucceeded = $true
    Write-Host "Frontend promoted successfully: $candidateDistDir (BUILD_ID $candidateBuildId)"
    Write-Host "Previous build preserved for rollback: $previousDistDir"
} catch {
    $deployFailure = $_
    if ($cutoverStarted -and -not $promotionSucceeded) {
        Write-Warning "Promotion failed. Rollback to $previousDistDir"
        try {
            Stop-FrontendProduction
            Write-ActiveBuildPointer -DistDir $previousDistDir
            if (-not (Start-ProductionAndSmoke -DistDir $previousDistDir)) {
                throw "rollback smoke returned false"
            }
        } catch {
            throw "Deploy failed ($($deployFailure.Exception.Message)) and Rollback failed ($($_.Exception.Message)); inspect $productionLog immediately"
        }
        throw "Deploy failed and Rollback succeeded: $($deployFailure.Exception.Message)"
    }
    throw
} finally {
    Stop-FrontendPort -Port $CandidatePort
    if ($candidateProcess -and -not $candidateProcess.HasExited) {
        Stop-Process -Id $candidateProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
