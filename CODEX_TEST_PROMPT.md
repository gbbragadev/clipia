# ClipIA — Prompt de Testes Rigorosos para Codex

## Contexto do Projeto

ClipIA e uma plataforma SaaS de geracao automatizada de videos curtos (Shorts/Reels/TikTok) com IA.

### Stack
- **Backend**: Python 3.12, FastAPI, Celery, Redis, PostgreSQL (async SQLAlchemy + Alembic)
- **Frontend**: Next.js 16, React 19, Remotion 4, Tailwind CSS 4
- **Auth**: JWT (HS256, 24h expiry), token no localStorage como `clipia_token`
- **Pagamentos**: MercadoPago SDK (webhook com validacao HMAC-SHA256)
- **Rate Limiting**: slowapi (5/min auth, 10/min generate, 60/min default)
- **Email**: SMTP via Gmail (OTP 6 digitos, 10min expiry)
- **GPU**: RTX 3090 para Whisper (transcricao)

### Arquitetura
```
Registro → Email OTP → Verificacao → 2 creditos gratis
Gerar video: 1 credito (Celery pipeline: script→TTS→transcribe→media→compose→finalize)
Editor Remotion: preview 9:16, edicao inline, AI suggest (0.5 credito)
Pagamento: MercadoPago checkout → webhook → credita usuario
```

### Banco de dados (PostgreSQL)
- `users`: id (UUID), email (unique), name, password_hash, credits (int, default 0), plan, email_verified (bool), verification_code, verification_expires, created_at
- `jobs`: id (UUID), user_id (FK→users), topic, style, duration_target, template_id, status, progress, current_step, error, video_url, script (JSONB), editor_state (JSONB), pending_credits (float), created_at, completed_at, exported_at
- `credit_purchases`: id (UUID), user_id (FK→users), package_name, credits_amount, price_brl (centavos), mp_payment_id, mp_preference_id, status, created_at, paid_at
- `waitlist`: id (serial), email (unique), created_at

### Endpoints principais
```
POST /api/v1/auth/register      — cria usuario (credits=0, email_verified=false, envia OTP)
POST /api/v1/auth/login         — retorna JWT
POST /api/v1/auth/verify-email  — valida OTP, da 2 creditos
POST /api/v1/auth/resend-code   — reenvia OTP (rate: 3/min)
GET  /api/v1/auth/me            — retorna usuario autenticado

POST /api/v1/generate           — gera video (1 credito, requer email_verified)
GET  /api/v1/jobs/{id}          — status do job (Redis)
GET  /api/v1/jobs/{id}/status   — status rapido (Redis, requer auth)
GET  /api/v1/jobs               — lista jobs do usuario
GET  /api/v1/jobs/{id}/download — download do video
GET  /api/v1/jobs/{id}/composition — dados do editor Remotion
POST /api/v1/jobs/{id}/edit     — salva estado do editor
POST /api/v1/jobs/{id}/regenerate-tts — regera narracao
POST /api/v1/jobs/{id}/ai-suggest — sugestao IA (0.5 credito acumulado)
POST /api/v1/jobs/{id}/render   — re-render com edicoes (cobra pending_credits)
POST /api/v1/jobs/{id}/reset    — reseta job (1 credito)

GET  /api/v1/credits/packages   — lista pacotes
POST /api/v1/credits/checkout   — cria checkout MercadoPago
GET  /api/v1/credits/history    — historico de compras
POST /api/v1/webhooks/mercadopago — webhook de pagamento

GET  /api/v1/templates          — lista templates de video
POST /api/v1/waitlist           — cadastro na waitlist
GET  /health                    — health check
```

### Configuracao de testes
- pytest + pytest-asyncio (asyncio_mode = "auto")
- conftest.py existente em tests/
- Database de teste: usar mesma URL mas com transactions rollback, ou SQLite in-memory
- Redis: mockar com fakeredis ou mockar _redis diretamente
- Celery tasks: sempre mockar dispatch_pipeline e task_rerender_video
- SMTP: mockar send_verification_email
- MercadoPago SDK: mockar sdk.preference().create e sdk.payment().get

---

