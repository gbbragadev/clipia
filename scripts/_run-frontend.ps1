$root = 'C:\Dev\clipia'
Set-Location "$root\frontend"
# Producao: usa o build standalone (rodar `npm run build` apos mudar codigo ou LOCAL_API_URL)
& npm run start -- -p 3003 *>&1 | Out-File -Encoding utf8 "$root\storage\frontend.log"
