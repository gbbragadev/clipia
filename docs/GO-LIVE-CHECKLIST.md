# ClipIA — Checklist de Go-Live (PRD "Produto lançado e funcional")

> Estado em 2026-06-30. Trabalho feito na branch `feat/frontend-elevacao` (commits
> `2b06dae`, `7c0db5b`, `4b51430`). Detalhe técnico na memória `golive-launch-fixes.md`.
> Marcar `[x]` conforme for fechando "check a check".

## ✅ Já feito e verificado (não mexer)
- [x] **Bug do 502** (amigo não gerava): chamadas LLM/transcribe síncronas → `asyncio.to_thread`. Provado (event loop livre).
- [x] **Geração funcional**: cascata de provedores LLM (OpenAI gpt-4o-mini primário → xAI → OpenRouter → free). OpenRouter recarregado.
- [x] **Frontend**: nunca vaza HTML de erro (`http.ts`), polling não trava em spinner infinito.
- [x] **Stripe** como 2º provedor (Checkout cartão funcionando, `cs_live_` criado).
- [x] **Worker NullPool** → corrige "Event loop is closed" no refund de crédito.
- [x] **Favicon coral** na aba.
- [x] **Guardrail anti-burn**: `MAX_AI_VIDEO_PER_DAY=3` por conta (vale p/ admin) + log de custo.
- [x] **QA de geração**: 6/7 vídeos distintos OK (stock, ElevenLabs, gameplay local, emoji, XSS, **ai_video premium Seedance**). Editor dogfood OK.
- [x] **QA adversarial/segurança 14/14**: auth, IDOR, 0-crédito, validação, checkout, URL assinada, rate-limit.

## 🔴 Bloqueadores de go-live (fazer antes de abrir)

### Pagamento (foco da próxima sessão)
- [ ] **Stripe webhook**: criar endpoint em dashboard.stripe.com → Developers → Webhooks apontando p/ `https://clipia.com.br/api/v1/webhooks/stripe`, copiar o `whsec_` p/ `STRIPE_WEBHOOK_SECRET` no `.env`.
- [ ] **Stripe Pix**: ativar em dashboard.stripe.com → Settings → Payments (hoje só cartão; o código já liga Pix sozinho ao ativar).
- [ ] **MP webhook**: registrar `https://clipia.com.br/api/v1/webhooks/mercadopago` no painel MP + copiar a "Assinatura secreta" p/ `MP_WEBHOOK_SECRET` no `.env`.
- [ ] **Teste E2E de pagamento SEM cobrar**: MP (usuário/cartão de teste) e Stripe (test mode) → comprar pacote → webhook → créditos creditados → idempotência (webhook repetido credita 1x). Precisa de chaves/usuários de TESTE p/ não gastar dinheiro real (a `STRIPE_SECRET_KEY` no `.env` é `rk_live`).

### Config/deploy
- [ ] **Deployar fix do gpt-image** (`4b51430`): restart do worker COM rede (`! powershell -File scripts\start-production.ps1`, fora do agente) → re-testar `ai_visual` e `novelinha` (templates de imagem). Confirmar que a conta da `LLM_OPENAI_KEY` tem acesso a gpt-image e que o modelo `gpt-image-2` existe.
- [ ] **JWT_SECRET** forte em prod — já OK (verificado, 64-hex).
- [ ] Decidir provedor LLM primário definitivo (OpenAI gpt-4o-mini barato vs DeepSeek via OpenRouter).

### Segurança/abuso
- [ ] **Investigar os ~$6 queimados** no OpenRouter (painel → Activity): qual conta/key. O gating está OK (2 créditos não geram ai_video); foi a conta admin (999k créditos).
- [ ] Opcional: baixar os 999.999 créditos do `seed_admin.py` (o cap de 3/dia já mitiga).

## 🟠 Recomendado antes/logo após o launch
- [ ] **Monitoramento/alertas**: crash do worker, taxa de jobs falhados, disco < 5GB.
- [ ] **Backup automático do Postgres** (scheduled task diária com `backup-postgres.ps1`).
- [ ] Garantir que os processos de prod são os do **logon (com rede)** — não reiniciar backend/worker de dentro de um agente sandbox (perde rede de saída).
- [ ] `validate_readiness.py` verde contra prod como gate final.

## 🟡 Qualidade / polish (não bloqueia)
- [ ] Relevância da mídia stock (Pexels): keyword às vezes tangencial (ex.: "Egito" → milho). Melhorar prompt de keywords.
- [ ] QA mobile dos fluxos logados (gerar/editar no celular).
- [ ] Cobrir templates restantes no QA de geração: `character_narration`, `story_time`, `dialogue_duo`, e os 7 nichos.
- [ ] Medir custo real $ por operação com o log já adicionado (telemetria de ai_video).

## Conta de QA (reuso)
`qa.dogfood@clipia.com.br` / `QAdogfood12345!` (50 créditos, verificada).
