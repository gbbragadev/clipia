$root = 'C:\Dev\auto-shorts'
Set-Location "$root\frontend"
& npm run dev -- -p 3003 *>&1 | Out-File -Encoding utf8 "$root\storage\frontend.log"
