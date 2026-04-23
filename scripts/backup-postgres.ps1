# scripts/backup-postgres.ps1
# Backup diario do Postgres ClipIA.
# Uso: .\scripts\backup-postgres.ps1 [-KeepDays 14]
param(
    [int]$KeepDays = 14
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $root "storage\backups"
$container = "auto-shorts-postgres-1"
$date = Get-Date -Format "yyyy-MM-dd_HHmm"
$file = Join-Path $backupDir "clipia_$date.sql.gz"

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "[$(Get-Date -Format o)] Starting ClipIA Postgres backup..."

# pg_dumpall via docker exec, pipe direto para gzip
$tempDumpFile = Join-Path $env:TEMP "clipia_dump_$([guid]::NewGuid()).sql"

docker exec $container pg_dumpall -U clipia > $tempDumpFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "pg_dumpall falhou (exit $LASTEXITCODE)" -ForegroundColor Red
    Remove-Item $tempDumpFile -Force -ErrorAction SilentlyContinue
    exit 1
}

# Gzip the dump
$outStream = [System.IO.File]::Create($file)
$gzip = New-Object System.IO.Compression.GzipStream($outStream, [System.IO.Compression.CompressionMode]::Compress)
$fileStream = [System.IO.File]::OpenRead($tempDumpFile)
$fileStream.CopyTo($gzip)
$fileStream.Close()
$gzip.Close()
$outStream.Close()

Remove-Item $tempDumpFile -Force

$sizeBytes = (Get-Item $file).Length
if ($sizeBytes -lt 1MB) {
    $size = [math]::Round($sizeBytes / 1KB, 1)
    $unit = "KB"
} else {
    $size = [math]::Round($sizeBytes / 1MB, 2)
    $unit = "MB"
}
Write-Host "[$(Get-Date -Format o)] Backup concluido: $file ($size $unit)"

# Limpar antigos
Get-ChildItem -Path $backupDir -Filter "clipia_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
    ForEach-Object {
        Write-Host "Removendo backup antigo: $($_.Name)"
        Remove-Item $_.FullName
    }

exit 0
