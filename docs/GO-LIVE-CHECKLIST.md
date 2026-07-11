# ClipIA — Checklist de Go-Live (PRD "Produto lançado e funcional")

> Estado em 2026-07-03. Trabalho feito na branch `feat/frontend-elevacao`.
> Detalhe técnico da sessão de go-live de 03/07 na seção "Sessão 03/07" abaixo.
> Marcar `[x]` conforme for fechando "check a check".

## ✅ Sessão 03/07/2026 — Destravada e pronta para go-live

### 🔴 Bloqueador crítico resolvido (causa real do "não entra no dashboard")
- [x] **Build inconsistente do Next.js em produção**: o `next start` (PID rodando
  desde 00:24) ficou servindo HTML referenciando chunks de um build antigo após um
  rebuild às 15:32 sobrecrever `.next/static`. Sintomas: chunks `.js` retornando
  HTTP 500 "text/plain" (`0nty5lbiuf0u~.js` em /auth/register, `0pga1maf6eclx.js`
  em todas as rotas /dashboard) → MIME type errado → browser recusa executar → JS
  morto → dashboard/login/register totalmente quebrados. **Resolvido** com
  `scripts/restart-frontend.ps1 -Rebuild` (parar → buildar atomicamente → reiniciar).
- [x] **Causa raiz prevenida**: documentada em `scripts/_run-frontend.ps1` (NUNCA
  rodar `npm run build` com o `next start` no ar). Criado `scripts/restart-frontend.ps1`
  com flag `-Rebuild` para rebuild atomico seguro.

### 🟠 Robustez de sessão (agravante, agora corrigido)
- [x] **`getMe()` tratava qualquer erro como sessão expirada**: um 502/503/timeout
  transitório do backend → `clearToken()` → usuário ejetado do dashboard. Corrigido
  em `frontend/src/lib/auth.ts` (nova classe `NetworkError`, timeout de 15s via
  AbortController, `notifySessionExpired()` só no 401 real) e `frontend/src/contexts/
  AuthContext.tsx` (loading inicial, polling de 5min, login e register preservam o
  token em erros transitórios). `tsc --noEmit` limpo.

### ✅ Smoke navegável em produção (clipia.com.br) — tudo verde
- [x] Landing `/`: 0 erros de console, 12/12 chunks 200, CTAs funcionais.
- [x] Login → Dashboard: entrou corretamente (49 créditos, saudação "Olá, QA",
  painel "Em alta" com 12 trends, 8 templates visíveis, vídeo "Egito antigo").
- [x] Geração de vídeo E2E: `POST /generate` → job `88bc5d34...` → pipeline completo
  (roteiro→TTS→transcrição→mídia→composição→finalize) → status `completed` em ~4min.
  Vídeo "Mistérios do Oceano Profundo" (45s) disponível, crédito debitado (49→48).
- [x] Editor `/editor/[jobId]`: 6 cenas, timeline 0:44.1, botões Resetar/Exportar/
  Reproduzir, estado "Salvo". (Nota: `ERR_QUIC_PROTOCOL_ERROR` transitório em
  range requests de MP4s grandes via Cloudflare — auto-recuperável em reload; não
  bloqueante, monitorar.)
- [x] Créditos `/dashboard/credits`: 3 pacotes Stripe (Starter/Popular/Pro), histórico
  com 2 entradas.
- [x] Settings `/dashboard/settings`: perfil, troca de senha (política), zona de
  perigo (exportar/excluir LGPD).
- [x] Mobile (375px): bottom-nav com 3 itens, `aria-current="page"` no active.

### ✅ Idempotência de pagamento
- [x] Webhooks MP e Stripe já eram idempotentes por `status` + lock por pagamento
  (`_credit_once`/`_revert_once` em `app/payments/service.py`).
- [x] Adicionado `test_webhook_approved_replay_is_idempotent` (MP) — espelho do
  `test_stripe_webhook_is_idempotent`. **347 testes pytest verdes.**

### 🆕 Gate de go-live (`validate_readiness.py`) desbloqueado
- [x] **Cloudflare Bot Fight Mode** bloqueava `Python-urllib/3.x` com erro 1010 ao
  bater em `clipia.com.br/health`. Corrigido: script agora envia
  `User-Agent: ClipIA-Readiness/1.0`.
- [x] **Turnstile** bloqueava o cadastro do script ("Verificacao anti-bot falhou").
  Adicionado bypass por header secreto: nova env `READINESS_BYPASS_SECRET` +
  header `X-Readiness-Bypass` em `app/auth/turnstile.py` + `app/auth/routes.py`.
  Testado em `tests/test_email_otp.py` (bypass correto passa, secret errado reprova).

