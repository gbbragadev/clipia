# ClipIA — Hardening Final: Eliminar Gaps de Producao

## Contexto
ClipIA ja tem: auth JWT, email OTP, rate limiting, CORS restrito, MercadoPago prod, 80 testes passando, password reset, health deep, observability, account management, pipeline resilience, error boundaries frontend.

Agora precisa de uma varredura rigorosa para eliminar tudo que um usuario real ou atacante encontraria em 5 minutos. Zero tolerancia a gaps de "vibe coding".

## Stack
- Backend: Python 3.12, FastAPI, Celery, Redis, PostgreSQL (async SQLAlchemy)
- Frontend: Next.js 16, React 19, Tailwind CSS 4
- Auth: JWT HS256, 24h expiry, token em localStorage
- Base URL: https://clipia.com.br (frontend), https://api.clipia.com.br (backend)

---

## BLOCO 1: Falhas de Autorizacao (CRITICO)

### Endpoints sem autenticacao que DEVERIAM ter

Os seguintes endpoints estao expostos sem auth:

```
GET  /jobs/{job_id}           — QUALQUER pessoa pode ver status de qualquer job
GET  /jobs/{job_id}/download  — QUALQUER pessoa pode baixar qualquer video
GET  /jobs/{job_id}/composition — QUALQUER pessoa pode ver dados do editor
GET  /admin/storage-stats     — QUALQUER pessoa pode ver stats do servidor
```

#### O que fazer:

1. **GET /jobs/{job_id}** — Adicionar `user: User = Depends(get_current_user)` e filtrar por `Job.user_id == user.id`. Se o job nao pertence ao usuario, retornar 404 (nao 403, para nao vazar existencia).

2. **GET /jobs/{job_id}/download** — Mesmo: auth + ownership check. Um usuario NAO pode baixar video de outro.

3. **GET /jobs/{job_id}/composition** — Mesmo: auth + ownership check. Dados do editor sao privados.

4. **GET /admin/storage-stats** — Exigir auth E verificar `user.plan == "admin"`. Se nao admin, retornar 403.

### Testes a adicionar (tests/test_authorization.py)

```python
def test_job_status_requires_auth(client):
    """GET /jobs/{id} sem token retorna 401/403"""

def test_job_status_wrong_user(client, verified_user, other_verified_user):
    """Usuario A nao pode ver job do usuario B"""

def test_download_requires_auth(client):
    """GET /jobs/{id}/download sem token retorna 401/403"""

def test_download_wrong_user(client, verified_user, other_verified_user):
    """Usuario A nao pode baixar video do usuario B"""

def test_composition_requires_auth(client):
    """GET /jobs/{id}/composition sem token retorna 401/403"""

def test_composition_wrong_user(client, verified_user, other_verified_user):
    """Usuario A nao pode ver composicao do usuario B"""

def test_admin_stats_requires_admin(client, verified_user):
    """Usuario normal nao pode acessar /admin/storage-stats"""

def test_admin_stats_works_for_admin(client, admin_user):
    """Admin pode acessar /admin/storage-stats"""
```

Adicionar fixture `other_verified_user` e `admin_user` no conftest.py.

---

## BLOCO 2: Mensagens de Erro que Vazam Info (MEDIO)

### Problema
Varias mensagens de erro estao em ingles ou vazam detalhes internos:

```python
# RUIM: vaza que o job existe mas nao pertence ao usuario
raise HTTPException(status_code=403, detail="Not authorized")

# RUIM: em ingles
raise HTTPException(status_code=404, detail="Job not found")
raise HTTPException(status_code=404, detail="Video not found")
raise HTTPException(status_code=404, detail="Script not found")
raise HTTPException(status_code=404, detail="Composition not found")
raise HTTPException(status_code=404, detail="Job files not found")
raise HTTPException(status_code=404, detail="Job status not found")
raise HTTPException(status_code=422, detail="Invalid job id")
```

### O que fazer

