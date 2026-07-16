param(
    [switch]$NoAlert
)

# Watchdog completo da producao local do ClipIA. Faz uma passada e sai; o
# Task Scheduler chama novamente a cada 2 minutos. Os launchers continuam sendo
# a fonte canonica dos processos e este script apenas os reergue quando necessario.
$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Dev\clipia"
. (Join-Path $PSScriptRoot "watchdog-production-core.ps1")
$logDir = Join-Path $root "storage"
$eventLog = Join-Path $logDir "production-watchdog.log"
$tunnelConfig = Join-Path $env:USERPROFILE ".cloudflared\clipia.yml"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

foreach ($key in @("CLIPIA_WPP_NUMBER", "CLIPIA_WPP_KEY", "CLIPIA_WPP_ENDPOINT", "TU_WPP_NUMBER", "TU_WPP_KEY", "TU_WPP_ENDPOINT")) {
    $value = [Environment]::GetEnvironmentVariable($key, "User")
    if ($value) { Set-Item -Path "env:$key" -Value $value }
}

$wppNumber = if ($env:CLIPIA_WPP_NUMBER) { $env:CLIPIA_WPP_NUMBER } else { $env:TU_WPP_NUMBER }
$wppKey = if ($env:CLIPIA_WPP_KEY) { $env:CLIPIA_WPP_KEY } else { $env:TU_WPP_KEY }
$wppEndpoint = if ($env:CLIPIA_WPP_ENDPOINT) { $env:CLIPIA_WPP_ENDPOINT } elseif ($env:TU_WPP_ENDPOINT) { $env:TU_WPP_ENDPOINT } else { "http://localhost:8081/message/sendText/grafana-alerts" }

function Get-Timestamp {
    return Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}

function Write-WatchdogLog([string]$Message) {
    if ((Test-Path -LiteralPath $eventLog) -and (Get-Item -LiteralPath $eventLog).Length -gt 10MB) {
        Move-Item -LiteralPath $eventLog -Destination "$eventLog.1" -Force
    }
    Add-Content -LiteralPath $eventLog -Value ("[{0}] {1}" -f (Get-Timestamp), $Message)
}

