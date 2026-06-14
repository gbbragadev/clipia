# QA_LEDGER — Estado do ralph QA (ClipIA)

Estado mutável lido e gravado a cada iteração. **Não editar à mão durante o loop.**

## Controle de ciclo
- `ciclo_atual`: 1
- `gerou_no_ciclo`: nao
- `smoke_prod_no_ciclo`: nao
- `ultimo_job`: (vazio)

> Iteração de teste 2026-06-13 ~22:05: rodada manual (demonstração). F01/F02 FAIL por **BUG-R001**
> (build de produção com chunks faltando → app não hidrata). Bloqueia o caminho-feliz de quase tudo
> até o rebuild. Geração (F06) e fluxos autenticados ficam impedidos enquanto o login não hidratar.

## Matriz de cobertura

| ID | Fluxo | run_count | last_result | recent (3 últimos) | last_run |
|----|-------|-----------|-------------|--------------------|----------|
| E01 | **Jornada E2E completa** (login→gerar→pipeline→editar abas→render→baixar) | 1 | PASS* | PASS* | 20260614-0034 (job b9e32bc3: gerou 242s, editor 5 abas/7 cenas, render ~5-6min, MP4 36.8MB. *expôs e CORRIGIU BUG-R002/R003 de sessão/preview) |
| F01 | Landing `/` | 2 | PASS | FAIL PASS | 20260613-2234 (BUG-R001 resolvido: main visível, console limpo) |
| F02 | Login | 2 | PASS | FAIL PASS | 20260613-2235 (BUG-R001 resolvido: LOGGED local+prod) |
| F03 | Register (validação) | 0 | — | — | — |
| F04 | Verify/Forgot/Reset | 0 | — | — | — |
| F05 | Dashboard | 0 | — | — | — |
| F06 | GenerateForm (+geração) | 0 | — | — | — |
| F07 | Editor (5 abas) | 0 | — | — | — |
| F08 | Export (modal) | 0 | — | — | — |
| F09 | Settings | 0 | — | — | — |
| F10 | Credits | 0 | — | — | — |
| F11 | Logout | 0 | — | — | — |
| F12 | Estáticas/Blog | 0 | — | — | — |
| F13 | Admin | 0 | — | — | — |
| F14 | Mídia avançada (clone voz, upload áudio, cancel/reset) | 0 | — | — | — |
| F15 | Conta, créditos & público (senha, export, waitlist, checkout) | 0 | — | — | — |
| S01 | Rotas protegidas não vazam (deslogado) | 0 | — | — | — |
| S02 | Security headers | 1 | PASS | PASS | 20260613-2235 (SEC-01 resolvido: 6 headers local+prod) |
| S03 | Token/secrets não vazam no client | 0 | — | — | — |
| S04 | API exige auth (sem bypass) | 1 | PASS | PASS | 20260613-2200 (401 sem token local+prod) |
| S05 | IDOR / autorização horizontal | 0 | — | — | — |
| S06 | Rate limiting no login | 0 | — | — | — |
| P01 | Home prod (smoke) | 0 | — | — | — |
| P02 | Públicas prod (smoke) | 0 | — | — | — |

## Eventos (BLOCKED / notas operacionais)

<!-- Acrescente aqui linhas tipo: BLOCKED preflight 20260613-1530: frontend=000 backend=200 -->
- dry-run 2026-06-13: stack LOCAL no ar (backend 8005=200; frontend 3003 vivo via browser/IPv4, curl localhost IPv6 pendura). Login OK, landing renderiza.
- dry-run 2026-06-13: **PROD clipia.com.br FORA** — HTTP 530 / Cloudflare error 1033 (túnel desconectado). Smoke prod (P01/P02/P-SEC) ficará BLOCKED até o túnel/scheduled task 'ClipIA Production' voltar. Ver SEC/DISPONIBILIDADE em QA_BUGS.md.
