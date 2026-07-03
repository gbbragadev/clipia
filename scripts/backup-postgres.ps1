# scripts/backup-postgres.ps1
# Backup diario do Postgres ClipIA (local + offsite opcional para Cloudflare R2).
#
# O offsite e ativado quando as env vars R2_* estao definidas (escopo User ou .env).
# Sem elas, cai graciosamente no backup local apenas (retencao $KeepDays dias).
#
# R2 (S3-compatible): o upload usa a API S3 nativa do R2 via aws-sigv4 sem
# dependencias — implementado em puro PowerShell/.NET. Nada a instalar.
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

# --- Credenciais R2 (opcionais): User-scope primeiro, depois .env ---
$script:R2_ACCOUNT_ID    = [System.Environment]::GetEnvironmentVariable("R2_ACCOUNT_ID", "User")
$script:R2_ACCESS_KEY_ID = [System.Environment]::GetEnvironmentVariable("R2_ACCESS_KEY_ID", "User")
$script:R2_SECRET_KEY    = [System.Environment]::GetEnvironmentVariable("R2_SECRET_ACCESS_KEY", "User")
$script:R2_BUCKET        = [System.Environment]::GetEnvironmentVariable("R2_BUCKET", "User")
$script:R2_ENDPOINT      = $null
if ($script:R2_ACCOUNT_ID -and $script:R2_ACCOUNT_ID -ne "") {
    $script:R2_ENDPOINT = "https://$($script:R2_ACCOUNT_ID).r2.cloudflarestorage.com"
}

function Test-R2Configured {
    return (-not [string]::IsNullOrWhiteSpace($script:R2_ACCESS_KEY_ID)) -and `
           (-not [string]::IsNullOrWhiteSpace($script:R2_SECRET_KEY)) -and `
           (-not [string]::IsNullOrWhiteSpace($script:R2_BUCKET)) -and `
           ($null -ne $script:R2_ENDPOINT)
}

# --- SigV4 minimal (HMAC-SHA256) para S3/R2 PUT de objeto ---
# Referencia: docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
function Get-HmacSha256Hex([byte[]]$keyBytes, [string]$data) {
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $keyBytes
    $hash = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($data))
    return [BitConverter]::ToString($hash).Replace("-", "").ToLower()
}

function Get-HmacSha256Bytes([byte[]]$keyBytes, [string]$data) {
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $keyBytes
    return $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($data))
}

function Get-Sha256HexBytes([byte[]]$bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLower()
    } finally { $sha.Dispose() }
}

function Upload-ToR2([string]$filePath, [string]$objectKey) {
    $region = "auto"
    $service = "s3"
    $now = [DateTime]::UtcNow
    $amzDate = $now.ToString("yyyyMMddTHHmmssZ")
    $dateStamp = $now.ToString("yyyyMMdd")

    $host_ = "$($script:R2_ENDPOINT -replace '^https://','')"
    $endpoint = "$($script:R2_ENDPOINT)/$($script:R2_BUCKET)/$objectKey"

    $bytes = [System.IO.File]::ReadAllBytes($filePath)
    $payloadHash = Get-Sha256HexBytes $bytes

    # Canonical request
    $canonicalHeaders = "host:$host_`nx-amz-content-sha256:$payloadHash`nx-amz-date:$amzDate`n"
    $signedHeaders = "host;x-amz-content-sha256;x-amz-date"
    $canonical = "PUT`n/$objectKey`n`n$canonicalHeaders`n$signedHeaders`n$payloadHash"

    # String to sign
    $scope = "$dateStamp/$region/$service/aws4_request"
    $kDate = Get-HmacSha256Bytes ([System.Text.Encoding]::UTF8.GetBytes("AWS4" + $script:R2_SECRET_KEY)) $dateStamp
    $kRegion = Get-HmacSha256Bytes $kDate $region
    $kService = Get-HmacSha256Bytes $kRegion $service
    $kSigning = Get-HmacSha256Bytes $kService "aws4_request"

    $stringToSign = "AWS4-HMAC-SHA256`n$amzDate`n$scope`n$(Get-Sha256HexBytes ([System.Text.Encoding]::UTF8.GetBytes($canonical)))"
    $signature = Get-HmacSha256Hex $kSigning $stringToSign

    $auth = "AWS4-HMAC-SHA256 Credential=$($script:R2_ACCESS_KEY_ID)/$scope, SignedHeaders=$signedHeaders, Signature=$signature"

    $resp = Invoke-WebRequest -Method PUT -Uri $endpoint `
        -Headers @{ "Authorization" = $auth; "x-amz-content-sha256" = $payloadHash; "x-amz-date" = $amzDate } `
        -Body $bytes -UseBasicParsing -ErrorAction Stop
    return $resp.StatusCode
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

# --- Offsite para R2 (se configurado) ---
if (Test-R2Configured) {
    $objectKey = "backups/$(Split-Path -Leaf $file)"
    try {
        $code = Upload-ToR2 $file $objectKey
        Write-Host "[$(Get-Date -Format o)] Offsite OK: R2 $($script:R2_BUCKET)/$objectKey (HTTP $code)" -ForegroundColor Green
    } catch {
        Write-Host "[$(Get-Date -Format o)] Offsite R2 FALHOU: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "    Backup local preservado em $file" -ForegroundColor Yellow
    }
} else {
    Write-Host "[$(Get-Date -Format o)] R2 nao configurado (R2_* ausentes) — apenas backup local." -ForegroundColor DarkGray
    Write-Host "    Para offsite: defina R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (User scope)." -ForegroundColor DarkGray
}

# Limpar antigos (local) — foreach statement (PS 5.1 nao confunde $_ em string aqui)
$oldBackups = Get-ChildItem -Path $backupDir -Filter "clipia_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) }
foreach ($b in $oldBackups) {
    Write-Host "[$(Get-Date -Format o)] Removendo backup local antigo: $($b.Name)"
    Remove-Item $b.FullName
}

exit 0
