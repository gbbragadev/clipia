# scripts/watchdog-tunnel.ps1
# Self-healing do tunel cloudflared do clipia. Incidente 11/07/2026: o loop
# _run-tunnel.ps1 foi morto junto com o cloudflared (kill externo da arvore,
# sem passar pelo respawn) e o site ficou 530 via dominio por horas sem ninguem
# saber -a origem local seguia 200. Este script roda agendado (schtask
# "ClipIA Tunnel Watchdog", a cada 5 min) e recicla o tunel quando detecta
# exatamente esse estado: dominio fora + origem local OK.
$root = 'C:\Dev\clipia'
$log = "$root\storage\tunnel-watchdog.log"
function Log([string]$m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Out-File -Append -Encoding utf8 $log }

function Test-Url([string]$url) {
    try {
        # UA proprio: o Bot Fight Mode do Cloudflare bloqueia UAs genericos de script
        $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 15 -Headers @{ 'User-Agent' = 'ClipIA-Readiness/1.0' }
        return $r.StatusCode -eq 200
    } catch { return $false }
}

# 2 tentativas espacadas: nao reciclar por blip de rede
if (Test-Url 'https://clipia.com.br/') { exit 0 }
Start-Sleep -Seconds 20
if (Test-Url 'https://clipia.com.br/') { exit 0 }

if (-not (Test-Url 'http://127.0.0.1:3003/')) {
    Log 'dominio E origem local fora -problema nao e o tunel; start-production cuida no logon'
    exit 1
}

Log 'dominio fora com origem local OK -reciclando o tunel clipia'
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*_run-tunnel.ps1*') -or
    ($_.Name -eq 'cloudflared.exe' -and $_.CommandLine -like '*clipia.yml*')
} | ForEach-Object {
    Log "matando PID $($_.ProcessId) ($($_.Name))"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3
# relanca o launcher oficial (tem loop de respawn e loga em storage\clipia-tunnel.log)
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\_run-tunnel.ps1"
Start-Sleep -Seconds 20
if (Test-Url 'https://clipia.com.br/') {
    Log 'tunel reciclado com sucesso -dominio 200'
} else {
    Log 'ALERTA: dominio segue fora apos reciclar o tunel -investigar (cloudflared edge? DNS?)'
}
