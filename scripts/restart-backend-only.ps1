# scripts/restart-backend-only.ps1
# Reinicia SOMENTE o backend (uvicorn 8005) com o venv312.
# Usar quando postgres/redis ja estao up e o start-production.ps1 trava no passo do Docker.
# Mata por PORTA (robusto) e sobe o _run-backend em background (le o .env, inclusive STRIPE_WEBHOOK_SECRET).
$ErrorActionPreference = 'Continue'

# 0. Mata qualquer start-production.ps1 travado (evita corrida que re-mataria o backend novo)
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*start-production.ps1*' } |
    ForEach-Object {
        Write-Host "Matando start-production travado PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# 1. Mata o backend antigo na 8005 (por porta = pega qualquer origem, inclusive Python global)
Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Matando backend antigo PID $($_.OwningProcess) (porta 8005)"
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 2

# 2. Sobe o backend novo (venv312, codigo atual + .env atual)
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'C:\Dev\clipia\scripts\_run-backend.ps1'
Write-Host "Backend novo lancado; aguardando /health..."
Start-Sleep -Seconds 12

# 3. Verifica
try {
    $r = Invoke-WebRequest 'http://127.0.0.1:8005/health' -UseBasicParsing -TimeoutSec 10
    Write-Host "OK backend /health = $($r.StatusCode) (start novo)"
} catch {
    Write-Host "FALHA backend /health: $($_.Exception.Message)"
}
