param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Continue"
$frontendRoot = Join-Path $Root "frontend"
$pointer = Join-Path $Root "storage\frontend-active-build.txt"
$logPath = Join-Path $Root "storage\frontend.log"
New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
Set-Location $frontendRoot

while ($true) {
    $activeDistDir = ".next"
    if (Test-Path -LiteralPath $pointer) {
        $activeDistDir = (Get-Content -LiteralPath $pointer -Raw).Trim()
    }

    try {
        if ([System.IO.Path]::IsPathRooted($activeDistDir)) { throw "absolute NEXT_DIST_DIR rejected" }
        $resolvedFrontend = [System.IO.Path]::GetFullPath($frontendRoot).TrimEnd('\')
        $resolvedBuild = [System.IO.Path]::GetFullPath((Join-Path $frontendRoot $activeDistDir))
        if (-not $resolvedBuild.StartsWith("$resolvedFrontend\", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "NEXT_DIST_DIR escaped frontend root"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $resolvedBuild "BUILD_ID"))) {
            throw "BUILD_ID missing from $activeDistDir"
        }

        $env:NEXT_DIST_DIR = $activeDistDir
        & npm.cmd run start -- -p 3003 *>&1 | Out-File -Append -Encoding utf8 $logPath
    } catch {
        Add-Content -Path $logPath -Value "$(Get-Date -Format o) Frontend launcher rejected build: $($_.Exception.Message)"
    }

    Add-Content -Path $logPath -Value "$(Get-Date -Format o) Frontend exited. Retrying pointer in 5s..."
    Start-Sleep -Seconds 5
}