## TAREFA: Escrever Suite de Testes Completa

Crie uma suite de testes abrangente e rigorosa no diretorio `tests/`. Cada arquivo de teste deve ser independente. Use fixtures do pytest para setup/teardown. Todos os testes devem rodar sem dependencias externas (sem GPU, sem Redis real, sem Postgres real se possivel — use mocks ou test database).

### Estrutura de arquivos a criar:

```
tests/
├── conftest.py              (MODIFICAR: adicionar fixtures de DB, users, auth)
├── test_auth_security.py    (NOVO)
├── test_email_otp.py        (NOVO)
├── test_credits_integrity.py (NOVO)
├── test_concurrent_usage.py (NOVO)
├── test_payment_webhook.py  (NOVO)
├── test_error_resilience.py (NOVO)
├── test_rate_limiting.py    (NOVO)
├── test_data_consistency.py (NOVO)
└── test_edge_cases.py       (NOVO)
```

---

## 1. test_auth_security.py — Seguranca de Autenticacao

Testar TODAS as seguintes vulnerabilidades e cenarios:

### JWT
- Token expirado retorna 401
- Token com secret errado retorna 401
- Token com payload malformado (sem "sub") retorna 401
- Token vazio retorna 401/403
- Token com user_id inexistente no banco retorna 401
- Token valido retorna usuario correto
- Nao aceitar tokens assinados com algoritmo "none" (JWT alg none attack)
- Nao aceitar tokens assinados com RS256 quando espera HS256

### Senhas
- Senha e armazenada como bcrypt hash, nunca em plaintext
- Login com senha errada retorna 401
- Login com email inexistente retorna 401 (mesma mensagem, sem vazamento)
- Registro com email duplicado retorna 409
- Senha com menos de 6 chars e rejeitada (se validacao existe)

### Endpoints protegidos
- Todos os endpoints que requerem auth retornam 401 sem token
- GET /me, POST /generate, POST /edit, GET /jobs, POST /checkout, GET /history — todos precisam de auth
- Webhook do MercadoPago NAO requer auth (e publico, mas valida assinatura)

### CORS
- Verificar que middleware CORS esta configurado com origens restritas
- Origin nao-autorizada nao recebe header Access-Control-Allow-Origin

---

## 2. test_email_otp.py — Fluxo de Verificacao por Email

### Fluxo feliz
- Registro cria usuario com credits=0, email_verified=false
- OTP e gerado (6 digitos numericos)
- Verificacao com codigo correto: email_verified=true, credits=2
- Apos verificacao, codigo e limpo do banco (verification_code=null)

### Seguranca OTP
- Codigo errado retorna 400 "Codigo incorreto"
- Codigo expirado retorna 400 "Codigo expirado"
- Email inexistente retorna 404
- Usuario ja verificado retorna "already_verified" (idempotente)
- Nao aceitar codigo de outro usuario (OTP isolation)
- Brute force: testar que rate limit 5/min funciona no verify-email
- Resend-code gera novo codigo (antigo invalida)
- Resend-code tem rate limit 3/min

### Timing attacks
- Verificacao nao deve vazar se email existe ou nao pelo tempo de resposta (idealmente)

### Verificacao bloqueia geracao
- Usuario nao-verificado com credits>0 NAO consegue gerar video (403)
- Usuario verificado com credits>0 CONSEGUE gerar video

---

## 3. test_credits_integrity.py — Integridade de Creditos

### Atomicidade
- Gerar video debita exatamente 1 credito
- AI suggest acumula exatamente 0.5 em pending_credits no job
- Reset job debita exatamente 1 credito e zera pending_credits
- Render debita pending_credits do usuario e zera no job
- Verificacao de email credita exatamente 2 creditos (nao 1, nao 3)

### Saldo insuficiente
- Gerar com 0 creditos retorna 402
- Reset com 0 creditos retorna 402
- Render com pending_credits > user.credits retorna 402
- Nenhuma dessas operacoes deve debitar parcialmente (tudo ou nada)

### Consistencia apos falha
- Se o Celery task falha apos debitar credito, o credito NAO e devolvido automaticamente (verificar comportamento atual)
- Se o commit do DB falha apos debitar, a transacao deve fazer rollback completo
- Credits nunca ficam negativos

