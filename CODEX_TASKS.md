# ClipIA — Tarefas Adicionais para Codex

Cada secao abaixo e uma tarefa independente. Copie a secao inteira e cole como prompt separado no Codex.

---

## TAREFA 1: Password Reset (Esqueci minha senha)

### Contexto
O ClipIA ja tem email OTP funcionando (SMTP Gmail). Precisa adicionar fluxo de "esqueci minha senha" usando o mesmo mecanismo de OTP.

### Arquivos relevantes
- `app/auth/routes.py` — endpoints de auth (register, login, verify-email, resend-code)
- `app/auth/schemas.py` — Pydantic models com email normalization
- `app/auth/email.py` — send_verification_email (SMTP)
- `app/auth/service.py` — hash_password, verify_password, create_access_token
- `app/db/models.py` — User model (ja tem verification_code e verification_expires)
- `frontend/src/lib/auth.ts` — funcoes de API (login, register, verifyEmail, resendCode)
- `frontend/src/app/auth/verify/page.tsx` — pagina OTP existente (referencia de UI)

### O que implementar

#### Backend (3 novos endpoints)
1. **POST /api/v1/auth/forgot-password** — recebe `{email}`, gera OTP, envia email com template diferente ("Redefinir senha"), rate limit 3/min. Retorna `{"status": "code_sent"}` sempre (mesmo se email nao existe, para nao vazar info).

2. **POST /api/v1/auth/verify-reset-code** — recebe `{email, code}`, valida OTP, retorna `{status: "verified", reset_token: "<JWT com 10min expiry e purpose=reset>"}`. O reset_token e um JWT separado com payload `{"sub": user_id, "purpose": "reset", "exp": 10min}`.

3. **POST /api/v1/auth/reset-password** — recebe `{reset_token, new_password}`, valida JWT (verifica purpose=reset), atualiza password_hash, limpa verification_code. Rate limit 3/min.

#### Schemas
- `ForgotPasswordRequest(email: str)` — com normalize_email
- `VerifyResetCodeRequest(email: str, code: str)` — code min/max 6
- `ResetPasswordRequest(reset_token: str, new_password: str)` — password min 6

#### Email template
- Reutilizar `send_verification_email` mas com subject e body diferentes
- Criar `send_password_reset_email(to_email, code, user_name)` em `app/auth/email.py`
- Template HTML similar ao OTP mas com texto "Redefinicao de senha" em vez de "Verificacao"

#### Frontend
1. **Link "Esqueci minha senha"** na pagina de login (`frontend/src/app/auth/login/page.tsx`)
2. **Pagina `/auth/forgot-password`** — campo email, botao "Enviar codigo"
3. **Pagina `/auth/reset-password?email=X`** — inputs OTP 6 digitos (reutilizar pattern de verify), campo nova senha, botao "Redefinir"
4. Funcoes em `lib/auth.ts`: `forgotPassword(email)`, `verifyResetCode(email, code)`, `resetPassword(token, password)`

#### Testes (tests/test_password_reset.py)
- Forgot password envia email (mock SMTP)
- Forgot password com email inexistente retorna 200 (nao vaza)
- Verify reset code correto retorna reset_token
- Verify reset code errado retorna 400
- Verify reset code expirado retorna 400
- Reset password com token valido muda a senha
- Reset password com token expirado falha
- Reset password com token purpose errado (ex: token de login normal) falha
- Login com nova senha funciona
- Login com senha antiga falha

#### Verificacao
```bash
pytest tests/test_password_reset.py -v
cd frontend && npx tsc --noEmit
```

---

## TAREFA 2: Deep Health Check + Observability

### Contexto
O ClipIA tem apenas `GET /health` que retorna `{"status":"ok"}`. Precisa de health check profundo e metricas basicas para monitoramento.

### Arquivos relevantes
- `app/main.py` — FastAPI app (create_app factory)
- `app/config.py` — settings
- `app/db/engine.py` — async engine e session
- Docker: PostgreSQL na porta 5435, Redis na porta 6382

### O que implementar

