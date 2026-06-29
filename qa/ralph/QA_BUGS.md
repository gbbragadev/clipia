# QA_BUGS — Bug ledger do ralph QA (ClipIA)

Bugs descobertos pelo loop, persistidos entre iterações. Dedup por assinatura (`<ID-fluxo> + <sintoma>`).
Status possíveis: `open` · `confirmed` (falhou 3x igual) · `intermittent` · `resolved?` (3 PASS seguidos depois de falhar).

> Bugs conhecidos do `QA_REPORT.md` (2026-04-26), para referência de dedup:
> - BUG-001: host `127.0.0.1:3003` quebra hidratação do Next dev (usar `localhost`).
> - BUG-002: preço no card de template não bate com o custo real por voz.

## Formato

```
### BUG-RXXX: <título curto>
- Assinatura: <ID-fluxo> + <sintoma>
- Severidade: alta | média | baixa
- Status: open | confirmed | intermittent | resolved?
- Ocorrências: <n>   Primeiro: <ts>   Último: <ts>
- Reprodução:
  1. ...
- Esperado: ...
- Observado: ...
- Evidência: qa/ralph/evidence/<png> + linhas de console
```

## Bugs abertos

### BUG-R001: Build de produção referencia chunks inexistentes → app não hidrata (login quebrado)  [CRÍTICO / PROD]
- Assinatura: F01/F02 + chunk 500 + hidratação quebrada
- Severidade: ALTA — afeta produção (clipia.com.br) e local (3003), usuários reais não conseguem logar
- Status: **RESOLVED** (rebuild limpo, verificado local+prod 2026-06-13 ~22:35)
- Correção aplicada: parar `next start` → `rm -rf frontend/.next` → `npm run build` (exit 0) → resubir `next start -p 3003`.
  Novo BUILD_ID `SIkuYphg25CQl4Q7QckNS`. Verificação: 41 chunks (/, /auth/login, /dashboard) todos 200 no local;
  12 chunks 200 em prod; login real grava `clipia_token` (LOGGED) local **e** em clipia.com.br; console 0 erros;
  home renderiza estilizada (evidência `qa/ralph/evidence/prod-login-fixed-20260613-223545.png`).
- Reprodução:
  1. `curl -4 -s http://127.0.0.1:3003/auth/login` (ou `https://clipia.com.br/auth/login`).
  2. Extrair os `/_next/static/chunks/*.js|*.css` referenciados no HTML.
  3. Testar cada um. Dois sempre dão **500**: `0pjnp0nyit1ls.css` e `0qhcykvks82oh.js`.
  4. Esses arquivos **não existem** em `frontend/.next/static/chunks/` (confirmado: "No such file").
- Observado: CSS + 1 JS chunk não carregam → React não hidrata → `is visible main/h1` = false, login não grava
  `clipia_token` (fica ANON), submit cai em comportamento nativo. Mesmo comportamento em prod (mesmos chunks = 500).
- Causa raiz provável: `next build` no Next 16 usa **turbopack** por padrão (HTML tem `turbopack-*.js`); o build das
  ~21:57 gerou um manifest inconsistente (referencia 2 chunks não emitidos). Build anterior (pré-21:57) funcionava.
- Correção sugerida: **rebuild limpo** — parar o `next start` (PID 24760), `rm -rf frontend/.next`, `npm run build`,
  validar que todos os chunks referenciados existem, `next start -p 3003`. Se recorrer, fixar bundler do build
  (evitar turbopack no `next build`) ou pinar versão do Next. **Não auto-corrigir sem o Gui pedir.**
- Evidência: medições inline (local + prod, 500 nos 2 chunks; ausentes no disco).

### BUG-R002: Preview de vídeo no dashboard usa endpoint protegido como `<video src>` → 401  [achado do E01]
- Assinatura: F05/E01 + preview 401
- Severidade: média (previews de vídeo não carregam no VideoCard)
- Status: **RESOLVED** (corrigido + verificado 2026-06-14)
- Correção: `VideoCard.tsx` carrega o preview via `fetchAuthenticatedBlobUrl` (Bearer) lazy no hover e usa `<video src={blob}>`;
  removida a tag `<video src={download_url}>` direta. Verificado: 0 elementos com src `/download`, 0 requests /download
  e 0 erros 401 no load do dashboard.
- Observado: `VideoCard.tsx:70` renderiza `<video src={job.download_url}>` com `download_url = /api/v1/jobs/{id}/download`,
  que exige `Authorization: Bearer`. Tags HTML não enviam header → cada preview faz `GET /download → 401` e não renderiza.
- Correção sugerida: endpoint de preview público/assinado (token na query/URL temporária) ou servir thumbnail separado;
  não referenciar um endpoint Bearer-only direto em `<video src>`. O `protected-download.spec.js` (skipped) já mira isso.