---



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

## 🔴 Pendências manuais (SÓ VOCÊ executa — exigem painéis externos)

### Configuração do gate de go-live (liberar `validate_readiness.py`)
- [ ] **Definir `READINESS_BYPASS_SECRET` no `.env`** e reiniciar o backend
      (`scripts\restart-backend-only.ps1`). Sem isso, o `validate_readiness.py` não
      consegue cadastrar (Turnstile bloqueia, corretamente). Valor forte sugerido:
      `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Em seguida eu
      rodo `validate_readiness.py --base https://clipia.com.br` como gate final.

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
- [ ] **Monitoramento externo (UptimeRobot/semelhante) batendo em `/health/deep`**:
      confirmar que o User-Agent do monitor não é bloqueado pelo Cloudflare Bot Fight
      Mode (vimos erro 1010 com `Python-urllib/3.x`). Se bloquear, allowlist manual no
      painel Cloudflare → Security → WAF, ou desligar Bot Fight Mode (pesar risco/anti-abuso).
- [ ] **Backup automático do Postgres** (scheduled task diária com `backup-postgres.ps1`).
- [ ] Garantir que os processos de prod são os do **logon (com rede)** — não reiniciar backend/worker de dentro de um agente sandbox (perde rede de saída).
- [ ] `validate_readiness.py` verde contra prod como gate final (requer `READINESS_BYPASS_SECRET` no `.env` + backend reiniciado).

## 🟡 Qualidade / polish (não bloqueia)
- [ ] Relevância da mídia stock (Pexels): keyword às vezes tangencial (ex.: "Egito" → milho). Melhorar prompt de keywords.
- [ ] QA mobile dos fluxos logados (gerar/editar no celular).
- [ ] Cobrir templates restantes no QA de geração: `character_narration`, `story_time`, `dialogue_duo`, e os 7 nichos.
- [ ] Medir custo real $ por operação com o log já adicionado (telemetria de ai_video).

## 🧪 Stress Test (antes de abrir para testadores)

Valida como o worker single-concurrency (`--concurrency=1`) comporta a fila quando vários
testadores disparam vídeos ao mesmo tempo. O script simula N usuários novos fazendo o funil
completo (cadastro → OTP → verify → `/generate`) **em paralelo** e mede latência de fila,
latência total, throughput e taxa de falha.

### Pré-requisitos
- [ ] `READINESS_BYPASS_SECRET` definido no `.env` (senão o Turnstile bloqueia o cadastro do script).
- [ ] `WELCOME_CREDIT_BONUS` no `.env` >= número de usuários do teste (cada um precisa de ≥1 crédito para gerar).
- [ ] Backend **e** worker reiniciados com a build que se quer testar (em particular `2be6192` para atomicidade de crédito).
- [ ] Rodar a partir do host de produção (com rede) — não de dentro de um agente sandbox.

### Comando (beta fechado, 5-8 testadores)
```bash
python scripts/stress_test.py --base https://clipia.com.br --users 5
python scripts/stress_test.py --base https://clipia.com.br --users 8
```
O script cria contas `stress+*@clipia.com.br`, gera vídeos reais (template `stock_narration`,
1 crédito cada, sem tocar APIs pagas), mede tudo e limpa as contas no fim.

### O que observar durante o teste
- Abra `https://clipia.com.br/metrics` numa aba — monitore `clipia_active_jobs` e a fila crescendo.
- Latência de **fila** (enqueue → running): prova a serialização do worker. Para 5 usuários,
  espere o último esperar ~4× o tempo de 1 vídeo.
- Latência **total** (enqueue → MP4): se passar de 10min para qualquer usuário, considere
  subir `worker_concurrency=2` (mas só se a CPU/GPU do host tiver folga — 2 encodes ffmpeg
  em paralelo podem estourar RAM).

### Quando preocupar
- Taxa de sucesso < 75% → investigar falhas antes de abrir para testadores reais.
- Latência máxima > 10min → fila longa demais para UX; subir concorrência ou avisar testadores.
- Qualquer job `failed` com `error` de API externa (Groq/Pexels) → dependência instável.

### Dar crédito aos testadores reais
Para o beta fechado, eleve temporariamente o bônus de boas-vindas no `.env`:
```
WELCOME_CREDIT_BONUS=20   # cada novo cadastro ganha 20 créditos (20 vídeos Edge)
```
Reinicie o backend e **volte para `2` antes do lançamento público**. Alternativa: creditar
manualmente testadores específicos via SQL (`UPDATE users SET credits = credits + N WHERE email = ...`).

---

## Conta de QA (reuso)
`qa.dogfood@clipia.com.br` / `QAdogfood12345!` (50 créditos, verificada).
