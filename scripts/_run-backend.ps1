$keys = @('ANTHROPIC_API_KEY','GROQ_API_KEY','ELEVENLABS_API_KEY','PEXELS_API_KEY','OPENAI_API_KEY','CLOUDFLARE_API_TOKEN')
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { Set-Item -Path "env:$k" -Value $v }
}
$root = 'C:\Dev\auto-shorts'
Set-Location $root
& .\.venv312\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8005 *>&1 | Out-File -Encoding utf8 "$root\storage\backend.log"