1. Padronizar TODAS as mensagens de erro para pt-BR
2. Mensagens de 404 devem ser genericas: "Recurso nao encontrado" (nao especificar o que nao foi encontrado)
3. Nunca retornar stack traces ou nomes de tabelas/campos ao usuario
4. Criar constantes para mensagens de erro reutilizaveis:

```python
# app/errors.py
class ErrorMessages:
    NOT_FOUND = "Recurso nao encontrado"
    UNAUTHORIZED = "Token invalido ou expirado"
    FORBIDDEN = "Acesso negado"
    INSUFFICIENT_CREDITS = "Creditos insuficientes"
    EMAIL_NOT_VERIFIED = "Verifique seu email antes de continuar"
    RATE_LIMITED = "Muitas tentativas. Aguarde um momento."
    INVALID_INPUT = "Dados invalidos"
    SERVER_ERROR = "Erro interno. Tente novamente."
    DISK_FULL = "Servidor temporariamente indisponivel. Tente mais tarde."
```

5. Adicionar exception handler global no FastAPI para capturar excecoes nao-tratadas e retornar mensagem generica (nunca stack trace):

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": ErrorMessages.SERVER_ERROR})
```

---

## BLOCO 3: Input Validation Gaps (MEDIO)

### Verificar e corrigir TODOS os endpoints

1. **POST /generate** — `topic` deve ter min_length=10, max_length=500. `style` deve ser um de ["educational", "storytelling", "news", "comedy"]. `duration_target` entre 15 e 180. `template_id` deve existir no TEMPLATES dict.

2. **POST /jobs/{job_id}/edit** — `editor_state` e um dict JSONB arbitrario. Colocar limite de tamanho maximo (ex: 500KB) para evitar payload bomb:
```python
body = await request.body()
if len(body) > 512_000:
    raise HTTPException(413, "Payload muito grande")
```

3. **POST /jobs/{job_id}/regenerate-tts** — `voice_id` deve ser um dos voices validos. `rate` entre -50 e 50. `pitch` entre -50 e 50. `text` max 5000 chars.

4. **POST /jobs/{job_id}/ai-suggest** — `message` max 1000 chars. `context` max 100KB.

5. **POST /waitlist** — `email` deve ser validado (mesmo validator dos schemas de auth).

6. **Path params** — Todos os `{job_id}` devem ser validados como UUID. Adicionar helper:
```python
def validate_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(422, ErrorMessages.INVALID_INPUT)
```

### Testes a adicionar (tests/test_input_validation.py)

```python
def test_generate_topic_too_short(auth_client):
    """Topic < 10 chars retorna 422"""

def test_generate_invalid_style(auth_client):
    """Style invalido retorna 422"""

def test_generate_duration_out_of_range(auth_client):
    """Duration < 15 ou > 180 retorna 422"""

def test_generate_invalid_template(auth_client):
    """Template inexistente retorna 422"""

def test_edit_payload_too_large(auth_client):
    """Editor state > 500KB retorna 413"""

def test_invalid_uuid_in_path(client):
    """/jobs/not-a-uuid retorna 422"""

def test_waitlist_invalid_email(client):
    """Email invalido na waitlist retorna 422"""

def test_tts_invalid_voice(auth_client):
    """Voice ID inexistente retorna 422"""

def test_ai_suggest_message_too_long(auth_client):
    """Message > 1000 chars retorna 422"""
