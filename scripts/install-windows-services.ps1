# scripts/install-windows-services.ps1
# Instala 3 servicos NSSM: clipia-backend, clipia-worker, clipia-frontend.
# Requer admin. Uso: .\scripts\install-windows-services.ps1

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv312\Scripts\python.exe"
$npmCmd = (Get-Command npm).Source
$logDir = Join-Path $root "storage\service-logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Install-ClipiaService {
    param(
        [string]$Name,
        [string]$Exe,
        [string]$Arguments,
        [string]$WorkDir
    )
    # Idempotente: remove se existe
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "Removendo service existente: $Name"
        nssm stop $Name 2>$null
        nssm remove $Name confirm
    }
    Write-Host "Instalando: $Name"
    nssm install $Name $Exe $Arguments
    nssm set $Name AppDirectory $WorkDir
    nssm set $Name AppStdout "$logDir\$Name.out.log"
    nssm set $Name AppStderr "$logDir\$Name.err.log"
    nssm set $Name AppRotateFiles 1
    nssm set $Name AppRotateBytes 10485760
    nssm set $Name Start SERVICE_AUTO_START
    nssm set $Name AppEnvironmentExtra "PYTHONUNBUFFERED=1" "ENVIRONMENT=production"
}

Install-ClipiaService `
    -Name "clipia-backend" `
    -Exe "$pythonExe" `
    -Arguments "-m uvicorn app.main:app --host 127.0.0.1 --port 8005" `
    -WorkDir $root

Install-ClipiaService `
    -Name "clipia-worker" `
    -Exe "$pythonExe" `
    -Arguments "-m celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo" `
    -WorkDir $root

Install-ClipiaService `
    -Name "clipia-frontend" `
    -Exe "$npmCmd" `
    -Arguments "run start -- -p 3003" `
    -WorkDir (Join-Path $root "frontend")

Write-Host ""
Write-Host "Services instalados (ainda NAO iniciados). Para iniciar:" -ForegroundColor Green
Write-Host "  Start-Service clipia-backend,clipia-worker,clipia-frontend"
Write-Host ""
Write-Host "IMPORTANTE: Antes de iniciar o frontend:"
Write-Host "  cd frontend; npm run build"
