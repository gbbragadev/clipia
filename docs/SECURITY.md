# ClipIA — Modelo de Segurança & Runbooks

> Estado em 2026-07-02. Documenta as defesas ativas, os trade-offs assumidos e os
> runbooks de resposta a incidente. Complementa `GO-LIVE-CHECKLIST.md` (alegações)
> e `ROADMAP.md` (produto). Atualizar quando uma defesa mudar de estado.

## Princípio

O deploy **é este checkout** rodando no PC do fundador via Cloudflare Tunnel
(single-machine, SPOF assumido). Tráfego só entra pelo túnel — não há rota direta
ao backend. Toda defesa é desenhada sabendo disso: o IP do cliente vem do header
`CF-Connecting-IP`, e a mídia privada é protegida por URL assinada (o editor
consome `<video src>` sem header de auth).

## Defesas ativas

| Superfície | Defesa | Onde | Estado |
|---|---|---|---|
| **Auth** | JWT HS256, 24h; `clipia_token` no localStorage | `app/auth/service.py` | ✅ |
| **Verificação de e-mail** | OTP via Resend; débito de crédito exige `email_verified` | `app/auth/routes.py` (verify-email) | ✅ |
| **OTP brute-force** | Máx 5 tentativas + expiração por código | `app/auth/routes.py:155` | ✅ |
| **Temp-mail / farming** | Blocklist de 32 domínios descartáveis | `app/auth/disposable.py` | ⚠️ parcial (lista finita) |
| **Anti-bot no cadastro** | Cloudflare Turnstile (server-side) | `app/auth/turnstile.py` | 🔴 **DESLIGADO** (sem chave) |
| **IDOR em jobs** | `get_owned_job` em todo `/jobs/{id}` | `app/api/security.py` | ✅ |
| **Rate-limit** | slowapi por IP real (`CF-Connecting-IP`) | `app/utils/ratelimit.py`, rotas auth/generate | ✅ |
| **Mídia privada** | URL assinada HMAC-SHA256, TTL 7d, `compare_digest` | `app/utils/media_url.py`, middleware `app/main.py` | ✅ (ver trade-off) |
| **Crédito = dinheiro** | `UPDATE … WHERE credits >= cost` atômico; idempotente por `purchase.status` sob lock | `app/api/routes.py:146`, `app/payments/service.py:28` | ✅ |
| **Burn de IA** | `MAX_AI_VIDEO_PER_DAY=3` (vale p/ admin) | `app/config.py:133`, `app/api/routes.py:206` | ✅ |
| **Webhooks** | Stripe: `construct_event` (secret seto); MP: re-busca na API | `app/payments/routes.py` | ✅ Stripe / ⚠️ MP sem registro |
| **Secrets** | Env vars Windows User scope; `.env` só DB/Redis/JWT/SMTP | `.env`, `scripts/check-env.ps1` | ✅ |
| **Disponibilidade** | Auto-restart backend/worker/frontend/tunnel; backup diário | `scripts/_run-*.ps1`, task "ClipIA Backup" | ✅ (uptime externo pendente) |

## Trade-offs assumidos (decisões conscientes)

- **Mídia assinada reusa `JWT_SECRET`** e tem TTL de 7 dias (`media_url.py`). Se o
  `JWT_SECRET` vazar, URLs de mídia podem ser forjadas por uma semana. Aceitável
  hoje (mídia de job não é sensível tipo documento); se mudar, separar
  `MEDIA_SIGNING_SECRET` e encurtar TTL.
- **Turnstile fail-open sem secret**: com a chave vazia (hoje), o cadastro não
  exige captcha. É proposital pra não quebrar o signup antes da chave ser plugada.
  **Ligar é ação do fundador** (ver abaixo).
- **Chargeback clampa em 0** sem ledger (`_revert_once`, `service.py:58`): se o
  usuário gastar antes do estorno, o saldo vai a 0 e o "débito não reversível"
  some sem trilha. Sem double-spend, mas sem auditoria — pendência de produto.