```

---

## BLOCO 4: Frontend Robustness (MEDIO)

### 4.1 API calls sem auth que deveriam ter

```typescript
// frontend/src/lib/api.ts linha 38
const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
// ^ SEM Authorization header! Vai falhar agora que adicionamos auth no backend
```

Varrer TODOS os arquivos em `frontend/src/lib/` e `frontend/src/contexts/` — garantir que toda chamada a endpoint protegido inclui o header `Authorization: Bearer ${token}`.

Endpoints que precisam de auth:
- GET /jobs/{id}
- GET /jobs/{id}/download
- GET /jobs/{id}/status
- GET /jobs/{id}/composition
- GET /jobs
- POST /generate
- POST /jobs/{id}/edit
- POST /jobs/{id}/regenerate-tts
- POST /jobs/{id}/ai-suggest
- POST /jobs/{id}/render
- POST /jobs/{id}/reset
- GET /credits/packages
- POST /credits/checkout
- GET /credits/history

Endpoints que NAO precisam de auth:
- POST /auth/register
- POST /auth/login
- POST /auth/verify-email
- POST /auth/resend-code
- POST /auth/forgot-password
- POST /auth/verify-reset-code
- POST /auth/reset-password
- POST /waitlist
- GET /templates
- GET /health

### 4.2 Session expiry sem feedback

Se o token JWT expira enquanto o usuario esta usando o app:
- Chamadas API retornam 401
- O usuario ve erro generico sem entender o que aconteceu

Garantir que em `AuthContext.tsx` ou num interceptor global:
- Se qualquer chamada API retornar 401 → limpar token → redirecionar para /auth/login
- Mostrar toast "Sua sessao expirou. Faca login novamente."
- NAO redirecionar se ja esta numa pagina de auth

### 4.3 localStorage SSR safety

Varrer todos os acessos a `localStorage` e garantir que tem guard de SSR:
```typescript
if (typeof window === "undefined") return null; // ou fallback
```

Arquivos que acessam localStorage fora de auth.ts:
- `WaitlistForm.tsx` (linhas 10, 27, 30)
- `ThemeToggle.tsx` (linhas 9, 17, 22)

Adicionar guards SSR nesses arquivos.

### 4.4 Empty states e loading states

Verificar que TODOS estes componentes tem:
- Loading state (skeleton ou spinner) enquanto dados carregam
- Empty state (mensagem amigavel) quando nao tem dados
- Error state (mensagem + botao retry) quando request falha

Componentes a verificar:
- `PurchaseHistory.tsx` — lista de compras vazia
- `VideoGrid.tsx` — sem videos
- `credits/page.tsx` — pacotes carregando
- `AIAssistant.tsx` — sem mensagens
- `EditorLayout.tsx` — composicao carregando

---

## BLOCO 5: Database Safety (BAIXO)

### 5.1 Migration para production

Verificar que Alembic esta configurado para rodar em producao:
```bash
alembic upgrade head
```
Deve funcionar sem erro com o banco de producao.

### 5.2 Indexes faltando

Verificar se esses campos tem index (consultas frequentes):
```sql
-- Usado em toda query de listagem
SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC;
-- Precisa: INDEX(user_id, created_at DESC)

-- Usado no webhook
SELECT * FROM credit_purchases WHERE id = ?;
-- OK: id e PK

-- Usado no login
SELECT * FROM users WHERE email = ?;
-- OK: ja tem index (unique constraint)
```

Se `jobs.user_id` nao tem index, criar migration:
```python
op.create_index('ix_jobs_user_id_created', 'jobs', ['user_id', sa.text('created_at DESC')])
```

### 5.3 Connection pool limits

Verificar que o engine async tem pool limits razoaveis:
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,       # maximo 10 conexoes
    max_overflow=5,     # +5 em pico
    pool_timeout=30,    # esperar max 30s por conexao
    pool_recycle=3600,  # reciclar conexoes a cada 1h
)
```

---

## BLOCO 6: Testes de Integracao Faltantes (MEDIO)

### Fluxos E2E que devem ter teste

Criar `tests/test_e2e_flows.py`:

```python
async def test_full_registration_flow(client, db_session):
    """Register → verify email → /me shows verified with 2 credits"""

async def test_generate_requires_verified_and_credits(client, db_session):
    """Unverified user cant generate. Verified with 0 credits cant generate. Verified with credits can."""

async def test_payment_flow(client, db_session, mock_mp):
    """List packages → checkout → simulate webhook → credits increased"""

async def test_password_reset_flow(client, db_session, mock_smtp):
    """Forgot password → get OTP → verify code → reset password → login with new password"""

async def test_account_deletion_flow(client, db_session):
    """Login → delete account → login again fails → data anonymized"""

async def test_job_lifecycle(client, db_session, mock_celery):
    """Generate → check status → download → edit → render"""

async def test_credit_debit_consistency(client, db_session, mock_celery):
    """Start with 5 credits → generate 3 videos → 2 credits remaining. No off-by-one."""

async def test_session_isolation(client, db_session):
    """User A creates job. User B cannot see/edit/download it."""
```

