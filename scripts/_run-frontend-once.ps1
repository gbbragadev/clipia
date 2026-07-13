param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$DistDir,
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$LogPath
)

$ErrorActionPreference = "Stop"
$frontendRoot = Join-Path $Root "frontend"
if ([System.IO.Path]::IsPathRooted($DistDir)) { throw "absolute NEXT_DIST_DIR rejected" }
$resolvedFrontend = [System.IO.Path]::GetFullPath($frontendRoot).TrimEnd('\')
$resolvedBuild = [System.IO.Path]::GetFullPath((Join-Path $frontendRoot $DistDir))
if (-not $resolvedBuild.StartsWith("$resolvedFrontend\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "NEXT_DIST_DIR escaped frontend root"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedBuild "BUILD_ID"))) {
    throw "BUILD_ID missing from $DistDir"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $LogPath) -Force | Out-Null
Set-Location $frontendRoot
$env:NEXT_DIST_DIR = $DistDir
& npm.cmd run start -- -p $Port *>&1 | Out-File -Append -Encoding utf8 $LogPath
exit $LASTEXITCODE
