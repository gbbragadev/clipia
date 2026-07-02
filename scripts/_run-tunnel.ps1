$root = 'C:\Dev\clipia'
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$config = "$env:USERPROFILE\.cloudflared\clipia.yml"
while ($true) {
    & $cf tunnel --config $config run clipia *>&1 | Out-File -Append -Encoding utf8 "$root\storage\clipia-tunnel.log"
    Add-Content -Path "$root\storage\clipia-tunnel.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Tunnel encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
