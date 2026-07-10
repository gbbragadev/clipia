$keys = @('OPEN_ROUTER_API_KEY','GROQ_API_KEY','ELEVENLABS_API_KEY','PEXELS_API_KEY','OPENAI_API_KEY','CLOUDFLARE_API_TOKEN','RCLONE_EXE','TURNSTILE_SECRET_KEY')
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { Set-Item -Path "env:$k" -Value $v }
}
$root = 'C:\Dev\clipia'
Set-Location $root
while ($true) {
    # -B: beat embutido (cleanup_old_jobs/cleanup_orphan_files nunca rodavam sem ele).
    # O watchdog de jobs travados NAO depende do beat (thread daemon via worker_ready).
    & .\.venv312\Scripts\python.exe -m celery -A app.worker.celery_app worker -B -s "$root\storage\celerybeat-schedule" -l info --concurrency=1 --pool=solo *>&1 | Out-File -Append -Encoding utf8 "$root\storage\worker.log"
    Add-Content -Path "$root\storage\worker.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Worker encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
