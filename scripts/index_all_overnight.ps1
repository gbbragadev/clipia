# Indexa embeddings CLIP de TODAS as tags da biblioteca do Drive (batch noturno).
# Idempotente: pula clips ja embeddados (WHERE embedding IS NULL).
# Seta RCLONE_EXE (winget fora do PATH) + PYTHONPATH + ffmpeg no PATH do processo.
# Loga em storage/index_overnight.log (append). Agendar via schtasks p/ madrugada.
$env:RCLONE_EXE = "C:\Users\guibr\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.74.3-windows-amd64\rclone.exe"
$env:PYTHONPATH = "C:\Dev\clipia"
$env:Path += ";C:\Users\guibr\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
Set-Location C:\Dev\clipia
$log = "C:\Dev\clipia\storage\index_overnight.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm') - inicio indexacao overnight ===" | Out-File -FilePath $log -Append -Encoding utf8
& .\.venv312\Scripts\python.exe scripts\index_library.py *>> $log
$exitCode = $LASTEXITCODE
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm') - fim (exit=$exitCode) ===" | Out-File -FilePath $log -Append -Encoding utf8
exit $exitCode
