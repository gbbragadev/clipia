$keys = @('OPEN_ROUTER_API_KEY','GROQ_API_KEY','ELEVENLABS_API_KEY','PEXELS_API_KEY','OPENAI_API_KEY','CLOUDFLARE_API_TOKEN','TURNSTILE_SECRET_KEY')
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { Set-Item -Path "env:$k" -Value $v }
}
$root = 'C:\Dev\clipia'
Set-Location $root
while ($true) {
    & .\.venv312\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8005 *>&1 | Out-File -Append -Encoding utf8 "$root\storage\backend.log"
    Add-Content -Path "$root\storage\backend.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Backend encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