#### 1. Deep Health Check — GET /health/deep
Verificar cada dependencia e retornar status individual:
```json
{
  "status": "healthy|degraded|unhealthy",
  "checks": {
    "database": {"status": "up", "latency_ms": 2.3},
    "redis": {"status": "up", "latency_ms": 0.8},
    "storage": {"status": "up", "writable": true, "free_gb": 45.2},
    "celery": {"status": "up", "workers": 1}
  },
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```
- Database: `SELECT 1` com timeout 3s
- Redis: `PING` com timeout 2s
- Storage: verificar que `settings.STORAGE_DIR` existe e e writable, reportar espaco livre
- Celery: `celery_app.control.ping(timeout=2)` — se nenhum worker responde, status="down"
- Status geral: "healthy" se tudo up, "degraded" se celery down, "unhealthy" se DB ou Redis down
- Nao requer auth (para monitoring externo)
- **Cachear resultado por 10s** para nao sobrecarregar com polling frequente

#### 2. Request logging middleware
Criar middleware que loga cada request com:
- Timestamp, method, path, status_code, duration_ms, client_ip, user_id (se autenticado)
- Format: JSON one-liner para facil parsing
- Nao logar /health (noise)
- Nao logar body de requests (seguranca)
- Usar `logging.getLogger("clipia.access")`

#### 3. Metricas basicas — GET /metrics (Prometheus format)
Endpoint simples com contadores:
```
# HELP clipia_requests_total Total requests
# TYPE clipia_requests_total counter
clipia_requests_total{method="POST",path="/api/v1/generate",status="200"} 42
clipia_requests_total{method="POST",path="/api/v1/auth/login",status="401"} 7

# HELP clipia_active_jobs Active jobs by status
# TYPE clipia_active_jobs gauge
clipia_active_jobs{status="queued"} 2
clipia_active_jobs{status="processing"} 1

# HELP clipia_credits_total Total credits transacted
# TYPE clipia_credits_total counter
clipia_credits_total{type="debit"} 150
clipia_credits_total{type="credit"} 200
```
- Usar dicionario in-memory para contadores (nao precisa de prometheus_client lib)
- Middleware incrementa contadores por path+method+status
- Nao requer auth

#### Testes
- test_health_deep.py: mock DB/Redis/Celery up/down, verificar status codes
- test_metrics.py: verificar formato prometheus, contadores incrementam

#### Verificacao
```bash
pytest tests/test_health_deep.py tests/test_metrics.py -v
curl http://localhost:8005/health/deep | python3 -m json.tool
curl http://localhost:8005/metrics
```

---

## TAREFA 3: Cleanup de Dados Orfaos + Storage Management

### Contexto
O ClipIA gera arquivos em `storage/jobs/{id}/` e `storage/output/{id}.mp4`. Jobs que falham ou sao muito antigos acumulam gigas de dados. Precisa de limpeza automatizada.

### Arquivos relevantes
- `app/worker/tasks.py` — pipeline Celery, _fail_job
- `app/worker/celery_app.py` — Celery config
- `app/config.py` — STORAGE_DIR
- `app/utils/files.py` — cleanup_job_dir, get_job_dir, get_output_dir
- `app/db/models.py` — Job model (status, created_at)

### O que implementar

#### 1. Celery beat task — cleanup_old_jobs (diario)
```python
@celery_app.task(name="cleanup_old_jobs")
def cleanup_old_jobs():
    """Remove job files older than 30 days and failed jobs older than 7 days."""
```
- Consultar Postgres: jobs com status="failed" e created_at > 7 dias
- Consultar Postgres: jobs com status in ("completed","editable") e created_at > 30 dias
- Para cada job: remover `storage/jobs/{id}/` e `storage/output/{id}.mp4`
- Atualizar job.video_url = None no Postgres
- NAO deletar o registro do job (manter historico)
- Logar quantidade de espaco liberado
- Enviar resumo por email se > 1GB liberado

