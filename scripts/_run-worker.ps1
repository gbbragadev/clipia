$keys = @('OPEN_ROUTER_API_KEY','GROQ_API_KEY','ELEVENLABS_API_KEY','PEXELS_API_KEY','OPENAI_API_KEY','CLOUDFLARE_API_TOKEN','RCLONE_EXE','TURNSTILE_SECRET_KEY')
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { Set-Item -Path "env:$k" -Value $v }
}
$root = 'C:\Dev\clipia'
Set-Location $root

# Beat como PROCESSO SEPARADO: o celery REJEITA -B no Windows ("does not work on
# Windows"). Sem beat, cleanup_old_jobs/cleanup_orphan_files nunca rodam. O watchdog
# de jobs travados NAO depende do beat (thread daemon via worker_ready no worker).
# Guard anti-duplicata: relancamentos do script nao podem empilhar beats (agendariam
# as tasks em dobro).
$existingBeat = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'celery' -and $_.CommandLine -match '\bbeat\b' }
if (-not $existingBeat) {
    Start-Process -WindowStyle Hidden -FilePath "$root\.venv312\Scripts\python.exe" `
        -ArgumentList '-m','celery','-A','app.worker.celery_app','beat','-s',"$root\storage\celerybeat-schedule",'-l','info' `
        -WorkingDirectory $root `
        -RedirectStandardOutput "$root\storage\beat.log" -RedirectStandardError "$root\storage\beat.err.log"
}

while ($true) {
    & .\.venv312\Scripts\python.exe -m celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo *>&1 | Out-File -Append -Encoding utf8 "$root\storage\worker.log"
    Add-Content -Path "$root\storage\worker.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Worker encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
