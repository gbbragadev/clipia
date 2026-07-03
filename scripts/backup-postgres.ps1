# scripts/backup-postgres.ps1
# Backup diario do Postgres ClipIA (local + offsite opcional para Cloudflare R2).
#
# O offsite e ativado quando as env vars R2_* estao definidas (escopo User).
# Sem elas, cai graciosamente no backup local apenas (retencao $KeepDays dias).
#
# O upload R2 (S3-compatible, SigV4) e feito por scripts/upload_r2.py (stdlib
# Python) — mais robusto que reimplementar SigV4 em PowerShell. Usa o venv
# .venv312 se existir, senao cai no python do PATH.
#
# Uso: .\scripts\backup-postgres.ps1 [-KeepDays 14]
param(
    [int]$KeepDays = 14
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $root "storage\backups"
$container = "clipia-postgres-1"
$date = Get-Date -Format "yyyy-MM-dd_HHmm"
$file = Join-Path $backupDir "clipia_$date.sql.gz"

# --- Credenciais R2 (opcionais): User-scope ---
# Lemos do User scope e PROPAGAMOS para o Process scope, para que o subprocesso
# Python (upload_r2.py) tambem enxergue as vars (cada processo novo herda so do
# pai imediato, e o scheduler/launcher pode nao ter User->Process automatico).
$script:R2_ACCOUNT_ID    = [System.Environment]::GetEnvironmentVariable("R2_ACCOUNT_ID", "User")
$script:R2_ACCESS_KEY_ID = [System.Environment]::GetEnvironmentVariable("R2_ACCESS_KEY_ID", "User")
$script:R2_SECRET_KEY    = [System.Environment]::GetEnvironmentVariable("R2_SECRET_ACCESS_KEY", "User")
$script:R2_BUCKET        = [System.Environment]::GetEnvironmentVariable("R2_BUCKET", "User")
foreach ($kv in @{
        R2_ACCOUNT_ID    = $script:R2_ACCOUNT_ID
        R2_ACCESS_KEY_ID = $script:R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY = $script:R2_SECRET_KEY
        R2_BUCKET        = $script:R2_BUCKET
    }.GetEnumerator()) {
    if ($kv.Value) {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Process")
    }
}

function Test-R2Configured {
    return (-not [string]::IsNullOrWhiteSpace($script:R2_ACCESS_KEY_ID)) -and `
           (-not [string]::IsNullOrWhiteSpace($script:R2_SECRET_KEY)) -and `
           (-not [string]::IsNullOrWhiteSpace($script:R2_BUCKET))
}

# --- Inicio ---
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "[$(Get-Date -Format o)] Starting ClipIA Postgres backup..."

# pg_dumpall via docker exec, dump para temp
$tempDumpFile = Join-Path $env:TEMP "clipia_dump_$([guid]::NewGuid()).sql"

docker exec $container pg_dumpall -U clipia > $tempDumpFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[$(Get-Date -Format o)] pg_dumpall falhou (exit $LASTEXITCODE)" -ForegroundColor Red
    Remove-Item $tempDumpFile -Force -ErrorAction SilentlyContinue
    exit 1
}

# Gzip
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
    $size = [math]::Round($sizeBytes / 1KB, 1); $unit = "KB"
} else {
    $size = [math]::Round($sizeBytes / 1MB, 2); $unit = "MB"
}
Write-Host "[$(Get-Date -Format o)] Backup local: $file ($size $unit)"

# --- Offsite para R2 (se configurado) via upload_r2.py ---
if (Test-R2Configured) {
    $objectKey = "backups/$(Split-Path -Leaf $file)"
    # Preferir o venv .venv312 (mesmo do app); fallback python do PATH.
    $venvPy = Join-Path $root ".venv312\Scripts\python.exe"
    if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }
    $uploader = Join-Path $PSScriptRoot "upload_r2.py"
    try {
        & $py $uploader $file $objectKey 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[$(Get-Date -Format o)] Offsite OK: R2 $($script:R2_BUCKET)/$objectKey" -ForegroundColor Green
        } else {
            throw "upload_r2.py exit $LASTEXITCODE"
        }
    } catch {
        Write-Host "[$(Get-Date -Format o)] Offsite R2 FALHOU: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "    Backup local preservado em $file" -ForegroundColor Yellow
    }
} else {
    Write-Host "[$(Get-Date -Format o)] R2 nao configurado (R2_* ausentes) — apenas backup local." -ForegroundColor DarkGray
    Write-Host "    Para offsite: defina R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (User scope)." -ForegroundColor DarkGray
}

# Limpar antigos (local)
$oldBackups = Get-ChildItem -Path $backupDir -Filter "clipia_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) }
foreach ($b in $oldBackups) {
    Write-Host "[$(Get-Date -Format o)] Removendo backup local antigo: $($b.Name)"
    Remove-Item $b.FullName
}

exit 0
