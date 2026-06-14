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
- Status: open (confirmar em PROD — dev tem ruído de turbopack que pode disparar o boundary)
- Observado: deslogado, `/dashboard` permanece na URL e mostra "Não foi possível carregar esta página /
  Ocorreu um erro inesperado". **Não vaza dados sensíveis** (sem créditos/email/lista). Esperado: redirect
  limpo para `/auth/login`. Em dev, o ChunkLoadError do turbopack pode estar disparando o boundary, então
  precisa ser confirmado contra build de produção.
- Evidência: dry-run inline (sem PNG).
