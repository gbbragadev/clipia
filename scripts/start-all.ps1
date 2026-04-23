# scripts/start-all.ps1
# Orquestra stack dev do ClipIA no Windows.
# Uso: .\scripts\start-all.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "[1/5] Validando env vars..." -ForegroundColor Cyan
& "$PSScriptRoot\check-env.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Env vars faltando. Abortando." -ForegroundColor Red
    exit 1
}

Write-Host "[2/5] Subindo Postgres + Redis..." -ForegroundColor Cyan
Push-Location $root
docker compose up postgres redis -d
$pgHealthy = $false
for ($i = 0; $i -lt 20; $i++) {
    $status = docker compose ps --format json | ConvertFrom-Json
    $pg = $status | Where-Object { $_.Service -eq "postgres" }
    if ($pg -and $pg.Health -eq "healthy") { $pgHealthy = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $pgHealthy) {
    Write-Host "Postgres nao ficou healthy em 40s." -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[3/5] Aplicando migrations..." -ForegroundColor Cyan
& "$root\.venv312\Scripts\python.exe" -m alembic upgrade head

Write-Host "[4/5] Abrindo 3 terminais (backend, worker, frontend)..." -ForegroundColor Cyan

$backendCmd = "cd '$root'; .\.venv312\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8005"
$workerCmd  = "cd '$root'; .\.venv312\Scripts\Activate.ps1; celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo"
$frontCmd   = "cd '$root\frontend'; npm run dev -- -p 3003"

Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit","-Command",$workerCmd
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontCmd

Pop-Location

Write-Host ""
Write-Host "[5/5] Stack subindo." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8005/docs"
Write-Host "  Frontend: http://localhost:3003"
Write-Host "  Admin:    ver .admin-credentials.local"
Write-Host ""
Write-Host "Para subir o tunnel Cloudflare: cloudflared tunnel run clipia-windows"