Cada teste deve:
- Usar o test client real (nao mocks de endpoint)
- Verificar estado do banco apos cada step
- Verificar response bodies completamente
- Testar o fluxo inteiro, nao steps isolados

---

## BLOCO 7: Checklist de Producao

Implementar verificacoes automaticas que rodamos antes de deploy:

Criar `scripts/production_check.py`:

```python
#!/usr/bin/env python3
"""Pre-production checklist. Run before every deploy."""
import os, sys

checks = []

def check(name, condition, fix=""):
    status = "PASS" if condition else "FAIL"
    checks.append((name, status, fix))
    print(f"  [{status}] {name}")
    if not condition and fix:
        print(f"         Fix: {fix}")

# Security
check("JWT_SECRET is not default",
    os.getenv("JWT_SECRET", "dev-secret") != "dev-secret-change-in-production",
    "openssl rand -hex 32 > .env JWT_SECRET")

check("JWT_SECRET is long enough",
    len(os.getenv("JWT_SECRET", "")) >= 32,
    "Use at least 32 bytes (64 hex chars)")

check("CORS is not wildcard",
    os.getenv("CORS_ORIGINS", "*") != "*",
    "Set CORS_ORIGINS to specific domains")

check("MP_WEBHOOK_SECRET is set",
    bool(os.getenv("MP_WEBHOOK_SECRET")),
    "Get webhook secret from MercadoPago dashboard")

check("MP_ACCESS_TOKEN is production",
    "APP_USR" in os.getenv("MP_ACCESS_TOKEN", "") and "sandbox" not in os.getenv("MP_ACCESS_TOKEN", "").lower(),
    "Use production access token, not sandbox")

check("SMTP is configured",
    bool(os.getenv("SMTP_HOST")),
    "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD")

check("FRONTEND_URL is HTTPS",
    os.getenv("FRONTEND_URL", "").startswith("https://"),
    "Set FRONTEND_URL=https://clipia.com.br")

check("BACKEND_URL is HTTPS",
    os.getenv("BACKEND_URL", "").startswith("https://"),
    "Set BACKEND_URL=https://api.clipia.com.br")

check("DEBUG mode is off",
    os.getenv("DEBUG", "false").lower() != "true",
    "Remove DEBUG=true from .env")

check(".env is not in git",
    not os.path.exists(".env") or os.system("git ls-files --error-unmatch .env 2>/dev/null") != 0,
    "Add .env to .gitignore")

# Database
check("DATABASE_URL uses SSL or is localhost",
    "localhost" in os.getenv("DATABASE_URL", "") or "sslmode" in os.getenv("DATABASE_URL", ""),
    "Add ?sslmode=require for remote databases")

# Summary
failed = sum(1 for _, s, _ in checks if s == "FAIL")
total = len(checks)
print(f"\n{'='*50}")
print(f"  {total - failed}/{total} checks passed")
if failed:
    print(f"  {failed} FAILED — fix before deploy!")
    sys.exit(1)
else:
    print("  All clear for production!")
```

---

## Instrucoes

1. Implementar TODOS os 7 blocos
2. Cada bloco deve ter seus testes
3. Rodar `pytest tests/ -q` — todos os testes existentes + novos devem passar
4. Rodar `cd frontend && npx tsc --noEmit` — zero erros
5. NAO quebrar funcionalidade existente
6. Seguir patterns do codigo existente (locks, auth dependencies, error handling)
7. Mensagens de erro SEMPRE em pt-BR

## Verificacao final
```bash
source .venv/bin/activate
pytest tests/ -v --tb=short
cd frontend && npx tsc --noEmit
python scripts/production_check.py
```
