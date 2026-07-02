$root = 'C:\Dev\clipia'
Set-Location "$root\frontend"
# Producao: usa o build standalone (rodar `npm run build` apos mudar codigo ou LOCAL_API_URL)
while ($true) {
    & npm run start -- -p 3003 *>&1 | Out-File -Append -Encoding utf8 "$root\storage\frontend.log"
    Add-Content -Path "$root\storage\frontend.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Frontend encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
