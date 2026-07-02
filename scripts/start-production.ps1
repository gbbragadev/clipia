# scripts/start-production.ps1
# Orquestrador de producao do ClipIA (idempotente).
# Chamado pela scheduled task "ClipIA Production" no logon do usuario,
# ou manualmente: powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1
#
# Sobe: postgres+redis (Docker) -> backend (8005) -> worker (celery solo)
#       -> frontend producao (3003) -> Cloudflare Tunnel 'clipia'.
# Roda no contexto do usuario (env vars User-scope das API keys funcionam).

$ErrorActionPreference = 'Continue'
$root = 'C:\Dev\clipia'
$logDir = "$root\storage"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$bootLog = "$logDir\start-production.log"

function Log([string]$msg) {
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    $line | Out-File -Append -Encoding utf8 $bootLog
    Write-Host $line
}

Log "=== start-production: inicio ==="

# 1. Esperar Docker engine (Docker Desktop pode demorar apos logon)
$dockerOk = $false
for ($i = 0; $i -lt 60; $i++) {
    docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $dockerOk) { Log "ERRO: Docker engine nao respondeu em 5min. Abortando."; exit 1 }
Log "Docker engine OK"

# 2. Postgres + Redis
Set-Location $root
docker compose up postgres redis -d *> $null
$pgHealthy = $false
for ($i = 0; $i -lt 30; $i++) {
    $state = docker inspect --format '{{.State.Health.Status}}' clipia-postgres-1 2>$null
    if ($state -eq 'healthy') { $pgHealthy = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $pgHealthy) { Log "ERRO: postgres nao ficou healthy em 60s. Abortando."; exit 1 }
Log "Postgres healthy, Redis up"

# 3. Matar instancias antigas (somente as do ClipIA)
$old = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe'      -and ($_.CommandLine -like '*uvicorn app.main:app*' -or $_.CommandLine -like '*celery*app.worker*')) -or
    ($_.Name -eq 'cloudflared.exe' -and  $_.CommandLine -like '*clipia.yml*')
}
foreach ($p in $old) {
    Log "Matando processo antigo PID $($p.ProcessId) ($($p.Name))"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
$port3003 = Get-NetTCPConnection -LocalPort 3003 -State Listen -ErrorAction SilentlyContinue
if ($port3003) {
    Log "Matando frontend antigo PID $($port3003[0].OwningProcess) (porta 3003)"
    Stop-Process -Id $port3003[0].OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# 4. Subir os 4 processos (hidden; cada launcher copia env User->Process e loga em storage\)
$launchers = @('_run-backend.ps1', '_run-worker.ps1', '_run-frontend.ps1', '_run-tunnel.ps1')
foreach ($l in $launchers) {
    # -NoProfile: evita que hooks de shell (ex. lean-ctx) interceptem args dos launchers (quebrava `-p 3003`)
    Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\$l"
    Log "Lancado: $l"
    Start-Sleep -Seconds 2
}

function Test-Endpoint($url, $timeout) {
    for ($i = 1; $i -le 3; $i++) {
        try { if ((Invoke-WebRequest $url -UseBasicParsing -TimeoutSec $timeout).StatusCode -eq 200) { return $true } } catch {}
        if ($i -lt 3) { Start-Sleep -Seconds 10 }
    }
    return $false
}
# 5. Verificacao
Start-Sleep -Seconds 15
$backendOk = $false
$backendOk = Test-Endpoint 'http://127.0.0.1:8005/health' 10
$frontOk = $false
$frontOk = Test-Endpoint 'http://localhost:3003' 15
if (-not $backendOk -or -not $frontOk) { Log "ALERTA: verificacao falhou apos 3 tentativas. Cheque storage\backend.log e storage\frontend.log." }
Log "Verificacao: backend=$backendOk frontend=$frontOk"
Log "=== start-production: fim ==="