#### 2. Celery beat task — cleanup_orphan_files (semanal)
```python
@celery_app.task(name="cleanup_orphan_files")
def cleanup_orphan_files():
    """Remove files in storage that don't have a corresponding job in DB."""
```
- Listar diretorios em `storage/jobs/`
- Para cada dir, verificar se existe job no Postgres
- Se nao existe: remover o diretorio
- Mesma logica para `storage/output/*.mp4`

#### 3. Celery beat schedule
Adicionar ao `celery_app.py`:
```python
celery_app.conf.beat_schedule = {
    "cleanup-old-jobs": {
        "task": "cleanup_old_jobs",
        "schedule": crontab(hour=4, minute=0),  # 4am daily
    },
    "cleanup-orphan-files": {
        "task": "cleanup_orphan_files",
        "schedule": crontab(hour=4, minute=30, day_of_week=0),  # Sunday 4:30am
    },
}
```

#### 4. Endpoint — GET /api/v1/admin/storage-stats (auth required, plan="admin")
```json
{
  "jobs_dir_size_gb": 12.5,
  "output_dir_size_gb": 3.2,
  "total_jobs": 150,
  "failed_jobs": 23,
  "orphan_dirs": 5,
  "oldest_job_days": 45
}
```

#### 5. Storage guard no /generate
Antes de criar novo job, verificar espaco em disco:
```python
import shutil
usage = shutil.disk_usage(settings.STORAGE_DIR)
if usage.free < 5 * 1024**3:  # < 5GB free
    raise HTTPException(503, "Servidor com pouco espaco. Tente novamente mais tarde.")
```

#### Testes
- test_cleanup.py: criar jobs fake, rodar cleanup, verificar que foram removidos
- Verificar que jobs recentes NAO sao removidos
- Verificar que orphan dirs sao detectados e removidos
- Verificar storage guard bloqueia quando disco cheio (mock disk_usage)

#### Verificacao
```bash
pytest tests/test_cleanup.py -v
```

---

## TAREFA 4: Account Management (Perfil + Deletar Conta)

### Contexto
Usuarios nao conseguem editar seu perfil ou deletar conta. Para LGPD/compliance, precisam poder solicitar exclusao de dados.

### Arquivos relevantes
- `app/auth/routes.py` — endpoints de auth
- `app/auth/schemas.py` — schemas
- `app/db/models.py` — User, Job, CreditPurchase (FK relationships)
- `frontend/src/components/dashboard/UserDropdown.tsx` — dropdown do usuario
- `frontend/src/contexts/AuthContext.tsx` — AuthContext

### O que implementar

#### Backend

1. **PATCH /api/v1/auth/me** — atualizar perfil
   - Campos editaveis: `name` (1-255 chars)
   - Nao permite mudar email (evita bypass de verificacao)
   - Requer auth

2. **POST /api/v1/auth/change-password** — mudar senha
   - Recebe `{current_password, new_password}`
   - Valida senha atual
   - new_password min 6 chars
   - Requer auth

3. **POST /api/v1/auth/delete-account** — solicitar exclusao
   - Recebe `{password}` para confirmacao
   - Soft delete: marca `user.plan = "deleted"`, limpa dados pessoais (name → "Deleted User", email → `deleted_{uuid}@removed.clipia.com.br`)
   - Manter jobs e purchases (anonimizados) para integridade contabil
   - Invalidar todos os tokens (mudar password_hash para string aleatoria)
   - Enviar email de confirmacao de exclusao
   - Retorna 200 `{"status": "account_deleted"}`

4. **GET /api/v1/auth/export-data** — exportar dados pessoais (LGPD)
   - Retorna JSON com: user info, jobs (sem arquivos), purchases
   - Formato GDPR/LGPD friendly
   - Requer auth

#### Frontend
1. **Pagina `/dashboard/settings`** — form de perfil (nome), botao mudar senha
2. **Secao "Zona de Perigo"** — botao vermelho "Excluir minha conta" com modal de confirmacao
3. **Link na UserDropdown** para `/dashboard/settings`

