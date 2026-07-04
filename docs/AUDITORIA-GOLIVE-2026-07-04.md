# Auditoria Adversarial de Go-Live — ClipIA (2026-07-04)

> Rodada como Tech Lead: workflow multi-agente (5 frentes → verificação adversarial de cada
> achado). **18 achados brutos → 14 confirmados** (4 refutados pela verificação). Baseline:
> 358 testes verdes em `feat/frontend-elevacao`. Foco: go-live **seguro** + integridade da
> **monetização**. Ver [[GO-LIVE-CHECKLIST.md]].

## Método
Cada frente tentou **falsificar os `[x]` do checklist** (validar = quebrar o claim, não bug-hunt
genérico). Cada achado passou por um verificador cético adversarial que só confirmava com evidência
de código. Análise **estática** (sem disparar geração paga). Frentes: pagamento/créditos, auth/abuso,
pipeline/custo, frontend/UX, config/observabilidade.

---

## ✅ BUCKET A — Corrigido nesta sessão (autônomo, testado)

| # | Achado | Sev | Arquivo | Fix |
|---|--------|-----|---------|-----|
| 1 | **Custo descontrolado por nº de cenas** — `ai_video`/`ai_image` cobram crédito FIXO mas custam por cena; LLM podia gerar 30+ cenas (R$300+/dia de queima) | 🔴 crítico | `scriptwriter.py`, `config.py` | Clamp **proporcional à duração** (`max(6, ceil(dur/4))`, teto `MAX_SCENES_PER_VIDEO=40`) — não corta vídeo longo legítimo. +2 testes |
| 2 | **`/generate` debita crédito sem estorno** se o enfileiramento falhar (Celery/Redis down) → paga e job nunca roda | 🔴 crítico | `app/api/routes.py` | try/except + `_refund_credits` + reverte cota diária + marca job `failed`. +1 teste |
| 3 | **`/render` idem** — pior, some crédito sem deixar rastro (job já `completed`) | 🟠 high | `app/api/routes.py` | try/except + refund + restaura `pending_credits` p/ re-tentativa. +1 teste |
| 4 | **login/register + 4 endpoints de conta sem timeout** → spinner trava ~100s até Cloudflare cair | 🟠 high | `frontend/src/lib/auth.ts` | helper `fetchWithTimeout` (15s) em **todas** as chamadas de auth |
| 5 | **Toast "créditos adicionados" prematuro** — webhook é assíncrono, saldo ainda antigo (quebra confiança na compra) | 🟡 medium (blocker) | `dashboard/credits/page.tsx` | Mensagem honesta + polling curto (saldo sobe sozinho) |
| 6 | **Opção "Roteiro avançado" confusa** — placeholder parecia conteúdo real, nada dizia "opcional" | 🟡 UX | `GenerateForm.tsx` | Label "(opcional)" + texto de ajuda + placeholder claramente exemplo |
| 7 | **`/metrics` não expõe jobs falhados/completados** → lançaria cego pra taxa de erro | 🟢 low | `app/observability.py` | Inclui `failed`/`completed` no gauge |

> Nota: o achado "dispatch_pipeline sem try/except" é a **mesma raiz** do #2 — o try/except no
> handler `/generate` já captura a exceção do `apply_async`.

---

## 🔴 BUCKET B — Só você faz (painéis externos / restart com rede)

Estes são o **gate real** do go-live seguro — o código está pronto, faltam os painéis:

- [ ] **Stripe webhook**: criar endpoint no dashboard → copiar `whsec_` p/ `STRIPE_WEBHOOK_SECRET` no `.env`.
- [ ] **MP webhook**: registrar URL no painel MP → copiar assinatura p/ `MP_WEBHOOK_SECRET` no `.env`.
- [ ] **Pix** (Stripe): ativar em Settings → Payments (o código liga sozinho).
- [ ] **`READINESS_BYPASS_SECRET`** no `.env` → destrava o gate `validate_readiness.py`.
- [ ] **Deploy gpt-image**: restart do worker **com rede** → destrava os 2 templates de imagem IA
      (`Drama Histórico`, `Imagens IA`), hoje quebrados.
- [ ] **Restart backend + worker** (com rede) pra pegar os fixes de código desta sessão (Python sem hot-reload).

Depois dos secrets configurados, fazer o **webhook fail-open hardening** (tornar o secret
obrigatório — hoje quebraria prod porque o secret está vazio; por isso está acoplado a este bucket).

---

## 🟠 Precisa da tua decisão

- **Credit farming por email (`+tag`/dot)** 🟠 high (classificado `go_live_blocker`, mas **deferido
  por decisão consciente**): `test+1@gmail`, `test+2@gmail`… não são canonicalizados → contas grátis
  por caixa de entrada.
  - **Já de-riscado pela arquitetura**: conta farmada ganha **2 créditos**, e `ai_video` (o caro)
    custa **30** — a cadeia farming→geração-cara **já está quebrada** pelo gate de crédito. O
    rendimento é vídeo **stock barato** + créditos de referral, não sangria de R$. Por isso é
    seguro adiar (não é o incêndio que o custo-por-cena era).
  - **Fix seguro** (não trivial): **coluna canônica separada** + checagem de colisão no cadastro +
    migração de backfill. **NÃO** canonicalizar in-place no `_normalize_email` — isso quebra login
    de gmail-com-pontos já cadastrado. (Até stripar só `+tag` quebra a mesma classe, população
    menor — não é risco zero.) **Precisa da tua decisão** sobre usuários existentes.
- **Pricing de `ai_video` por duração**: hoje é crédito fixo (30) pra qualquer duração; um vídeo
  de 180s custa ~R$120 de API. O clamp mata o *abuso*, mas vídeo longo legítimo ainda é margem
  fina. Considerar cobrar proporcional à duração.

---

## 🕒 Deferido (não bloqueia go-live)

- **Token não invalidado em troca de senha** (medium): precisa migration (`password_changed_at`).
  Defense-in-depth; só explorável após roubo de token.
- **Celery Beat não sobe (`-B` ausente)** (medium): reaper/cleanup nunca rodam → **bloat de disco**
  (créditos estão protegidos por redelivery automático `task_reject_on_worker_lost`). Adicionar `-B`
  ao script de serviço + estender reaper p/ jobs `processing`.
  - **Interação com o fix #2**: quando `/generate` estorna por falha de enfileiramento, marca o job
    `failed` no Redis mas a linha no Postgres fica `queued` (órfã). Sem o Beat/reaper, essas órfãs
    acumulam. Não é dinheiro (crédito já estornado) nem bloqueador — some quando o reaper subir.

## ✅ Refutados pela verificação adversarial (registro)
- Forjar webhook p/ creditar conta arbitrária → **falso**: fallback via API do provedor revalida.
- Race de lock Stripe pagamento/refund → **falso**: guards de `status` serializam.
- `asyncio.Lock` não serializa multi-worker → **inválido hoje**: roda 1 worker.
- OTP com `random` não-cripto → real mas **mitigado** por rate-limit+expiry (só defense-in-depth).
- Webhook credita conta não-verificada → **correto**: gate de gasto está no `/generate`.
