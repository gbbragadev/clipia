# Instala o watchdog completo do ClipIA no Task Scheduler do usuario atual.
# Nao requer admin porque a producao depende da sessao do usuario (Docker Desktop
# e variaveis de ambiente User-scope).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$taskName = "ClipIA Production Watchdog"
$legacyTaskName = "ClipIA Tunnel Watchdog"
$watchdog = Join-Path $root "scripts\watchdog-production.ps1"

if (-not (Test-Path -LiteralPath $watchdog)) {
    throw "Watchdog nao encontrado: $watchdog"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
    "-NoProfile -ExecutionPolicy Bypass -File `"$watchdog`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

# O watchdog novo inclui tunnel e origem. Manter os dois causaria reciclagens
# concorrentes e alertas duplicados.
if (Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName $legacyTaskName | Out-Null
}

Start-ScheduledTask -TaskName $taskName
Write-Host "$taskName instalado (passada a cada 2 minutos)."