### Double-spend
- Duas requests simultaneas de /generate com 1 credito restante: apenas 1 deve suceder
- Simular com asyncio.gather ou threads paralelas

---

## 4. test_concurrent_usage.py — Uso Simultaneo

### Race conditions
- 10 requests simultaneas de /generate para usuario com 5 creditos: maximo 5 devem suceder
- 5 requests simultaneas de /verify-email com mesmo codigo: apenas 1 deve creditar
- 3 requests simultaneas de /resend-code: apenas 1 novo codigo deve prevalecer
- 2 requests simultaneas de /render para mesmo job: pending_credits debitado apenas 1x

### Webhook replay
- Mesmo payment_id enviado 2x: creditos creditados apenas 1x (idempotencia)
- 10 webhooks simultaneos com mesmo payment_id: creditos creditados apenas 1x

### Session consistency
- Login retorna token, /me com esse token retorna usuario correto
- Apos verificacao, /me reflete email_verified=true e credits atualizados

---

## 5. test_payment_webhook.py — Pagamento MercadoPago

### Fluxo feliz
- Checkout cria CreditPurchase com status="pending"
- Webhook com payment approved → status="approved", credits creditados
- purchase.paid_at e preenchido
- purchase.mp_payment_id e salvo

### Validacao de assinatura
- Webhook sem header x-signature → rejeitado ("invalid_signature")
- Webhook com assinatura invalida → rejeitado
- Webhook com assinatura valida → processado normalmente
- Construir HMAC corretamente: manifest = "id:{data_id};request-id:{request_id};ts:{ts};"

### Cenarios de erro
- payment_id inexistente no MercadoPago → graceful handling
- external_reference (purchase_id) nao encontrado no banco → log warning, nao crash
- Payment status != "approved" → ignorado, sem creditar
- Webhook com action nao-relevante (ex: "merchant_order") → retorna "ignored"
- Webhook sem payment_id no body → retorna "no_payment_id"

### Pacotes
- Checkout com pacote invalido retorna 400
- Checkout com pacote "starter" cria purchase com credits_amount=10, price_brl=1990
- Checkout com pacote "popular" → 30 creditos, 4990 centavos
- Checkout com pacote "pro" → 100 creditos, 12990 centavos

### Idempotencia
- Webhook aprovado 2x para mesma purchase → credita apenas 1x
- purchase.status ja "approved" → retorna false, nao credita novamente

---

## 6. test_error_resilience.py — Resiliencia a Erros

### Database errors
- Se DB esta indisponivel, endpoints retornam 500 (nao hang)
- Se Redis esta indisponivel, /jobs/{id} retorna 404 ou 500 (nao hang)

### Celery failures
- Se dispatch_pipeline falha, o job e criado mas com status adequado
- Se task intermediaria falha (ex: TTS timeout), Redis marca status="error"

### Malformed requests
- JSON invalido no body retorna 422
- Campos faltando retornam 422 com mensagem clara
- topic com string vazia ou muito curta → validacao rejeita
- UUID invalido no path (/jobs/not-a-uuid) → 404 ou 422

### File system
- Se storage/jobs/{id}/ nao existe, composition retorna 404
- Se narration.wav nao existe, download retorna 404
- Se script.json esta corrompido (JSON invalido), tratar gracefully

### External API failures
- Se MercadoPago API esta fora, checkout retorna erro explicativo
- Se Anthropic API esta fora, ai-suggest retorna erro (nao credita 0.5)
- Se Pexels API falha, pipeline Celery marca erro no job

---

## 7. test_rate_limiting.py — Rate Limiting

### Limites configurados
- POST /auth/register: 5 requests/minuto, 6a retorna 429
- POST /auth/login: 5 requests/minuto, 6a retorna 429
- POST /auth/verify-email: 5 requests/minuto
- POST /auth/resend-code: 3 requests/minuto
- POST /generate: 10 requests/minuto
- Demais endpoints: 60 requests/minuto (default)