### BUG-R003: Qualquer 401 desloga o usuário (logout global) → deslogamento espúrio  [achado do E01 — o mais sério]
- Assinatura: sessão + 401 derruba token
- Severidade: alta (perda de sessão no meio do uso; combinado com BUG-R002, navegar no dashboard/editor pode deslogar)
- Status: **RESOLVED** (corrigido + verificado 2026-06-14)
- Correção: `notifySessionExpired()` removido de `http.ts` (fetchJson), `download.ts` e dos painéis do editor
  (AIAssistant/ExportPanel/VoiceSelector). Expiração de sessão agora é detectada só por `getMe()` (load + polling
  5min do AuthContext); um 401 de recurso secundário falha local (toast), não desloga. Verificado: token sobrevive a
  3 navegações dashboard↔editor (antes sumia sozinho). tsc + build OK; prod 200.
- Observado: `http.ts:58-60` (fetch genérico), `lib/download.ts:13`, `lib/auth.ts` e os painéis do editor chamam
  `notifySessionExpired()` para TODO `401`, que faz `localStorage.removeItem('clipia_token')` + evento → AuthContext desloga.
  Logo um 401 de **recurso secundário** (preview/download de um job específico) derruba a sessão válida inteira.
- Correção sugerida: só tratar como sessão expirada o 401 do endpoint de **sessão/auth** (ex: `/auth/me`). 401 de um
  recurso específico deve falhar localmente (toast/retry), não deslogar. Distinguir "token inválido" de "acesso negado a X".
- Repro QA: logar → navegar dashboard↔editor algumas vezes monitorando `localStorage.getItem('clipia_token')`; se virar
  null sem o usuário clicar em Sair → bug presente.

### BUG-R004: Race condition — /api/v1/jobs e /api/v1/trends disparam 401 na carga inicial do dashboard
- Assinatura: F05 + 401 race condition no load
- Severidade: média (console poluído; UX com flash de grid vazio ~2s; riesgo de retry loop)
- Status: **intermittent** (1 ocorrência no ciclo 1; NÃO reproduzido em ciclos 2 e 3 — F05 PASS em ambos)
- Ocorrências: 1   Primeiro: 20260628-215416   Último: 20260628-215416
- Reprodução:
  1. Logar → navegar para /dashboard (primeira carga)
  2. Observar console: `GET /api/v1/jobs → 401` e `GET /api/v1/trends → 401` nos primeiros 500ms
  3. Após ~2s, as chamadas repetem e retornam 200
- Esperado: primeira chamada já autentica (token pronto antes do fetch)
- Observado: AuthContext não fornece o token a tempo das primeiras chamadas dos componentes; elas disparam sem Bearer header e retornam 401, depois retry retorna 200
- Evidência: `qa/.claude/qa-evidence/F05-dashboard-20260628-215416.png` + network log inline

### BUG-R007: Tunnel clipia.yml não sobrevive a reinicializações — prod cai sem aviso
- Assinatura: P01 + 530 / tunnel dead
- Severidade: alta (prod offline sem alerta; usuários reais sem acesso)
- Status: **intermittent** (ocorreu no início do QA; P01/P02 PASS em 3 ciclos consecutivos sem recorrência; tunnel estável desde recuperação)
- Ocorrências: 2   Primeiro: 20260613 (DISP-PRE-01)   Último: 20260628-221000
- Reprodução: após reinicialização do sistema ou kill do cloudflared de prod, `clipia.com.br` retorna 530
- Esperado: scheduled task 'ClipIA Production' mantém tunnel sempre no ar
- Observado: `cloudflared.exe --config clipia.yml` não estava rodando (PID 23808=Services sem cmdline visível; PID 26136=senior-mcp; PID 29532=config.yml padrão sem clipia)
- Correção aplicada (QA): subiu `_run-tunnel.ps1` manualmente → prod voltou a 200
- Correção sugerida: monitorar/auto-restart do tunnel (Windows Service dedicado ou health check no scheduled task; confirmar que start-production.ps1 reinicia o tunnel quando chamado)
- Evidência: `Get-CimInstance Win32_Process` inline + P01-prod-live-20260628-221245.png

### BUG-R006: Landing mostra "2 vídeos" hardcoded enquanto /api/v1/public/stats retorna total_videos=0
- Assinatura: F15 + public stats hardcoded
- Severidade: baixa (social proof incorreto — número inventado)
- Status: **resolved?** (falso positivo — re-analisado em 20260629)
- Ocorrências: 1   Primeiro: 20260628   Último: 20260628
- Re-análise (20260629): O "2 vídeos" capturado pelo regex era o COPY DE MARKETING ("2 vídeos grátis ao criar conta" em HeroSection.tsx:18), NÃO um stat de plataforma. O componente real de estatísticas é `SocialProofBar.tsx` que mostra "500+" por padrão (intencional — social proof default quando API retorna 0). Comportamento é design intencional, não bug.
- Reprodução: `GET /api/v1/public/stats` → `{"total_videos":0}`; landing mostra "2 vídeos criados"
- Esperado: número reflete endpoint dinâmico
- Observado: landing hardcoded ou usa dado diferente do endpoint
- Evidência: inline + F15-credits-20260628-220603.png