#### Testes (tests/test_account_management.py)
- Update name funciona
- Update com nome vazio falha
- Change password com senha atual errada falha
- Change password funciona, login com nova senha funciona
- Delete account anonimiza dados
- Delete account invalida token
- Login apos delete falha
- Export data retorna todas as info do usuario

#### Verificacao
```bash
pytest tests/test_account_management.py -v
cd frontend && npx tsc --noEmit
```

---

## TAREFA 5: Celery Pipeline Resilience + Retry Logic

### Contexto
O pipeline Celery (6 tasks em chain) falha e perde o credito do usuario em casos de erro. Ja tem _fail_job com refund, mas precisa de retry inteligente e melhor observabilidade.

### Arquivos relevantes
- `app/worker/tasks.py` — todas as 7 tasks (generate_script, synthesize_audio, transcribe_audio, fetch_media, compose_video, finalize, rerender_video)
- `app/worker/celery_app.py` — config do Celery
- `app/services/` — scriptwriter, tts, transcriber, media, compositor

### O que implementar

#### 1. Retry automatico com backoff exponencial
Para tasks que podem falhar por razoes transientes:
- `task_fetch_media`: Pexels API pode estar temporariamente indisponivel → retry 3x com backoff (10s, 30s, 60s)
- `task_synthesize_audio`: Edge TTS pode falhar por rede → retry 2x com backoff (5s, 15s)
- `task_generate_script`: Claude API pode dar rate limit → retry 2x com backoff (10s, 30s)

Implementar usando `self.retry(exc=e, countdown=backoff, max_retries=N)` do Celery.

NAO fazer retry em:
- `task_transcribe_audio` (GPU, Whisper — se falha, e problema real)
- `task_compose_video` (FFmpeg — se falha, e problema real)
- `task_finalize` (file copy — se falha, e problema de disco)

#### 2. Progress tracking granular
Atualizar Redis com mais detalhe durante cada task:
```python
_update_job(job_id, "processing", "scripting", 0.1, detail="Gerando roteiro com IA...")
_update_job(job_id, "processing", "tts", 0.25, detail="Sintetizando narracao...")
_update_job(job_id, "processing", "tts", 0.35, detail="Validando audio...")
_update_job(job_id, "processing", "transcribing", 0.45, detail="Transcrevendo com Whisper...")
_update_job(job_id, "processing", "media", 0.55, detail="Buscando videos (cena 1/3)...")
_update_job(job_id, "processing", "compositing", 0.7, detail="Montando video com FFmpeg...")
_update_job(job_id, "processing", "finalizing", 0.95, detail="Salvando video final...")
```
Adicionar campo `detail` no Redis hash do job.

#### 3. Timeout handling
- Se `task_soft_time_limit` (240s) e atingido, capturar `SoftTimeLimitExceeded` e:
  - Logar qual task excedeu
  - Marcar job como error com mensagem clara: "Video demorou demais para gerar. Tente novamente."
  - Refundar credito

#### 4. Job cancellation
- Novo endpoint: **POST /api/v1/jobs/{job_id}/cancel** (auth required)
- Setar flag no Redis: `job:{id}:cancelled = true`
- Cada task verifica no inicio: `if _redis.get(f"job:{job_id}:cancelled"): return`
- Se cancelado: refundar credito, limpar arquivos, marcar status="cancelled"

#### 5. Dead letter queue
Jobs que falham 3x (apos retries) devem:
- Ir para uma "fila de revisao" no Redis: `SET failed_jobs:{id} {timestamp}`
- Log level ERROR com stacktrace completo
- Email de alerta para admin (se SMTP configurado)

#### Testes (tests/test_pipeline_resilience.py)
- Mock task que falha 1x e sucede na 2a → verificar retry
- Mock task que falha 3x → verificar que para de tentar e refunda
- Soft time limit → verificar refund e mensagem
- Job cancellation → verificar que para e refunda
- Progress detail → verificar que Redis tem campo detail

#### Verificacao
```bash
pytest tests/test_pipeline_resilience.py -v
```

---

## TAREFA 6: Frontend Error Boundaries + Loading States + Offline Handling