### Comportamento do 429
- Response body contem informacao sobre o limite
- Header Retry-After esta presente (ou X-RateLimit-*)
- Rate limit e por IP (get_remote_address)

### Rate limit nao bloqueia outros IPs
- IP A excede limite, IP B continua funcionando

---

## 8. test_data_consistency.py — Consistencia de Dados

### Relacionamentos
- Deletar usuario com jobs → verificar constraint (cascade ou restrict?)
- Deletar usuario com purchases → verificar constraint
- Job sempre tem user_id valido
- Purchase sempre tem user_id valido

### Status transitions
- Job: queued → processing → completed/error (nunca pula etapas no Redis)
- Purchase: pending → approved (nunca pending → pending, approved → pending)
- User email_verified: false → true (nunca true → false)

### JSONB fields
- job.script pode ser null (antes de finalize)
- job.editor_state pode ser null (antes de editar)
- editor_state salvo via /edit e recuperado via /composition
- Script editado no editor persiste entre requests

### Cross-source consistency
- Redis job status e Postgres job status: /jobs endpoint cruza ambos
- Se Redis nao tem o job, usar status do Postgres

---

## 9. test_edge_cases.py — Casos de Borda

### Registro
- Email com maiusculas (Test@Email.com) → tratar como case-insensitive?
- Email com espacos → rejeitar
- Nome com caracteres especiais (acentos, emojis) → aceitar
- Senha exatamente com 6 caracteres → aceitar
- Registro com mesmo email apos delete → verificar comportamento

### OTP
- Codigo "000000" → deve funcionar se for o gerado
- Verificacao no exato momento de expiracao (boundary)
- Resend imediatamente apos register → funciona, gera novo codigo

### Creditos
- Usuario com credits=0 tenta gerar → 402
- Usuario com credits=999999 (overflow?) → aceitar, int do Postgres aguenta
- pending_credits com muitas casas decimais (0.5 + 0.5 + 0.5) → precisao float

### Video pipeline
- Topic com 500 caracteres (limite do campo) → aceitar
- Topic com 501 caracteres → rejeitar ou truncar?
- template_id inexistente → fallback para default ou erro?
- Job de outro usuario: /edit, /render, /reset devem retornar 404 (nao 403, para nao vazar existencia)

### Webhooks
- Webhook com body gigante (1MB+) → nao crashar
- Webhook com Content-Type errado → tratar gracefully
- Webhook com external_reference que nao e UUID valido → log e ignorar

---

## Diretrizes de Implementacao

1. **Cada teste deve ser independente** — nao depender da ordem de execucao
2. **Use fixtures do pytest** para criar/destruir dados de teste
3. **Mock tudo que e externo**: Redis, Celery, SMTP, MercadoPago SDK, Anthropic
4. **Nao usar sleep() nos testes** — usar mocks para simular passagem de tempo
5. **Nomear testes descritivamente**: `test_register_with_duplicate_email_returns_409`
6. **Cada assertion deve ter mensagem explicativa** em caso de falha
7. **Testar tanto o status code quanto o body da response**
8. **Para testes de concorrencia**: usar `asyncio.gather` com httpx.AsyncClient
9. **Marcar testes lentos com `@pytest.mark.slow`**
10. **Coverage target: 90%+ nos modulos auth, payments, api routes**

## Configuracao do conftest.py

O conftest.py deve:
- Criar engine async para test database (SQLite in-memory ou Postgres de teste)
- Criar todas as tabelas no setup
- Fornecer fixtures: `db_session`, `test_client`, `authenticated_client(user)`, `verified_user`, `unverified_user`
- Mockar Redis globalmente com fakeredis ou MagicMock
- Mockar Celery dispatch
- Mockar SMTP (send_verification_email)
- Override da dependency `get_db` para usar session de teste
- Override da dependency `get_current_user` quando necessario
- Limpar dados entre cada teste (transaction rollback)

## Comando para rodar

```bash
cd /home/gui/projects/auto-shorts
source .venv/bin/activate
pip install fakeredis httpx pytest-asyncio
pytest tests/ -v --tb=short -x
```

Para coverage:
```bash
pip install pytest-cov
pytest tests/ -v --cov=app --cov-report=term-missing
```
