$root = 'C:\Dev\clipia'
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$config = "$env:USERPROFILE\.cloudflared\clipia.yml"
& $cf tunnel --config $config run clipia *>&1 | Out-File -Encoding utf8 "$root\storage\clipia-tunnel.log"
