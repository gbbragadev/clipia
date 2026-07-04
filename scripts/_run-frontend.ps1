$root = 'C:\Dev\clipia'
Set-Location "$root\frontend"
# Producao: roda o build estatico de .next (gerado por `npm run build`).
#
# !!! BUG RAIZ DOCUMENTADO !!!
# NUNCA rode `npm run build` enquanto este processo (next start) estiver no ar.
# O `next start` carrega o manifest (BUILD_ID + mapa de chunks/server-actions) em
# memoria ao subir. Se o .next for sobreescrito por um build novo durante a vida
# do processo, o HTML comeca a referenciar chunks do build NOVO que o processo
# nao conhece -> HTTP 500 "text/plain" em arquivos .js -> browser recusa executar
# (MIME type errado) -> JS da pagina morre -> login/dashboard/register quebrados
# (sintoma: "nao consigo entrar no dashboard"). Alem disso, Server Actions deixam
# de ser encontradas ("Failed to find Server Action ...").
#
# Para rebuildar em producao, use sempre:
#   powershell -ExecutionPolicy Bypass -File scripts\restart-frontend.ps1 -Rebuild
# (ele PARA o next start, builda atomico, e so entao reinicia).
while ($true) {
    & npm run start -- -p 3003 *>&1 | Out-File -Append -Encoding utf8 "$root\storage\frontend.log"
    Add-Content -Path "$root\storage\frontend.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Frontend encerrou. Reiniciando em 5s..."
    Start-Sleep 5
}