### BUG-R005: noise.svg retorna 404 — asset estático faltando no build
- Assinatura: F05 + noise.svg 404
- Severidade: baixa (visual — textura de background ausente)
- Status: **resolved?** (arquivo criado em 20260629; requer restart do next start para servir)
- Ocorrências: 1   Primeiro: 20260628   Último: 20260628
- Correção aplicada: `frontend/public/noise.svg` criado (328 bytes, SVG com feTurbulence fractalNoise). Next.js indexa `public/` na inicialização — o arquivo será servido após próximo restart/rebuild.
- Reprodução: Acessar qualquer página do dashboard → console mostra `GET /noise.svg → 404`
- Esperado: arquivo `frontend/public/noise.svg` existe e serve corretamente
- Observado: 404 em ambas as cargas do dashboard observadas (servidor não reiniciado após criação)
- Evidência: console inline

---

_(achados preliminares de segurança/disponibilidade do dry-run abaixo)_

## Achados preliminares de segurança (dry-run 2026-06-13, a confirmar)

### SEC-01: Frontend de PRODUÇÃO não envia NENHUM header de segurança  [CONFIRMADO]
- Assinatura: S02 + frontend prod sem headers
- Severidade: média (clickjacking / MIME-sniffing / sem HSTS)
- Status: **RESOLVED** (corrigido no `next.config.ts`, verificado em prod 2026-06-13 ~22:35)
- Correção aplicada: `async headers()` em `frontend/next.config.ts` agora injeta em `/(.*)`: `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`,
  `Permissions-Policy` e `Content-Security-Policy: frame-ancestors 'none'` (CSP mínima p/ não quebrar Next/Remotion).
  Verificado: 6 headers presentes em `https://clipia.com.br/` e no local. Espelha a política do backend (`app/main.py`).
- Observado: `GET https://clipia.com.br/` (app respondendo 200) **não** retorna `content-security-policy`,
  `x-frame-options`, `x-content-type-options`, `strict-transport-security`, `referrer-policy` nem
  `permissions-policy` — TODOS faltam. O backend (8005) envia o conjunto completo; o frontend Next não.
  (Quando prod estava em erro 1033, a página de erro do Cloudflare mostrava X-Frame SAMEORIGIN/Referrer —
  isso era do Cloudflare, não do app.)
- Esperado: a resposta HTML deveria ter ao menos `x-frame-options: DENY` (ou CSP `frame-ancestors 'none'`),
  `x-content-type-options: nosniff` e `strict-transport-security`. Risco: clickjacking via iframe, MIME-sniffing.
- Correção sugerida: adicionar `async headers()` em `frontend/next.config.ts` (mesmo conjunto do backend),
  ou Transform Rules no Cloudflare. **Não corrigir sem o Gui pedir** (política de QA: reportar, não auto-corrigir).
- Evidência: medição inline (6/6 headers ausentes em prod).

### DISP-PRE-01: Produção deu 530/error 1033 — TRANSITÓRIO (resolvido)
- Assinatura: P01 + tunnel down
- Severidade: baixa (foi blip de rede, não config)
- Status: resolved? (prod voltou a 200 minutos depois; causa identificada)
- Causa raiz: blip de DNS/rede do cloudflared `clipia` (PID 1992). Log `storage\clipia-tunnel.log`:
  `Failed to refresh DNS local resolver: i/o timeout` ~00:51:02 → reconectou 4 conexões (gru21/cwb01/gru02) 00:51:17.
  O teste de 530 caiu exatamente nessa janela. Frontend prod (`next start -p 3003`, PID 24760) e backend (8005)
  nunca caíram. Prod agora 200, 17.5KB, título correto.
- Risco latente (recomendação, não bug ativo): `clipia.yml` usa `service: http://localhost:3003`. Como `localhost`
  resolve IPv6 `::1` (que pendura — ver learning), trocar para `service: http://127.0.0.1:3003` deixa o túnel mais
  robusto a falhas de resolução IPv6. Baixa prioridade — hoje funciona.
- Evidência: log do túnel + 3x 200 na recheck.

### SEC-PRE-02: `/dashboard` deslogado cai em error boundary em vez de redirecionar
- Assinatura: S01 + sem redirect deslogado
- Severidade: baixa (não vaza dados — apenas UX/robustez)
- Status: **resolved?** (S01 testado 20260628: /dashboard/settings/credits/admin→redirect "Entrar | ClipIA" sem dados sensíveis; editor→view genérica; 0 vazamentos)
- Observado: deslogado, `/dashboard` permanece na URL e mostra "Não foi possível carregar esta página /
  Ocorreu um erro inesperado". **Não vaza dados sensíveis** (sem créditos/email/lista). Esperado: redirect
  limpo para `/auth/login`. Em dev, o ChunkLoadError do turbopack pode estar disparando o boundary, então
  precisa ser confirmado contra build de produção.
- Evidência: dry-run inline (sem PNG). S01 em 20260628 não encontrou recorrência.