function Send-Alert([string]$Text) {
    if ($NoAlert -or -not $wppKey -or -not $wppNumber) {
        Write-WatchdogLog "ALERT-SKIP: $Text"
        return
    }

    try {
        $body = @{ number = $wppNumber; text = $Text } | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        Invoke-RestMethod -Uri $wppEndpoint -Method Post -Headers @{ apikey = $wppKey } `
            -ContentType "application/json" -Body $bytes -TimeoutSec 20 | Out-Null
    } catch {
        Write-WatchdogLog "ALERT-FAIL: $($_.Exception.Message)"
    }
}

function Test-Http([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10 `
            -Headers @{ "User-Agent" = "ClipIA-Watchdog/1.0" }
        return [int]$response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-DeepHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8005/health/deep" -UseBasicParsing -TimeoutSec 10
        return $response.Content | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Stop-MatchingProcesses([string[]]$Patterns) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
        $process = $_
        $matched = $false
        foreach ($pattern in $Patterns) {
            if ($process.CommandLine -like $pattern) { $matched = $true; break }
        }
        if ($matched -and $process.ProcessId -ne $PID) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-Launcher([string]$Name) {
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList `
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts\$Name")
}

function Restart-Backend {
    Stop-MatchingProcesses @("*_run-backend.ps1*", "*uvicorn app.main:app*--port 8005*")
    Stop-PortOwnerSafely -Port 8005 -Root $root
    Start-Sleep -Seconds 2
    Start-Launcher "_run-backend.ps1"
}

function Restart-Worker {
    Stop-MatchingProcesses @("*_run-worker.ps1*", "*celery*app.worker.celery_app*")
    Start-Sleep -Seconds 2
    Start-Launcher "_run-worker.ps1"
}

function Restart-Frontend {
    Stop-MatchingProcesses @("*_run-frontend.ps1*")
    Stop-PortOwnerSafely -Port 3003 -Root $root
    Start-Sleep -Seconds 2
    Start-Launcher "_run-frontend.ps1"
}

function Restart-Tunnel {
    Stop-MatchingProcesses @("*_run-tunnel.ps1*", "*cloudflared.exe*tunnel*clipia*")
    Start-Sleep -Seconds 2
    Start-Launcher "_run-tunnel.ps1"
}

function Ensure-Containers {
    & docker version --format "{{.Server.Version}}" *> $null
    if ($LASTEXITCODE -ne 0) {
        $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path -LiteralPath $dockerDesktop) {
            Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
            for ($attempt = 0; $attempt -lt 10; $attempt++) {
                Start-Sleep -Seconds 5
                & docker version --format "{{.Server.Version}}" *> $null
                if ($LASTEXITCODE -eq 0) { break }
            }
        }
    }

    if ($LASTEXITCODE -ne 0) { return $false }
    Push-Location $root
    try {
        & docker compose up postgres redis -d *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        Pop-Location
    }
}

function Test-TunnelConfig {
    if (-not (Test-Path -LiteralPath $tunnelConfig)) { return $false }
    $configText = Get-Content -LiteralPath $tunnelConfig -Raw
    return $configText -match "service:\s*http://(?:localhost|127\.0\.0\.1):3003(?:\s|$)"
}

$restarted = New-Object System.Collections.Generic.List[string]
$unresolved = New-Object System.Collections.Generic.List[string]

# Backend e dependencias. /health/deep e deliberadamente interpretado; HTTP 200
# sozinho nao prova banco, Redis ou Celery.
if (-not (Test-Http "http://127.0.0.1:8005/health")) {
    Restart-Backend
    $restarted.Add("backend :8005")
    Start-Sleep -Seconds 12
}

$deepHealth = Get-DeepHealth
if ($null -eq $deepHealth) {
    $deepHealth = Repair-NullDeepHealth `
        -EnsureContainers { Ensure-Containers } `
        -RestartBackend { Restart-Backend; [void]$restarted.Add("backend :8005") } `
        -WaitForBackend { Start-Sleep -Seconds 12 } `
        -GetDeepHealth { Get-DeepHealth }
    if ($null -ne $deepHealth) {
        $restarted.Add("Postgres/Redis")
    } else {
        $unresolved.Add("backend sem health profundo apos recuperar dependencias")
    }
}

if ($null -ne $deepHealth) {
    if ($deepHealth.checks.database.status -ne "up" -or $deepHealth.checks.redis.status -ne "up") {
        if (Ensure-Containers) {
            $restarted.Add("Postgres/Redis")
            Start-Sleep -Seconds 10
            $deepHealth = Get-DeepHealth
        } else {
            $unresolved.Add("Docker/Postgres/Redis indisponivel")
        }
    }

    if ($null -ne $deepHealth -and $deepHealth.checks.celery.status -ne "up") {
        Restart-Worker
        $restarted.Add("worker/beat")
        Start-Sleep -Seconds 10
        $deepHealth = Get-DeepHealth
    }

    if ($null -eq $deepHealth -or $deepHealth.checks.database.status -ne "up" -or $deepHealth.checks.redis.status -ne "up") {
        $unresolved.Add("dependencias do backend seguem degradadas")
    }
    if ($null -eq $deepHealth -or $deepHealth.checks.celery.status -ne "up") {
        $unresolved.Add("Celery segue indisponivel")
    }
    if ($null -eq $deepHealth -or $deepHealth.checks.storage.status -ne "up" -or $deepHealth.checks.storage.writable -ne $true) {
        $unresolved.Add("storage segue indisponivel ou somente leitura")
    }
}

# Frontend local e a origem do tunnel. Um 200 apenas na landing nao mascara a
# indisponibilidade do backend porque o health profundo foi validado acima.
$frontendHealthy = (Test-Http "http://127.0.0.1:3003/") -and (Test-FrontendActiveBuild -Root $root -ProbeBuild {
    param($BuildId)
    Test-Http "http://127.0.0.1:3003/_next/static/$BuildId/_buildManifest.js"
})
if (-not $frontendHealthy) {
    Restart-Frontend
    $restarted.Add("frontend :3003")
    Start-Sleep -Seconds 12
    $frontendHealthy = (Test-Http "http://127.0.0.1:3003/") -and (Test-FrontendActiveBuild -Root $root -ProbeBuild {
        param($BuildId)
        Test-Http "http://127.0.0.1:3003/_next/static/$BuildId/_buildManifest.js"
    })
    if (-not $frontendHealthy) {
        $unresolved.Add("frontend segue indisponivel")
    }
}

# Nao reciclar tunnel quando a origem local esta fora. Isso evita o flap que
# mascara falha de backend/frontend como se fosse Cloudflare.
if ($frontendHealthy) {
    if (-not (Test-TunnelConfig)) {
        $unresolved.Add("clipia.yml nao aponta para localhost:3003")
    } elseif (-not (Test-Http "https://clipia.com.br/")) {
        Restart-Tunnel
        $restarted.Add("tunnel clipia")
        Start-Sleep -Seconds 20
        if (-not (Test-Http "https://clipia.com.br/")) {
            $unresolved.Add("dominio publico segue indisponivel")
        }
    }
}

if ($restarted.Count -gt 0 -or $unresolved.Count -gt 0) {
    $summary = "ClipIA watchdog: reiniciei [{0}]; pendente [{1}]. {2}. Log: {3}" -f `
        ($restarted -join ", "), ($unresolved -join ", "), (Get-Timestamp), $eventLog
    Write-WatchdogLog $summary
    Send-Alert $summary
}

if ($unresolved.Count -gt 0) { exit 1 }
exit 0