### Contexto
O frontend Next.js nao tem tratamento de erros robusto. Requests que falham mostram tela branca ou mensagens genericas. Precisa de UX resiliente.

### Arquivos relevantes
- `frontend/src/app/layout.tsx` — root layout
- `frontend/src/app/dashboard/page.tsx` — dashboard principal
- `frontend/src/app/editor/[jobId]/page.tsx` — editor Remotion
- `frontend/src/contexts/AuthContext.tsx` — auth state
- `frontend/src/lib/auth.ts` — API calls
- `frontend/src/lib/api.ts` — API calls (generate, jobs)
- `frontend/src/lib/editor-api.ts` — editor API calls
- `frontend/src/components/dashboard/GenerateForm.tsx` — form de geracao

### O que implementar

#### 1. Error Boundary global
Criar `frontend/src/components/ErrorBoundary.tsx`:
- Captura erros React nao-tratados
- Mostra UI amigavel: "Algo deu errado", botao "Recarregar pagina"
- Loga erro no console com stack trace
- Envolver o app inteiro no layout.tsx

#### 2. Toast notification system
Criar `frontend/src/components/Toast.tsx` + `frontend/src/contexts/ToastContext.tsx`:
- Tipos: success (verde), error (vermelho), warning (amarelo), info (azul)
- Auto-dismiss apos 5s (configuravel)
- Stack de toasts (max 3 visiveis)
- Animacao de entrada/saida suave
- Position: bottom-right
- Usar em vez de `setError()` inline nos forms

#### 3. Retry automatico em API calls
Modificar `frontend/src/lib/api.ts` e `editor-api.ts`:
- Criar wrapper `fetchWithRetry(url, options, {maxRetries: 2, backoff: 1000})`
- Retry automatico em: 500, 502, 503, 504, network error
- NAO retry em: 400, 401, 402, 403, 404, 409, 422, 429
- Mostrar toast "Reconectando..." durante retry
- Mostrar toast "Servidor indisponivel" se todos os retries falharem

#### 4. Loading skeletons
Substituir loading spinners por skeletons nos componentes:
- `VideoGrid`: skeleton cards 9:16 com shimmer
- `GenerateForm`: skeleton do form inteiro
- `CreditsBadge`: skeleton pill
- Dashboard page: skeleton completo enquanto carrega

Criar `frontend/src/components/Skeleton.tsx` com variantes: `text`, `card`, `avatar`, `button`

#### 5. Session expiry handling
Em `frontend/src/lib/auth.ts`, no `getMe()`:
- Se retornar 401: limpar token, redirecionar para login
- Mostrar toast "Sua sessao expirou. Faca login novamente."
- No AuthContext: verificar token a cada 5min (polling silencioso)

#### 6. Offline detection
Criar `frontend/src/hooks/useOnlineStatus.ts`:
- Monitorar `navigator.onLine` e eventos `online`/`offline`
- Quando offline: mostrar banner amarelo fixo no topo "Voce esta offline"
- Quando voltar online: toast "Conexao restaurada" + refresh dados

#### Testes
Nao e necessario testes automatizados para frontend nesta tarefa. TypeScript check e suficiente.

#### Verificacao
```bash
cd frontend && npx tsc --noEmit
```
Testar manualmente: desligar backend → tentar gerar video → deve mostrar toast de erro com retry.

---

## Instrucoes gerais para todas as tarefas

1. **Manter compatibilidade**: nao quebrar funcionalidade existente
2. **Seguir patterns existentes**: olhar como o codigo atual faz antes de criar algo novo
3. **Importar do lugar certo**: `from app.utils.locks import get_lock`, `from app.config import settings`
4. **Email normalization**: todos os emails passam por `.strip().lower()` via Pydantic validators
5. **Async/await**: backend e full async (asyncpg, async sessions)
6. **Testes**: usar a infra de conftest.py existente (client, db_session, verified_user fixtures)
7. **Rodar testes antes de finalizar**: `pytest tests/ -q`
8. **Rodar TypeScript check**: `cd frontend && npx tsc --noEmit`
