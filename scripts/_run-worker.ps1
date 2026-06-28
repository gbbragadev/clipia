$keys = @('OPEN_ROUTER_API_KEY','GROQ_API_KEY','ELEVENLABS_API_KEY','PEXELS_API_KEY','OPENAI_API_KEY','CLOUDFLARE_API_TOKEN','RCLONE_EXE')
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { Set-Item -Path "env:$k" -Value $v }
}
$root = 'C:\Dev\clipia'
Set-Location $root
& .\.venv312\Scripts\python.exe -m celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo *>&1 | Out-File -Encoding utf8 "$root\storage\worker.log"
