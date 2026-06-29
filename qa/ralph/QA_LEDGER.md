# QA_LEDGER — Estado do ralph QA (ClipIA)

Estado mutável lido e gravado a cada iteração. **Não editar à mão durante o loop.**

## Controle de ciclo
- `ciclo_atual`: 3
- `gerou_no_ciclo`: sim (job 1df7199f — ciclo 1→2)
- `smoke_prod_no_ciclo`: sim
- `ultimo_job`: 1df7199f-35eb-48ae-bf1f-9e4a67a75844

> Iteração de teste 2026-06-13 ~22:05: rodada manual (demonstração). F01/F02 FAIL por **BUG-R001**
> (build de produção com chunks faltando → app não hidrata). Bloqueia o caminho-feliz de quase tudo
> até o rebuild. Geração (F06) e fluxos autenticados ficam impedidos enquanto o login não hidratar.

## Matriz de cobertura

| ID | Fluxo | run_count | last_result | recent (3 últimos) | last_run |
|----|-------|-----------|-------------|--------------------|----------|
| E01 | **Jornada E2E completa** (login→gerar→pipeline→editar abas→render→baixar) | 2 | PASS | PASS* PASS | 20260629-0122 (job 1df7199f: stock_narration [QA-E2E] buracos negros, Edge TTS, pipeline ~90s, 5 cenas/45s, 12.9MB MP4, editor 5 abas OK, export modal YT/TikTok/IG OK, token preservado, 0 erros console) |
| F01 | Landing `/` | 4 | PASS | PASS PASS PASS | 20260629-c3 (c3: landing OK, console sem erros) |
| F02 | Login | 4 | PASS | PASS PASS PASS | 20260629-c3 (c3: auth/me retorna email+créditos OK) |
| F03 | Register (validação) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: validações OK, form não submeteu) |
| F04 | Verify/Forgot/Reset | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: verify/forgot/reset todos 200) |
| F05 | Dashboard | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: h1+créditos+token OK) |
| F06 | GenerateForm (+geração) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: topicInput+genBtn presentes; sem submeter) |
| F07 | Editor (5 abas) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: 5 abas ativas via editor job 1df7199f) |
| F08 | Export (modal) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: hasBaixar+hasYT OK; botão Exportar funcional) |
| F09 | Settings | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: auth/me name+email OK) |
| F10 | Credits | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: packages=3) |
| F11 | Logout | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: token→NULL via removeItem; re-login OK) |
| F12 | Estáticas/Blog | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: blog/termos/privacidade todos 200) |
| F13 | Admin | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: /dashboard/admin=200) |
| F14 | Mídia avançada (clone voz, upload áudio, cancel/reset) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: reset→status=rendering OK) |
| F15 | Conta, créditos & público (senha, export, waitlist, checkout) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: history=true; packages=3; R006=false positive) |
| S01 | Rotas protegidas não vazam (deslogado) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: /dashboard sem dados sensíveis; hasUserData=false) |
| S02 | Security headers | 4 | PASS | PASS PASS PASS | 20260629-c3 (c3: 6/6 headers frontend ✅ QA-GREEN) |
| S03 | Token/secrets não vazam no client | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: 0 secrets na landing) |
| S04 | API exige auth (sem bypass) | 4 | PASS | PASS PASS PASS | 20260629-c3 (c3: jobs=401 me=401 sem token ✅ QA-GREEN) |
| S05 | IDOR / autorização horizontal | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: UUID fake→404) |
| S06 | Rate limiting no login | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: 401,401,401,429) |
| P01 | Home prod (smoke) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: 200 clipia.com.br; tunnel estável) |
| P02 | Públicas prod (smoke) | 3 | PASS | PASS PASS PASS | 20260629-c3 (c3: blog=200 prod) |

## Eventos (BLOCKED / notas operacionais)

<!-- Acrescente aqui linhas tipo: BLOCKED preflight 20260613-1530: frontend=000 backend=200 -->
- dry-run 2026-06-13: stack LOCAL no ar (backend 8005=200; frontend 3003 vivo via browser/IPv4, curl localhost IPv6 pendura). Login OK, landing renderiza.
- dry-run 2026-06-13: **PROD clipia.com.br FORA** — HTTP 530 / Cloudflare error 1033 (túnel desconectado). Smoke prod (P01/P02/P-SEC) ficará BLOCKED até o túnel/scheduled task 'ClipIA Production' voltar. Ver SEC/DISPONIBILIDADE em QA_BUGS.md.
- BLOCKED preflight 20260628-205119: frontend=000 (CONNECTION_REFUSED curl+browser), backend=200. Frontend 3003 (`next start`) offline. Subir com `.\scripts\start-all.ps1` ou `.\scripts\_run-frontend.ps1` antes da próxima iteração.
- RECOVERED 20260628-214932: frontend subido manualmente via `_run-frontend.ps1` (PID background). Iteração 1 prosseguiu após isso.
- BLOCKED smoke-prod 20260628-221000: clipia.com.br 530. Tunnel clipia.yml não estava rodando. Subido manualmente `_run-tunnel.ps1` → prod voltou a 200 em ~8s. BUG-R007 aberto.
- QA GREEN 20260629: ciclo 3 concluído. Todos os fluxos F01–F15/S01–S06/P01–P02 com ≥3 PASSes consecutivos. E01 com 2 PASSes. R004→intermittent (não reproduzido em 2 ciclos). R007→intermittent (P01/P02 PASS em 3 ciclos consecutivos). Zero bugs open/confirmed.
