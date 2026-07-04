# scripts/restart-frontend.ps1
#
# Reinicia SOMENTE o frontend Next.js (porta 3003) do ClipIA.
#
# Causa raiz que este script resolve: quando se roda `npm run build` enquanto um
# `next start` ja esta em pe, o processo em memoria mantem o manifest do build
# ANTIGO, mas os arquivos em .next/static sao do build NOVO. Resultado: HTML novo
# referencia chunks que sumiram do disco -> HTTP 500 "text/plain" em .js -> o
# browser recusa executar (MIME type errado) -> JS morto -> login/dashboard/register
# nao funcionam (sintoma: "nao consigo entrar no dashboard").
#
# Como usar (a partir da raiz do repo, com a maquina de producao logada com rede):
#   powershell -ExecutionPolicy Bypass -File scripts\restart-frontend.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\restart-frontend.ps1 -Rebuild
#     (-Rebuild roda `npm run build` antes do restart; use apos mudar codigo TS/TSX)
#
# O script:
#   0. Mata qualquer start-production.ps1 travado (evita corrida que mataria o novo)
#   1. Mata o next start antigo na porta 3003 (pega qualquer origem)
#   2. (Opcional, com -Rebuild) roda npm run build de forma atomica
#   3. Sobe o _run-frontend.ps1 em background
#   4. Valida que a home e os chunks estao servindo 200
#
# Importante: rodar fora de um agente sandbox, no logon com rede, para que o
# processo filho herde saida para a internet (Cloudflare Tunnel, etc).

param(
    [switch]$Rebuild
)

$ErrorActionPreference = 'Continue'
$root = 'C:\Dev\clipia'

# 0. Mata qualquer start-production.ps1 travado (evita corrida)
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*start-production.ps1*' } |
    ForEach-Object {
        Write-Host "Matando start-production travado PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# 1. Mata o frontend antigo na porta 3003 (por porta = pega qualquer next start/npm)
Get-NetTCPConnection -LocalPort 3003 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $pidToKill = $_.OwningProcess
        Write-Host "Matando frontend antigo PID $pidToKill (porta 3003)"
        # Mata tambem a arvore de filhos (npm -> node) para nao deixar orfaos
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 2

# 1b. Mata qualquer _run-frontend.ps1 que ainda esteja vivo (ele reinicia em loop)
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*_run-frontend.ps1*' } |
    ForEach-Object {
        Write-Host "Matando loop _run-frontend travado PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 1

# 2. Rebuild atomico (opcional): so feito com o processo parado, evita o bug raiz.
if ($Rebuild) {
    Write-Host "Rebuilding frontend (npm run build)..."
    Push-Location "$root\frontend"
    & npm run build 2>&1 | Out-String | Write-Host
    $buildExit = $LASTEXITCODE
    Pop-Location
    if ($buildExit -ne 0) {
        Write-Host "FALHA no build (exit $buildExit). Abortando restart para nao subir build quebrado."
        exit 1
    }
    Write-Host "Build OK. BUILD_ID: $(Get-Content "$root\frontend\.next\BUILD_ID")"
}

# 3. Sobe o _run-frontend novo (em background, igual o restart-backend-only faz)
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\_run-frontend.ps1"
Write-Host "Frontend novo lancado; aguardando porta 3003..."
Start-Sleep -Seconds 10

# 4. Validacao: home 200 + checa se ainda ha chunks fantasmas (500 em .js)
try {
    $home = Invoke-WebRequest 'http://127.0.0.1:3003/' -UseBasicParsing -TimeoutSec 15
    Write-Host "OK home HTTP $($home.StatusCode)"
} catch {
    Write-Host "FALHA home: $($_.Exception.Message)"
}

# Extrai um chunk do HTML da home e testa se serve 200 com content-type correto
try {
    $html = (Invoke-WebRequest 'http://127.0.0.1:3003/auth/login' -UseBasicParsing -TimeoutSec 15).Content
    $matches = [regex]::Matches($html, '/_next/static/chunks/[^"''\s]+\.js')
    $broken = 0; $tested = 0
    foreach ($m in $matches) {
        $url = 'http://127.0.0.1:3003' + $m.Value
        $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 10
        $tested++
        if ($r.StatusCode -ne 200 -or $r.Headers['Content-Type'] -notmatch 'javascript') {
            $broken++
            Write-Host "  CHUNK QUEBRADO: $($m.Value) -> HTTP $($r.StatusCode) ($($r.Headers['Content-Type']))"
        }
    }
    if ($broken -eq 0) {
        Write-Host "OK $tested chunks de /auth/login servindo 200 (javascript). Build consistente."
    } else {
        Write-Host "ATENCAO: $broken/$tested chunks quebrados. Build ainda inconsistente - rode com -Rebuild."
    }
} catch {
    Write-Host "Aviso: nao consegui validar chunks de /auth/login: $($_.Exception.Message)"
}
