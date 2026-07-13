# scripts/check-env.ps1
# Verifica que todas as env vars de User necessarias para ClipIA estao setadas.
# Uso: .\scripts\check-env.ps1

$required = @{
    'OPEN_ROUTER_API_KEY'  = 'OpenRouter / DeepSeek (roteiro + IA editor)'
    'PEXELS_API_KEY'       = 'Stock media'
    'GROQ_API_KEY'         = 'Whisper ASR primario'
    'OPENAI_API_KEY'       = 'OpenAI (Whisper fallback + futuro gpt-image)'
    'ELEVENLABS_API_KEY'   = 'ElevenLabs TTS'
    'CLOUDFLARE_API_TOKEN' = 'Cloudflare Tunnel'
    'METRICS_TOKEN'        = 'Bearer privado do Prometheus'
}

$missing = @()
$ok = @()

foreach ($key in $required.Keys) {
    $val = [Environment]::GetEnvironmentVariable($key, 'User')
    if ([string]::IsNullOrWhiteSpace($val)) {
        $missing += "  - $key ($($required[$key]))"
    } else {
        $ok += "  + $key (len=$($val.Length))"
    }
}

Write-Host ""
Write-Host "=== ClipIA env vars check ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Present:" -ForegroundColor Green
$ok | ForEach-Object { Write-Host $_ -ForegroundColor Green }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "MISSING:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    Write-Host ""
    Write-Host "Criar com (PowerShell em janela nova apos setar):" -ForegroundColor Yellow
    Write-Host "  [Environment]::SetEnvironmentVariable('NOME','VALOR','User')" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Todas as env vars presentes." -ForegroundColor Green
exit 0