- **Lock de crédito é in-process** (`get_lock`, asyncio). Vale porque o uvicorn é
  single-process. Se um dia rodar múltiplos workers de API, reabre a janela de
  race — documentar como constraint antes de escalar.
- **Idempotência de webhook depende de `purchase.status`**: segundo webhook do
  mesmo pagamento não re-credita. Confirmado por teste (`test_payment_webhook_stripe.py`).

## 🔴 Como LIGAR o Turnstile (ação do fundador — ~10 min)

O código já valida server-side (`app/auth/turnstile.py`); só falta a chave.

1. Painel Cloudflare → **Turnstile** → **Add site**. Domínio: `clipia.com.br`.
   Mode: **Managed** (recomendado).
2. Copiar **Site Key** e **Secret Key**.
3. `.env` (backend): `TURNSTILE_SECRET_KEY=<secret>`.
4. `frontend/.env.local`: `NEXT_PUBLIC_TURNSTILE_SITE_KEY=<site key>`.
5. Rebuild do frontend (`npm run build` — a site key é baked no bundle) e restart.
6. Validar: cadastro **sem** token Turnstile → deve retornar 400 ("Verificação
   anti-bot falhou"). Cadastro normal pelo browser → passa (widget resolve).

Sem esse passo, a barreira anti-farming é só a blocklist de e-mail + 2 créditos
grátis por conta verificada + cap de 3 vídeos-IA/dia.

## Runbook — resposta a abuso (farming de créditos)

Sinais: pico de cadastros, muitos referrals encadeados, IPs repetidos criando
contas. Investigue via SQL (Postgres vivo, `clipia-postgres-1`, user/db `clipia`):

```bash
# Contas criadas hoje
docker exec clipia-postgres-1 psql -U clipia -d clipia -t -c \
  "SELECT email, credits, created_at, referred_by FROM users WHERE created_at::date = CURRENT_DATE ORDER BY created_at DESC;"

# Referrals encadeados suspeitos (>3 indicações de um mesmo usuário)
docker exec clipia-postgres-1 psql -U clipia -d clipia -t -c \
  "SELECT referred_by, COUNT(*) FROM users WHERE referred_by IS NOT NULL GROUP BY referred_by ORDER BY 2 DESC LIMIT 10;"
```

Resposta: banir e-mail (`UPDATE users SET plan='deleted', credits=0, email='deleted_'||id::text||'@removed.clipia.com.br' WHERE email=...`),
adicionar o domínio a `app/auth/disposable.py`, e **ligar Turnstile** se ainda não.

## Runbook — Disaster Recovery (disco/DB corrompido)

Backups: `storage/backups/clipia_<ts>.sql.gz` (diário 02:00, retenção 14d) +
cópia externa via rclone (ação pendente do fundador — o dump local não protege
se o disco pifar).

```bash
# Restore de um backup
docker exec -i clipia-postgres-1 gunzip -c | docker exec -i clipia-postgres-1 psql -U clipia -d clipia < storage/backups/clipia_YYYY-MM-DD_HHMM.sql.gz
# (ajustar: descompactar localmente e pipear psql — validar o comando antes de precisar dele)
```

RPO: até 24h (backup diário). RTO: minutos (restore + restart). Se a máquina
inteira cair,重建 = clone do repo + `start-production.ps1` + restore do backup.

## Runbook — produção cai

1. `curl https://clipia.com.br` → se 530, frontend/backend caídos (tunnel de pé).
2. `! powershell -File scripts\start-production.ps1` **fora do agente** (com rede).
3. Checar `storage/backend.log`, `storage/worker.log`, `storage/frontend.log`.
4. Com auto-restart nos launchers (2026-07-02), um crash isolado não derruba mais
   — só um restart manual se TODOS caírem (reboot da máquina, Docker parado).
5. **Uptime externo** (UptimeRobot batendo `/api/v1/health/deep`) ainda é pendência
   do fundador — é o que transforma "18h caído sem ninguém ver" em alerta imediato.
