# ClipIA — Fase A (Ressurreição Windows) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resuscitar o MVP do ClipIA no PC Windows do Gui (GTX 1660 4GB, Python 3.14, Docker Desktop, Node 24, FFmpeg 8.1) com a única mudança funcional sendo Whisper local (CUDA Linux) → Groq Whisper API. Sistema SaaS mantido vivo mas em modo admin-only (creator-first).

**Architecture:** Stack nativo Windows para processos (Python 3.12 via venv, Node 24 via npm, Cloudflared como Windows service). Docker Desktop só para stateful services (Postgres 16, Redis 7). Transcrição via HTTP para Groq (free tier) com fallback opcional para OpenAI Whisper. Secrets lidos de env vars de User do Windows, não duplicados em `.env` do repo. Serviços de backend/worker/frontend gerenciados por NSSM para auto-start em boot. Backup diário via pg_dump em Task Scheduler.

**Tech Stack:** Python 3.12, FastAPI + uvicorn, Celery, Next.js 16 + Remotion 4, Postgres 16, Redis 7, Docker Desktop, FFmpeg 8.1, NSSM, Cloudflared, Groq Whisper API, ElevenLabs, OpenAI, Anthropic, Pexels.

---

## File Structure

### Files to modify
- `app/services/transcriber.py` — rewrite completo (de faster-whisper local para Groq HTTP)
- `app/worker/gpu_models.py` — desativar `get_whisper_model` e `get_tts_model` (raise NotImplementedError)
- `app/config.py` — adicionar campos `GROQ_API_KEY`, `OPENAI_API_KEY`, `ASR_FALLBACK_ENABLED`, mapear env vars do Windows
- `tests/test_transcriber.py` — reescrever (mocks de HTTP em vez de Whisper local)
- `pyproject.toml` — remover `TTS>=0.22.0` e `faster-whisper>=1.1.0`; adicionar `groq>=0.11.0` e `openai>=1.54.0`
- `docker-compose.yml` — mover `backend` e `worker` para profile `prod`
- `.env.example` — documentar env vars Windows necessárias
- `.gitignore` — adicionar `.venv312/`, `.admin-credentials.local`, `.env.local`
- `CLAUDE.md` — comandos Windows como default; Linux legacy em apêndice
- `frontend/src/components/Navbar.tsx` — esconder link "Criar conta" (se existir)
- `frontend/src/components/hero/HeroSection.tsx` — idem
- `frontend/src/app/auth/register/page.tsx` — manter funcional mas sem link público

### Files to create
- `app/services/transcriber_local.py.bak` — arquivo atual renomeado (preservação histórica)
- `scripts/check-env.ps1` — valida env vars Windows antes de subir stack
- `scripts/start-all.ps1` — orquestra Postgres+Redis+alembic+3 terminais dev
- `scripts/backup-postgres.ps1` — pg_dump agendado diário
- `scripts/seed_admin.py` — cria user admin idempotentemente
- `scripts/install-windows-services.ps1` — instala NSSM + 3 services (backend, worker, frontend)
- `docs/RUN-WINDOWS.md` — runbook testado pelo Gui
- `.env.local` (gitignored) — overrides locais (`ASR_FALLBACK_ENABLED`, etc)
- `.admin-credentials.local` (gitignored) — password admin gerada

---

## Task 0: Preparação e criação de branch de trabalho

**Files:**
- None (só git)

- [ ] **Step 1: Verificar estado atual do repo**

Run:
```bash
git status
git log -1 --oneline
```

Expected: working tree com `deploy-frontend.sh` e `scripts/backup-postgres.sh` modificados e último commit `ec3dff0 docs: add Phase A (Windows resurrection) design spec` na branch `backup/2026-04-15-srv01-final`.

- [ ] **Step 2: Criar branch de trabalho da Fase A**

Run:
```bash
git checkout -b feat/phase-a-windows-resurrection
```

Expected: "Switched to a new branch 'feat/phase-a-windows-resurrection'"

- [ ] **Step 3: Limpar modificações não-relacionadas**

As modificações em `deploy-frontend.sh` e `scripts/backup-postgres.sh` são do snapshot pré-Linux. Vamos descartar (o novo `backup-postgres.ps1` substitui):

Run:
```bash
git checkout -- deploy-frontend.sh scripts/backup-postgres.sh
git status
```

Expected: working tree clean exceto arquivos untracked (`.claude/`, etc). Nada staged.

---

## Task 1: Instalar Python 3.12 side-by-side

**Files:** None (instalação de SO)

- [ ] **Step 1: Baixar instalador oficial**

Abrir navegador em https://www.python.org/downloads/release/python-3128/ — baixar **Windows installer (64-bit)** (Python 3.12.8).

- [ ] **Step 2: Instalar**

Executar o MSI com estas opções:
- **Customize installation**
- Marcar: `pip`, `tcl/tk`, `py launcher`
- Desmarcar: "Add Python 3.12 to PATH" (evita conflito com 3.14 que já está no PATH)
- Install location: `C:\Python312\`
- Install for all users: **não**

- [ ] **Step 3: Validar instalação**

Run PowerShell:
```powershell
C:\Python312\python.exe --version
```

Expected: `Python 3.12.8` (ou versão 3.12.x patch)

- [ ] **Step 4: Commit docs nota (não há código nesse step, apenas vai aparecer no RUN-WINDOWS mais tarde)**

Nenhum commit aqui — isso é setup de SO.

---

## Task 2: Criar venv e instalar dependências

**Files:**
- Create: `.venv312/` (gitignored)
- Modify: `.gitignore` (adicionar `.venv312/`)
- Modify: `pyproject.toml` (remover `TTS`, `faster-whisper`; adicionar `groq`, `openai`)

- [ ] **Step 1: Criar venv com Python 3.12**

Run PowerShell na raiz do repo (`C:\Dev\auto-shorts`):
```powershell
C:\Python312\python.exe -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python --version
```

Expected: `Python 3.12.8`. Prompt com `(.venv312)` à esquerda.

Se ao ativar aparecer erro de execution policy, rodar **uma vez** em PowerShell admin: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (e confirmar).

- [ ] **Step 2: Adicionar `.venv312/` ao `.gitignore`**

Editar `.gitignore` — antes da linha `.venv/` adicionar:
```
.venv312/
.env.local
.admin-credentials.local
```

Arquivo final (`.gitignore` completo):
```
__pycache__/
*.pyc
.env
.env.local
.admin-credentials.local
storage/
*.egg-info/
dist/
.venv/
.venv312/
.pytest_cache/
reference_voices/*.wav
.gstack/
.next/
.playwright-mcp/
.remember/
finalTEMP_MPY_wvf_snd.mp4
```

- [ ] **Step 3: Remover deps ML locais e adicionar Groq+OpenAI no `pyproject.toml`**

Editar `pyproject.toml`, substituir o bloco `dependencies`:

```toml
dependencies = [
    "fastapi[standard]>=0.115.0",
    "uvicorn>=0.34.0",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "anthropic>=0.42.0",
    "groq>=0.11.0",
    "openai>=1.54.0",
    "moviepy>=2.1.0",
    "httpx>=0.28.0",
    "pydantic-settings>=2.7.0",
    "pydub>=0.25.1",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "mercadopago>=2.2.0",
    "slowapi>=0.1.9",
    "elevenlabs>=1.50.0",
]
```

(Removido: `TTS>=0.22.0`, `faster-whisper>=1.1.0`. Adicionado: `groq`, `openai`, `elevenlabs`.)

- [ ] **Step 4: Instalar dependências dev**

Run (venv ativada):
```powershell
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: instala ~80 packages, termina sem erro. Se der erro de build em alguma lib Windows-hostile, anotar e seguir — tratamos na Task 2b se necessário.

- [ ] **Step 5: Instalar pre-commit ferramentas (ruff)**

Run:
```powershell
pip install pre-commit ruff
pre-commit install
```

Expected: `pre-commit installed at .git\hooks\pre-commit`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: swap local ML deps for API clients (groq, openai, elevenlabs)"
```

---

## Task 3: Validar env vars Windows necessárias (check-env.ps1)

**Files:**
- Create: `scripts/check-env.ps1`

- [ ] **Step 1: Criar script de validação**

Criar `scripts/check-env.ps1`:

```powershell
# scripts/check-env.ps1
# Verifica que todas as env vars de User necessárias para ClipIA estão setadas.
# Uso: .\scripts\check-env.ps1

$required = @{
    'ANTHROPIC_API_KEY'        = 'Claude (scripts)'
    'PEXELS_API_KEY'           = 'Stock media'
    'GROQ_API_KEY'             = 'Whisper ASR primário'
    'OPEN_API_CLIPIA_TOKEN'    = 'OpenAI (Whisper fallback + futuro gpt-image)'
    'ELEVEN_LABS_CLIPIA_KEY'   = 'ElevenLabs TTS'
    'CLOUDFLARE_API_TOKEN'     = 'Cloudflare Tunnel'
}

$missing = @()
$ok = @()

foreach ($key in $required.Keys) {
    $val = [Environment]::GetEnvironmentVariable($key, 'User')
    if ([string]::IsNullOrWhiteSpace($val)) {
        $missing += "  - $key ($($required[$key]))"
    } else {
        $ok += "  + $key (len=$($val.Length))"
    }
}

Write-Host ""
Write-Host "=== ClipIA env vars check ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Present:" -ForegroundColor Green
$ok | ForEach-Object { Write-Host $_ -ForegroundColor Green }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "MISSING:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    Write-Host ""
    Write-Host "Criar com (PowerShell em janela nova apos setar):" -ForegroundColor Yellow
    Write-Host "  [Environment]::SetEnvironmentVariable('NOME','VALOR','User')" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Todas as env vars presentes." -ForegroundColor Green
exit 0
```

- [ ] **Step 2: Rodar e confirmar quais faltam**

Run:
```powershell
.\scripts\check-env.ps1
```

Expected: lista quais estão presentes e quais faltam. Exit 1 se alguma faltar.

- [ ] **Step 3: Criar env vars faltantes**

Para cada variável faltante, rodar PowerShell (substituir `<VALOR>`):
```powershell
[Environment]::SetEnvironmentVariable('GROQ_API_KEY', '<VALOR>', 'User')
[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', '<VALOR>', 'User')
[Environment]::SetEnvironmentVariable('PEXELS_API_KEY', '<VALOR>', 'User')
[Environment]::SetEnvironmentVariable('ELEVEN_LABS_CLIPIA_KEY', '<VALOR>', 'User')
```

**Importante:** após setar, **fechar e abrir novo PowerShell** para as vars serem herdadas. Rodar novamente `.\scripts\check-env.ps1` em janela nova.

Se Gui não tiver conta Groq, criar em https://console.groq.com → API Keys → Create → copiar valor.

- [ ] **Step 4: Validação final**

Em PowerShell novo:
```powershell
.\scripts\check-env.ps1
```

Expected: Exit 0, "Todas as env vars presentes."

- [ ] **Step 5: Commit**

```bash
git add scripts/check-env.ps1
git commit -m "feat: add env vars validator script for Windows setup"
```

---

## Task 4: Atualizar `docker-compose.yml` com profile prod

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Adicionar profile `prod` aos serviços `backend` e `worker`**

Substituir o arquivo inteiro `docker-compose.yml` por:

```yaml
# ClipIA local stack
# Dev: "docker compose up postgres redis -d" (sobe só dados)
# Prod futura: "docker compose --profile prod up -d" (sobe tudo)
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: clipia
      POSTGRES_PASSWORD: clipia_dev
      POSTGRES_DB: clipia
    ports:
      - "5435:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clipia"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --appendfsync everysec
    ports:
      - "6382:6379"
    volumes:
      - redisdata:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  backend:
    profiles: ["prod"]
    build: .
    ports:
      - "8005:8005"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./storage:/app/storage
      - ./fonts:/app/fonts

  worker:
    profiles: ["prod"]
    build: .
    command: celery -A app.worker.celery_app worker -l info --concurrency=1
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./storage:/app/storage
      - ./fonts:/app/fonts

volumes:
  pgdata:
  redisdata:
```

- [ ] **Step 2: Subir só dados**

Run:
```powershell
docker compose up postgres redis -d
docker compose ps
```

Expected: dois serviços `running (healthy)`. Se um estiver `starting`, aguardar 20s e rodar `ps` de novo.

- [ ] **Step 3: Validar conexão Postgres**

Run:
```powershell
docker exec auto-shorts-postgres-1 psql -U clipia -c "SELECT version();"
```

Expected: imprime versão `PostgreSQL 16.x on ...`

- [ ] **Step 4: Validar conexão Redis**

Run:
```powershell
docker exec auto-shorts-redis-1 redis-cli ping
```

Expected: `PONG`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: gate backend/worker behind prod profile in compose"
```

---

## Task 5: Atualizar `app/config.py` com campos Groq, OpenAI e fallback

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Escrever teste falhante**

Criar arquivo `tests/test_config_groq_openai.py`:

```python
import os
from unittest.mock import patch

from app.config import Settings


def test_groq_api_key_reads_from_env_var():
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_123"}, clear=False):
        s = Settings()
    assert s.GROQ_API_KEY == "gsk_test_123"


def test_openai_api_key_reads_from_env_var():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test"}, clear=False):
        s = Settings()
    assert s.OPENAI_API_KEY == "sk-proj-test"


def test_asr_fallback_disabled_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASR_FALLBACK_ENABLED", None)
        s = Settings()
    assert s.ASR_FALLBACK_ENABLED is False


def test_asr_fallback_enabled_via_env():
    with patch.dict(os.environ, {"ASR_FALLBACK_ENABLED": "true"}, clear=False):
        s = Settings()
    assert s.ASR_FALLBACK_ENABLED is True
```

- [ ] **Step 2: Rodar teste — deve falhar**

Run:
```powershell
.\.venv312\Scripts\Activate.ps1
pytest tests/test_config_groq_openai.py -v
```

Expected: 4 FAILED com erros tipo `AttributeError: 'Settings' object has no attribute 'GROQ_API_KEY'`.

- [ ] **Step 3: Adicionar fields ao `app/config.py`**

Editar `app/config.py`. Localizar o bloco `# Voice Providers` e substituí-lo + adicionar bloco `# ASR Providers`:

Substituir:
```python
    # Voice Providers
    ELEVENLABS_API_KEY: str = ""
```

Por:
```python
    # Voice Providers
    ELEVENLABS_API_KEY: str = ""

    # ASR Providers (Phase A: remote only — no local Whisper)
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ASR_FALLBACK_ENABLED: bool = False
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"
    OPENAI_WHISPER_MODEL: str = "whisper-1"
```

- [ ] **Step 4: Rodar teste — agora deve passar**

Run:
```powershell
pytest tests/test_config_groq_openai.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Atualizar `validate_production_settings` para avisar sobre Groq**

Localizar a função `validate_production_settings` no final do `config.py` e substituir o laço `for key in (...)` por:

```python
    warn_keys = ("ANTHROPIC_API_KEY", "PEXELS_API_KEY", "GROQ_API_KEY", "ELEVENLABS_API_KEY")
    for key in warn_keys:
        if not getattr(s, key):
            _logger.warning("Config: %s nao configurado — funcionalidade limitada", key)
```

- [ ] **Step 6: Mapear env vars do Windows via `.env.local` (não código)**

As env vars do Gui são `OPEN_API_CLIPIA_TOKEN` e `ELEVEN_LABS_CLIPIA_KEY`, mas o `Settings` espera `OPENAI_API_KEY` e `ELEVENLABS_API_KEY`. Em vez de mapear em código (fica acoplado aos nomes dele), vamos usar `.env.local` como ponte.

Criar `.env.local` (gitignored, não commitar):

```
OPENAI_API_KEY=${OPEN_API_CLIPIA_TOKEN}
ELEVENLABS_API_KEY=${ELEVEN_LABS_CLIPIA_KEY}
```

Hmm — pydantic-settings não faz substituição `${VAR}`. Solução alternativa: setar as vars padrão como alias no User scope:

Run em PowerShell (uma vez, persistente):
```powershell
$openai = [Environment]::GetEnvironmentVariable('OPEN_API_CLIPIA_TOKEN','User')
$eleven = [Environment]::GetEnvironmentVariable('ELEVEN_LABS_CLIPIA_KEY','User')
[Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $openai, 'User')
[Environment]::SetEnvironmentVariable('ELEVENLABS_API_KEY', $eleven, 'User')
```

Depois rodar `.\scripts\check-env.ps1` com `$required` atualizado — adicionar `OPENAI_API_KEY` e `ELEVENLABS_API_KEY` ao hash `$required`.

**Editar `scripts/check-env.ps1`**: substituir o bloco `$required` por:

```powershell
$required = @{
    'ANTHROPIC_API_KEY'    = 'Claude (scripts)'
    'PEXELS_API_KEY'       = 'Stock media'
    'GROQ_API_KEY'         = 'Whisper ASR primario'
    'OPENAI_API_KEY'       = 'OpenAI (Whisper fallback + futuro gpt-image)'
    'ELEVENLABS_API_KEY'   = 'ElevenLabs TTS'
    'CLOUDFLARE_API_TOKEN' = 'Cloudflare Tunnel'
}
```

Rodar:
```powershell
.\scripts\check-env.ps1
```

Expected: Exit 0 com todas presentes. Se faltar `OPENAI_API_KEY` ou `ELEVENLABS_API_KEY`, rodar os SetEnvironmentVariable acima.

- [ ] **Step 7: Commit**

```bash
git add app/config.py tests/test_config_groq_openai.py scripts/check-env.ps1
git commit -m "feat(config): add Groq/OpenAI/ASR_FALLBACK settings with tests"
```

---

## Task 6: Renomear transcriber.py atual para preservação

**Files:**
- Rename: `app/services/transcriber.py` → `app/services/transcriber_local.py.bak`
- Modify: `app/worker/gpu_models.py`

- [ ] **Step 1: Renomear via git**

Run:
```bash
git mv app/services/transcriber.py app/services/transcriber_local.py.bak
```

Expected: status mostra `renamed: app/services/transcriber.py -> app/services/transcriber_local.py.bak`.

- [ ] **Step 2: Desativar `get_whisper_model` e `get_tts_model`**

Substituir o arquivo `app/worker/gpu_models.py` inteiro por:

```python
"""GPU-bound model loaders.

Phase A (Windows pivot): local ASR (Whisper via faster-whisper) and local
TTS (XTTS via TTS) are disabled. Transcription runs via Groq API, TTS via
ElevenLabs/EdgeTTS. These functions are kept as shells so that future phases
can re-enable local models without re-plumbing callers.
"""
from threading import Lock

_tts_model = None
_whisper_model = None
_lock = Lock()


def get_tts_model():
    raise NotImplementedError(
        "Local XTTS TTS disabled in Phase A. Use ElevenLabsProvider or EdgeProvider."
    )


def get_whisper_model():
    raise NotImplementedError(
        "Local faster-whisper disabled in Phase A. Use app.services.transcriber "
        "(Groq API) instead."
    )
```

- [ ] **Step 3: Verificar que o código atual quebra propositalmente**

Run:
```powershell
pytest tests/test_transcriber.py -v
```

Expected: ERROR ou FAILED — o teste existente importa `app.services.transcriber` que não existe mais. Isso é esperado, vamos recriar na Task 7.

- [ ] **Step 4: Commit**

```bash
git add app/services/ app/worker/gpu_models.py
git commit -m "refactor: archive local whisper, disable gpu_models loaders"
```

---

## Task 7: TDD — teste do novo `transcriber.py` com mock de Groq

**Files:**
- Modify: `tests/test_transcriber.py`

- [ ] **Step 1: Reescrever `tests/test_transcriber.py`**

Substituir o arquivo inteiro por:

```python
"""Tests for app.services.transcriber (Phase A: Groq API backend)."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.transcriber import transcribe_with_timestamps


def _groq_response_with_words():
    """Minimal mock of Groq verbose_json response."""
    resp = MagicMock()
    resp.words = [
        MagicMock(word="Voce", start=0.0, end=0.3),
        MagicMock(word="sabia", start=0.3, end=0.7),
        MagicMock(word="disso", start=0.7, end=1.1),
    ]
    return resp


def test_transcribe_returns_word_timestamps(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _groq_response_with_words()

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert len(words) == 3
    assert words[0] == {"word": "Voce", "start": 0.0, "end": 0.3}
    assert words[1] == {"word": "sabia", "start": 0.3, "end": 0.7}
    assert words[2] == {"word": "disso", "start": 0.7, "end": 1.1}


def test_transcribe_strips_whitespace_from_words(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    resp = MagicMock()
    resp.words = [MagicMock(word="  hello  ", start=0.0, end=0.5)]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = resp

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert words[0]["word"] == "hello"


def test_transcribe_raises_when_groq_returns_no_words(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    resp = MagicMock()
    resp.words = []
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = resp

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="empty transcription"):
            transcribe_with_timestamps(str(audio))


def test_transcribe_retries_on_transient_error_then_succeeds(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    call = {"n": 0}

    def _side_effect(**_kwargs):
        call["n"] += 1
        if call["n"] < 3:
            raise ConnectionError("boom")
        return _groq_response_with_words()

    mock_client.audio.transcriptions.create.side_effect = _side_effect
    # Zero backoff for test speed
    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert call["n"] == 3
    assert len(words) == 3


def test_transcribe_raises_after_max_retries(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = ConnectionError("boom")
    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        with pytest.raises(ConnectionError):
            transcribe_with_timestamps(str(audio))
```

- [ ] **Step 2: Rodar — deve falhar (módulo não existe)**

Run:
```powershell
pytest tests/test_transcriber.py -v
```

Expected: 5 ERRORS por `ModuleNotFoundError: No module named 'app.services.transcriber'`.

---

## Task 8: Implementar `transcriber.py` com Groq (passa testes)

**Files:**
- Create: `app/services/transcriber.py`

- [ ] **Step 1: Criar novo `app/services/transcriber.py`**

```python
"""Audio transcription via Groq Whisper API (Phase A: remote ASR only).

Exposes the same public surface as the former local-Whisper implementation:

    transcribe_with_timestamps(audio_path: str) -> list[dict]

Each item: {"word": str, "start": float, "end": float}.
"""
import logging
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = (2, 4, 8)  # 3 attempts total


def _get_groq_client():
    from groq import Groq
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    return Groq(api_key=settings.GROQ_API_KEY)


def _get_openai_client():
    from openai import OpenAI
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _transcribe_groq(audio_path: str) -> list[dict]:
    client = _get_groq_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(Path(audio_path).name, f.read()),
            model=settings.GROQ_WHISPER_MODEL,
            language="pt",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return _parse_response_words(response)


def _transcribe_openai(audio_path: str) -> list[dict]:
    client = _get_openai_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=f,
            model=settings.OPENAI_WHISPER_MODEL,
            language="pt",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return _parse_response_words(response)


def _parse_response_words(response) -> list[dict]:
    """Normalize Groq/OpenAI verbose_json response to our schema."""
    raw_words = getattr(response, "words", None) or []
    words = []
    for w in raw_words:
        word_text = getattr(w, "word", None) or w["word"] if isinstance(w, dict) else w.word
        start = getattr(w, "start", None) or (w["start"] if isinstance(w, dict) else w.start)
        end = getattr(w, "end", None) or (w["end"] if isinstance(w, dict) else w.end)
        text_clean = word_text.strip()
        if text_clean:
            words.append({
                "word": text_clean,
                "start": round(float(start), 3),
                "end": round(float(end), 3),
            })
    if not words:
        raise RuntimeError("empty transcription: no word-level timestamps returned")
    return words


def transcribe_with_timestamps(audio_path: str) -> list[dict]:
    """Transcribe audio file to word-level timestamps.

    Tries Groq first. If ASR_FALLBACK_ENABLED and Groq exhausts retries,
    tries OpenAI Whisper as fallback before raising.
    """
    last_exc: Exception | None = None
    for attempt, backoff in enumerate(_BACKOFF_SECONDS, start=1):
        try:
            words = _transcribe_groq(audio_path)
            if attempt > 1:
                logger.info("Groq transcription succeeded on attempt %d", attempt)
            return words
        except RuntimeError:
            # empty transcription, missing key — do not retry
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Groq transcription attempt %d/%d failed: %s",
                attempt, len(_BACKOFF_SECONDS), exc,
            )
            if attempt < len(_BACKOFF_SECONDS):
                time.sleep(backoff)

    if settings.ASR_FALLBACK_ENABLED:
        logger.warning("Groq exhausted retries; falling back to OpenAI Whisper")
        try:
            return _transcribe_openai(audio_path)
        except Exception as exc:
            logger.error("OpenAI Whisper fallback also failed: %s", exc)
            raise

    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 2: Rodar testes — devem passar**

Run:
```powershell
pytest tests/test_transcriber.py -v
```

Expected: 5 PASSED.

- [ ] **Step 3: Rodar todos os testes pra ver o baseline da suite**

Run:
```powershell
pytest -q 2>&1 | tail -40
```

Expected: maioria passa; se algum falhar por razão não relacionada (ex: teste que esperava `faster-whisper` importável), anotar em issue local mas não bloqueia esta task.

- [ ] **Step 4: Commit**

```bash
git add app/services/transcriber.py tests/test_transcriber.py
git commit -m "feat(asr): replace local whisper with Groq API + optional OpenAI fallback"
```

---

## Task 9: TDD — teste de fallback OpenAI

**Files:**
- Modify: `tests/test_transcriber.py`

- [ ] **Step 1: Adicionar testes de fallback ao final de `tests/test_transcriber.py`**

Adicionar no final do arquivo (após o último teste):

```python
def test_openai_fallback_activates_when_groq_fails_and_flag_enabled(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    groq_client = MagicMock()
    groq_client.audio.transcriptions.create.side_effect = ConnectionError("groq down")

    openai_client = MagicMock()
    openai_client.audio.transcriptions.create.return_value = _groq_response_with_words()

    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr("app.config.settings.ASR_FALLBACK_ENABLED", True)

    with (
        patch("app.services.transcriber._get_groq_client", return_value=groq_client),
        patch("app.services.transcriber._get_openai_client", return_value=openai_client),
    ):
        words = transcribe_with_timestamps(str(audio))

    assert len(words) == 3
    assert openai_client.audio.transcriptions.create.called


def test_openai_fallback_skipped_when_flag_disabled(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    groq_client = MagicMock()
    groq_client.audio.transcriptions.create.side_effect = ConnectionError("groq down")
    openai_client = MagicMock()

    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr("app.config.settings.ASR_FALLBACK_ENABLED", False)

    with (
        patch("app.services.transcriber._get_groq_client", return_value=groq_client),
        patch("app.services.transcriber._get_openai_client", return_value=openai_client),
    ):
        with pytest.raises(ConnectionError):
            transcribe_with_timestamps(str(audio))

    assert not openai_client.audio.transcriptions.create.called
```

- [ ] **Step 2: Rodar — devem passar (implementação já cobre)**

Run:
```powershell
pytest tests/test_transcriber.py -v
```

Expected: 7 PASSED (os 5 anteriores + 2 novos).

- [ ] **Step 3: Commit**

```bash
git add tests/test_transcriber.py
git commit -m "test(asr): cover OpenAI Whisper fallback on/off paths"
```

---

## Task 10: Criar `.env.example` atualizado e `.env` local

**Files:**
- Modify: `.env.example`
- Create: `.env` (gitignored, local)
- Create: `.env.local` (gitignored, overrides)

- [ ] **Step 1: Reescrever `.env.example`**

Substituir `.env.example` inteiro por:

```
# =============================================================================
# ClipIA — .env.example
# Copie para .env e preencha. NUNCA commitar o .env.
# =============================================================================
#
# IMPORTANTE — Segredos: as chaves de API DEVEM vir das variaveis de ambiente
# do Windows (User scope), nao deste arquivo. Ver scripts/check-env.ps1.
# Env vars Windows esperadas:
#   - ANTHROPIC_API_KEY      (Claude scripts)
#   - GROQ_API_KEY           (Whisper primario)
#   - OPENAI_API_KEY         (Whisper fallback + gpt-image futuro)
#   - ELEVENLABS_API_KEY     (TTS premium)
#   - PEXELS_API_KEY         (stock media)
#   - CLOUDFLARE_API_TOKEN   (tunnel)
#
# pydantic-settings le primeiro .env, depois env vars (env vars vencem).
# Neste arquivo deixamos as chaves VAZIAS para nao sobrescrever o User scope.

# --- Local services ---
DATABASE_URL=postgresql+asyncpg://clipia:clipia_dev@localhost:5435/clipia
REDIS_URL=redis://localhost:6382/0
FRONTEND_URL=http://localhost:3003
BACKEND_URL=

# --- Auth ---
JWT_SECRET=<openssl rand -hex 32>
JWT_ALGORITHM=HS256

# --- CORS ---
CORS_ORIGINS=http://localhost:3003,https://autoshorts.gbbragadev.com

# --- ASR fallback ---
# Quando true, apos Groq esgotar retries cai pra OpenAI Whisper (pago).
ASR_FALLBACK_ENABLED=false

# --- Placeholders (nao preencher aqui; usar env vars Windows) ---
ANTHROPIC_API_KEY=
PEXELS_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
ELEVENLABS_API_KEY=

# --- MercadoPago (dormant na Fase A) ---
MP_ACCESS_TOKEN=
MP_WEBHOOK_SECRET=

# --- SMTP (opcional) ---
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@clipia.com.br
```

- [ ] **Step 2: Gerar `.env` local com JWT_SECRET real**

Run:
```powershell
$jwt = python -c "import secrets; print(secrets.token_hex(32))"
@"
DATABASE_URL=postgresql+asyncpg://clipia:clipia_dev@localhost:5435/clipia
REDIS_URL=redis://localhost:6382/0
FRONTEND_URL=http://localhost:3003
JWT_SECRET=$jwt
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:3003,https://autoshorts.gbbragadev.com
ASR_FALLBACK_ENABLED=false
"@ | Out-File -Encoding utf8 .env
Get-Content .env
```

Expected: arquivo `.env` criado com JWT_SECRET aleatório de 64 chars hex.

- [ ] **Step 3: Validar que Settings carrega sem explodir**

Run (venv ativa):
```powershell
python -c "from app.config import settings; print('JWT len:', len(settings.JWT_SECRET)); print('GROQ present:', bool(settings.GROQ_API_KEY))"
```

Expected: `JWT len: 64` e `GROQ present: True` (True se env var do Windows está setada).

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "docs: rewrite .env.example documenting Windows env var handoff"
```

(NÃO commitar `.env`; está gitignored.)

---

## Task 11: Alembic migrate + teste de conexão

**Files:** None (execução apenas)

- [ ] **Step 1: Subir Postgres se não estiver up**

Run:
```powershell
docker compose up postgres -d
docker compose ps postgres
```

Expected: `running (healthy)`.

- [ ] **Step 2: Rodar Alembic upgrade head**

Run (venv ativa, no raiz do repo):
```powershell
alembic upgrade head
```

Expected: múltiplas linhas `Running upgrade ... -> ..., ...` terminando com o head atual. Sem exceções.

- [ ] **Step 3: Listar tabelas criadas**

Run:
```powershell
docker exec auto-shorts-postgres-1 psql -U clipia -d clipia -c "\dt"
```

Expected: lista incluindo `users`, `jobs`, `credit_purchases`, `alembic_version`, etc.

- [ ] **Step 4: Verificar versão de migração**

Run:
```powershell
docker exec auto-shorts-postgres-1 psql -U clipia -d clipia -c "SELECT version_num FROM alembic_version;"
```

Expected: hash bate com `d89117d` (o head atual das migrações).

- [ ] **Step 5: Commit (nenhuma mudança de código; só log de validação)**

Sem commit; validação de infra.

---

## Task 12: Script de seed do admin

**Files:**
- Create: `scripts/seed_admin.py`
- Create: `tests/test_seed_admin.py`

- [ ] **Step 1: TDD — escrever teste falho**

Criar `tests/test_seed_admin.py`:

```python
"""Test the admin seed script idempotency and output."""
import importlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_seed_creates_admin_when_absent(tmp_path, monkeypatch):
    """When no admin user exists, creates one and writes credentials file."""
    cred_file = tmp_path / ".admin-credentials.local"
    monkeypatch.setattr("scripts.seed_admin.CREDENTIALS_PATH", cred_file)

    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("scripts.seed_admin.async_session", return_value=mock_session):
        seed_module = importlib.import_module("scripts.seed_admin")
        await seed_module.seed_admin()

    assert cred_file.exists()
    content = cred_file.read_text()
    assert "admin@gui" in content
    assert "password" in content.lower()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_seed_is_idempotent_when_admin_exists(tmp_path, monkeypatch):
    """When admin already exists, does not recreate and does not write file."""
    cred_file = tmp_path / ".admin-credentials.local"
    monkeypatch.setattr("scripts.seed_admin.CREDENTIALS_PATH", cred_file)

    existing_user = MagicMock()
    existing_user.email = "gbbraga.dev@gmail.com"

    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user)))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("scripts.seed_admin.async_session", return_value=mock_session):
        seed_module = importlib.import_module("scripts.seed_admin")
        await seed_module.seed_admin()

    assert not cred_file.exists()
    mock_session.add.assert_not_called()
```

- [ ] **Step 2: Rodar — deve falhar**

Run:
```powershell
pytest tests/test_seed_admin.py -v
```

Expected: ERRORS por `ModuleNotFoundError: No module named 'scripts.seed_admin'`.

- [ ] **Step 3: Criar `scripts/__init__.py` (marker)**

```powershell
New-Item -ItemType File -Force scripts/__init__.py | Out-Null
```

- [ ] **Step 4: Criar `scripts/seed_admin.py`**

```python
"""Idempotent admin user seeder for Phase A creator-first mode.

Creates user admin@gui (gbbraga.dev@gmail.com) with plan="admin" and a high
credit balance. Password is random, printed to stdout and saved to
.admin-credentials.local (gitignored).

Schema confirmed against app/db/models.py::User (2026-04-22):
- id: UUID (generated)
- email: str (unique)
- name: str (required)
- password_hash: str (required)
- credits: int (default 2)
- plan: str (default "free"; "admin" grants admin access via dependencies.get_current_admin_user)
- email_verified: bool (default False)
"""
import asyncio
import secrets
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.engine import async_session
from app.db.models import User
from app.auth.service import hash_password


ADMIN_EMAIL = "gbbraga.dev@gmail.com"
ADMIN_NAME = "admin@gui"
ADMIN_CREDITS = 999_999
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / ".admin-credentials.local"


async def seed_admin() -> None:
    password = secrets.token_urlsafe(24)
    pwd_hash = hash_password(password)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin {ADMIN_EMAIL} already exists (id={existing.id}); skipping.")
            return

        user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            password_hash=pwd_hash,
            plan="admin",
            credits=ADMIN_CREDITS,
            email_verified=True,
        )
        session.add(user)
        await session.commit()

    CREDENTIALS_PATH.write_text(
        f"email: {ADMIN_EMAIL}\npassword: {password}\n",
        encoding="utf-8",
    )
    print(f"Created admin {ADMIN_EMAIL}")
    print(f"Password written to: {CREDENTIALS_PATH}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
    sys.exit(0)
```

**Sanity check prévio ao rodar (deve bater com o código acima):**

Run:
```powershell
python -c "from app.db.models import User; print([c.name for c in User.__table__.columns])"
python -c "from app.auth.service import hash_password; print(hash_password('x')[:20])"
```

Expected primeiro: lista incluindo `id`, `email`, `name`, `password_hash`, `credits`, `plan`, `email_verified` (confirmado contra o schema em `app/db/models.py:28-48` no commit `ec3dff0`).

Expected segundo: imprime hash começando com `$2b$` (bcrypt).

- [ ] **Step 5: Rodar testes — devem passar**

Run:
```powershell
pytest tests/test_seed_admin.py -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Rodar o seed real**

Run:
```powershell
python scripts/seed_admin.py
```

Expected:
```
Created admin gbbraga.dev@gmail.com
Password written to: C:\Dev\auto-shorts\.admin-credentials.local
```

Rodar segunda vez:
```powershell
python scripts/seed_admin.py
```

Expected: `Admin gbbraga.dev@gmail.com already exists (id=1); skipping.`

- [ ] **Step 7: Salvar password num lugar seguro (fora do repo)**

Abrir `.admin-credentials.local`, copiar password e salvar em um gerenciador de senhas do Gui. O arquivo pode continuar no repo local (gitignored) como backup.

- [ ] **Step 8: Commit**

```bash
git add scripts/seed_admin.py scripts/__init__.py tests/test_seed_admin.py
git commit -m "feat(scripts): idempotent admin seeder for creator-first mode"
```

---

## Task 13: Script start-all.ps1

**Files:**
- Create: `scripts/start-all.ps1`

- [ ] **Step 1: Criar script**

```powershell
# scripts/start-all.ps1
# Orquestra stack dev do ClipIA no Windows.
# Uso: .\scripts\start-all.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "[1/5] Validando env vars..." -ForegroundColor Cyan
& "$PSScriptRoot\check-env.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Env vars faltando. Abortando." -ForegroundColor Red
    exit 1
}

Write-Host "[2/5] Subindo Postgres + Redis..." -ForegroundColor Cyan
Push-Location $root
docker compose up postgres redis -d
$pgHealthy = $false
for ($i = 0; $i -lt 20; $i++) {
    $status = docker compose ps --format json | ConvertFrom-Json
    $pg = $status | Where-Object { $_.Service -eq "postgres" }
    if ($pg -and $pg.Health -eq "healthy") { $pgHealthy = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $pgHealthy) {
    Write-Host "Postgres nao ficou healthy em 40s." -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[3/5] Aplicando migrations..." -ForegroundColor Cyan
& "$root\.venv312\Scripts\python.exe" -m alembic upgrade head

Write-Host "[4/5] Abrindo 3 terminais (backend, worker, frontend)..." -ForegroundColor Cyan

$backendCmd = "cd '$root'; .\.venv312\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8005"
$workerCmd  = "cd '$root'; .\.venv312\Scripts\Activate.ps1; celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo"
$frontCmd   = "cd '$root\frontend'; npm run dev -- -p 3003"

Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit","-Command",$workerCmd
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontCmd

Pop-Location

Write-Host ""
Write-Host "[5/5] Stack subindo." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8005/docs"
Write-Host "  Frontend: http://localhost:3003"
Write-Host "  Admin:    ver .admin-credentials.local"
Write-Host ""
Write-Host "Para subir o tunnel Cloudflare: cloudflared tunnel run clipia-windows"
```

**Nota:** `--pool=solo` no Celery é necessário em Windows porque o default `prefork` não funciona (não tem `fork()`).

- [ ] **Step 2: Rodar**

Run:
```powershell
.\scripts\start-all.ps1
```

Expected: Três janelas PowerShell novas abrem (backend, worker, frontend). Cada uma mostra logs de startup. Depois de ~20s, todos os três estão ouvindo.

- [ ] **Step 3: Validar que responde**

Run em PowerShell diferente:
```powershell
Invoke-WebRequest http://localhost:8005/api/v1/health -UseBasicParsing | Select-Object StatusCode, Content
Invoke-WebRequest http://localhost:3003 -UseBasicParsing | Select-Object StatusCode
```

Expected: `200` em ambos.

- [ ] **Step 4: Commit**

```bash
git add scripts/start-all.ps1
git commit -m "feat(scripts): start-all orchestrator for Windows dev stack"
```

---

## Task 14: Smoke test — gerar 1 vídeo end-to-end

**Files:** None (teste manual)

- [ ] **Step 1: Login via browser**

Abrir http://localhost:3003/auth/login. Usar email `gbbraga.dev@gmail.com` e password do `.admin-credentials.local`.

Expected: redireciona para `/dashboard`.

- [ ] **Step 2: Submeter geração**

No dashboard, preencher:
- Tema: `5 curiosidades sobre o planeta Marte`
- Template: `stock_narration`
- Voz: primeira ElevenLabs disponível

Clicar "Gerar".

- [ ] **Step 3: Acompanhar progresso**

O card do job deve evoluir: `pending` → `processing (generating script)` → `(synthesizing audio)` → `(transcribing)` → `(fetching media)` → `(composing)` → `completed`.

Tempo esperado end-to-end: 2-5 minutos.

- [ ] **Step 4: Baixar e validar o MP4**

Clicar no botão de download. Abrir o `.mp4` baixado em player.

Validação manual:
- [ ] Narração audível e em pt-BR
- [ ] Legendas aparecem sincronizadas com áudio
- [ ] Mídia visual muda ao longo do vídeo
- [ ] Duração entre 30-90s
- [ ] Resolução 1080x1920

- [ ] **Step 5: Ver logs do worker pra confirmar que usou Groq**

Na janela do worker, procurar linha:
```
INFO celery.app.trace Task transcribe_audio[...] succeeded
```

Anteriormente teria mensagens de `faster-whisper` / `ctranslate2` / `cublas`. Se essas **não** aparecerem e o job completar, migração tá OK.

- [ ] **Step 6: Se o vídeo ficou bom, commit nota no CLAUDE.md como validação**

Sem commit de código aqui — só verificação manual. Se **falhar**, retornar à task apropriada para fix.

---

## Task 15: Escrever `docs/RUN-WINDOWS.md`

**Files:**
- Create: `docs/RUN-WINDOWS.md`

- [ ] **Step 1: Criar doc com passos reais já testados**

```markdown
# Rodando ClipIA no Windows

Este doc documenta o setup **exato** usado no PC do Gui em 2026-04-22
(Windows 11, GTX 1660 4GB, Python 3.14 no PATH, Node 24, Docker Desktop,
FFmpeg 8.1 no PATH).

## 1. Pre-requisitos

Software:
- Python 3.12 instalado em `C:\Python312\` (nao adicionar ao PATH)
- Node 24+ (`node --version`)
- Docker Desktop rodando
- FFmpeg 8+ no PATH (`ffmpeg -version`)
- Git

Env vars de User (Painel de Controle > Variaveis de ambiente > do usuario):
- `ANTHROPIC_API_KEY` — Claude
- `GROQ_API_KEY` — https://console.groq.com
- `OPENAI_API_KEY` — sk-proj-... (alias de OPEN_API_CLIPIA_TOKEN)
- `ELEVENLABS_API_KEY` — (alias de ELEVEN_LABS_CLIPIA_KEY)
- `PEXELS_API_KEY` — https://www.pexels.com/api
- `CLOUDFLARE_API_TOKEN`

Validar:
\`\`\`powershell
.\scripts\check-env.ps1
\`\`\`

## 2. Setup inicial (uma unica vez)

\`\`\`powershell
# clone
git clone <url> auto-shorts
cd auto-shorts

# venv Python 3.12
C:\Python312\python.exe -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install

# infra
docker compose up postgres redis -d

# migrations
alembic upgrade head

# admin (idempotente)
python scripts/seed_admin.py
# guardar senha do .admin-credentials.local em gerenciador de senhas

# frontend deps
cd frontend
npm install
cd ..
\`\`\`

## 3. Dia-a-dia dev

\`\`\`powershell
.\scripts\start-all.ps1
\`\`\`

Abre 3 janelas PowerShell (backend, worker, frontend). Para parar, fechar as
3 janelas (ou Ctrl+C em cada).

URLs locais:
- http://localhost:3003 — frontend
- http://localhost:8005/docs — Swagger backend

## 4. Tunnel Cloudflare (acesso externo)

\`\`\`powershell
cloudflared tunnel run clipia-windows
\`\`\`

Mapeamento (arquivo `~\.cloudflared\config.yml` ou via dashboard):
- `autoshorts.gbbragadev.com` -> `http://localhost:3003`
- `api-autoshorts.gbbragadev.com` -> `http://localhost:8005`

Setup inicial do tunnel — ver Task Scheduler ou servico Windows (Task 17 do plano).

## 5. Backup manual e restore

Backup:
\`\`\`powershell
.\scripts\backup-postgres.ps1
\`\`\`

Produz `storage\backups\clipia_YYYY-MM-DD_HHMM.sql.gz`. Retencao 14 dias.

Restore (em caso de desastre):
\`\`\`powershell
gzip -d storage\backups\clipia_2026-04-22_0300.sql.gz
docker compose up postgres -d
Get-Content storage\backups\clipia_2026-04-22_0300.sql | `
    docker exec -i auto-shorts-postgres-1 psql -U clipia -d clipia
\`\`\`

## 6. Troubleshooting

**Celery worker nao aceita tasks:**
Em Windows, default do pool prefork nao funciona. O `start-all.ps1` ja passa
`--pool=solo`. Se rodar celery manual, lembrar:
\`\`\`powershell
celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo
\`\`\`

**Erro "GROQ_API_KEY not configured":**
Env var nao foi herdada. Fechar e abrir novo PowerShell. Ou setar na sessao:
\`\`\`powershell
$env:GROQ_API_KEY = [Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')
\`\`\`

**Postgres nao sobe:**
\`\`\`powershell
docker compose logs postgres | Select-Object -Last 40
\`\`\`

**JWT invalido no login:**
Usuario provavelmente foi criado com JWT_SECRET diferente. Rodar:
\`\`\`powershell
docker exec auto-shorts-postgres-1 psql -U clipia -d clipia -c "DELETE FROM users;"
python scripts/seed_admin.py
\`\`\`

## 7. Ciclo de vida: Fase A -> B -> C

- **A (atual):** ressurreicao Windows, stack rodando, Gui e unico usuario admin.
- **B:** gpt-image-1 como media primaria; novos templates de novelinha.
- **C:** scheduler de canal, auto-upload YouTube.
- **D:** fork (continua creator ou reabre SaaS com showcase).

Cada fase tem spec em `docs/superpowers/specs/` e plano em `docs/superpowers/plans/`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/RUN-WINDOWS.md
git commit -m "docs: add Windows runbook for Phase A"
```

---

## Task 16: Script de backup PostgreSQL para Windows

**Files:**
- Create: `scripts/backup-postgres.ps1`

- [ ] **Step 1: Criar script**

```powershell
# scripts/backup-postgres.ps1
# Backup diario do Postgres ClipIA.
# Uso: .\scripts\backup-postgres.ps1 [-KeepDays 14]
param(
    [int]$KeepDays = 14
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $root "storage\backups"
$container = "auto-shorts-postgres-1"
$date = Get-Date -Format "yyyy-MM-dd_HHmm"
$file = Join-Path $backupDir "clipia_$date.sql.gz"

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

Write-Host "[$(Get-Date -Format o)] Starting ClipIA Postgres backup..."

# pg_dumpall via docker exec, gzip no stream pelo PowerShell
$dump = docker exec $container pg_dumpall -U clipia
if ($LASTEXITCODE -ne 0) {
    Write-Host "pg_dumpall falhou (exit $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

# Gzip
$outStream = [System.IO.File]::Create($file)
$gzip = New-Object System.IO.Compression.GzipStream($outStream, [System.IO.Compression.CompressionMode]::Compress)
$writer = New-Object System.IO.StreamWriter($gzip)
$writer.Write($dump)
$writer.Close()
$gzip.Close()
$outStream.Close()

$size = [math]::Round((Get-Item $file).Length / 1KB, 1)
Write-Host "[$(Get-Date -Format o)] Backup concluido: $file ($size KB)"

# Limpar antigos
Get-ChildItem -Path $backupDir -Filter "clipia_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
    ForEach-Object {
        Write-Host "Removendo backup antigo: $($_.Name)"
        Remove-Item $_.FullName
    }

exit 0
```

- [ ] **Step 2: Testar manualmente**

Run:
```powershell
.\scripts\backup-postgres.ps1
ls storage\backups\
```

Expected: arquivo `clipia_YYYY-MM-DD_HHMM.sql.gz` criado, tamanho > 1 KB.

- [ ] **Step 3: Agendar no Task Scheduler**

Run (PowerShell Admin):
```powershell
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\Dev\auto-shorts\scripts\backup-postgres.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "3:00AM"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType S4U
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask `
    -TaskName "ClipIA-Postgres-Backup" `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description "Daily Postgres backup for ClipIA (gzipped pg_dumpall)."
```

Expected: task registrada; validar via:
```powershell
Get-ScheduledTask -TaskName "ClipIA-Postgres-Backup" | Format-List TaskName, State, NextRunTime
```

- [ ] **Step 4: Forcar execucao uma vez para confirmar**

Run:
```powershell
Start-ScheduledTask -TaskName "ClipIA-Postgres-Backup"
Start-Sleep -Seconds 5
Get-ScheduledTaskInfo -TaskName "ClipIA-Postgres-Backup" | Format-List LastRunTime, LastTaskResult
```

Expected: `LastTaskResult: 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup-postgres.ps1
git commit -m "feat(scripts): Windows-native Postgres backup with retention"
```

---

## Task 17: Tunnel Cloudflare atualizado

**Files:** None (config fora do repo)

- [ ] **Step 1: Instalar cloudflared (se não estiver)**

Run (PowerShell Admin):
```powershell
winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements
```

Ou baixar MSI de https://github.com/cloudflare/cloudflared/releases.

Validar:
```powershell
cloudflared --version
```

- [ ] **Step 2: Autenticar**

Run:
```powershell
cloudflared tunnel login
```

Abrirá navegador. Login com a conta Cloudflare do `gbbragadev.com`. Autorizar o cert no domínio.

- [ ] **Step 3: Listar tunnels existentes**

Run:
```powershell
cloudflared tunnel list
```

Expected: mostra tunnel existente (provavelmente criado pro Linux). Anotar UUID e nome.

- [ ] **Step 4: Criar ou reutilizar tunnel**

**Se já existe um tunnel `clipia-linux` ou similar**, criar novo pra não brigar:
```powershell
cloudflared tunnel create clipia-windows
```

Expected: imprime UUID e caminho de credentials em `~\.cloudflared\<uuid>.json`.

- [ ] **Step 5: Criar `config.yml`**

Criar `%USERPROFILE%\.cloudflared\config.yml`:
```yaml
tunnel: clipia-windows
credentials-file: C:\Users\guibr\.cloudflared\<UUID-que-voce-copiou>.json

ingress:
  - hostname: autoshorts.gbbragadev.com
    service: http://localhost:3003
  - hostname: api-autoshorts.gbbragadev.com
    service: http://localhost:8005
  - service: http_status:404
```

- [ ] **Step 6: Apontar DNS**

Run:
```powershell
cloudflared tunnel route dns clipia-windows autoshorts.gbbragadev.com
cloudflared tunnel route dns clipia-windows api-autoshorts.gbbragadev.com
```

Se já existirem (do tunnel antigo), substituir:
```powershell
cloudflared tunnel route dns --overwrite-dns clipia-windows autoshorts.gbbragadev.com
cloudflared tunnel route dns --overwrite-dns clipia-windows api-autoshorts.gbbragadev.com
```

- [ ] **Step 7: Rodar tunnel e testar**

Em terminal separado (stack dev rodando):
```powershell
cloudflared tunnel run clipia-windows
```

Em outro terminal:
```powershell
Invoke-WebRequest https://autoshorts.gbbragadev.com -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest https://api-autoshorts.gbbragadev.com/api/v1/health -UseBasicParsing | Select-Object StatusCode
```

Expected: `200` em ambos.

- [ ] **Step 8: Instalar cloudflared como serviço**

Run (Admin):
```powershell
cloudflared service install
Start-Service cloudflared
Get-Service cloudflared
```

Expected: `Running`. O serviço usa `~\.cloudflared\config.yml` automaticamente.

- [ ] **Step 9: Commit nota (no RUN-WINDOWS.md já está coberto)**

Sem commit de código; validação.

---

## Task 18: NSSM services para backend, worker, frontend

**Files:**
- Create: `scripts/install-windows-services.ps1`

- [ ] **Step 1: Instalar NSSM**

Run (Admin):
```powershell
winget install --id NSSM.NSSM --accept-source-agreements --accept-package-agreements
nssm --help | Select-Object -First 5
```

Expected: imprime versão do NSSM.

- [ ] **Step 2: Criar script de instalação**

Criar `scripts/install-windows-services.ps1`:

```powershell
# scripts/install-windows-services.ps1
# Instala 3 servicos NSSM: clipia-backend, clipia-worker, clipia-frontend.
# Requer admin. Uso: .\scripts\install-windows-services.ps1

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv312\Scripts\python.exe"
$npmCmd = (Get-Command npm).Source
$logDir = Join-Path $root "storage\service-logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Install-ClipiaService {
    param(
        [string]$Name,
        [string]$Exe,
        [string]$Args,
        [string]$WorkDir
    )
    # Idempotente: remove se existe
    nssm status $Name 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Removendo service existente: $Name"
        nssm stop $Name 2>$null
        nssm remove $Name confirm
    }
    Write-Host "Instalando: $Name"
    nssm install $Name $Exe $Args
    nssm set $Name AppDirectory $WorkDir
    nssm set $Name AppStdout "$logDir\$Name.out.log"
    nssm set $Name AppStderr "$logDir\$Name.err.log"
    nssm set $Name AppRotateFiles 1
    nssm set $Name AppRotateBytes 10485760
    nssm set $Name Start SERVICE_AUTO_START
    # Herdar env vars de User scope
    nssm set $Name AppEnvironmentExtra `
        "PYTHONUNBUFFERED=1"
}

Install-ClipiaService `
    -Name "clipia-backend" `
    -Exe "$pythonExe" `
    -Args "-m uvicorn app.main:app --host 127.0.0.1 --port 8005" `
    -WorkDir $root

Install-ClipiaService `
    -Name "clipia-worker" `
    -Exe "$pythonExe" `
    -Args "-m celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo" `
    -WorkDir $root

Install-ClipiaService `
    -Name "clipia-frontend" `
    -Exe "$npmCmd" `
    -Args "run start -- -p 3003" `
    -WorkDir (Join-Path $root "frontend")

Write-Host ""
Write-Host "Services instalados (ainda NAO iniciados). Para iniciar:" -ForegroundColor Green
Write-Host "  Start-Service clipia-backend,clipia-worker,clipia-frontend"
Write-Host ""
Write-Host "IMPORTANTE: Antes de iniciar o frontend:"
Write-Host "  cd frontend; npm run build"
```

- [ ] **Step 3: Buildar frontend pra prod**

Run:
```powershell
cd frontend
npm run build
cd ..
```

Expected: `.next/` criado com assets produzidos. Sem erro de tipo.

- [ ] **Step 4: Rodar instalador NSSM**

Run (Admin):
```powershell
.\scripts\install-windows-services.ps1
```

Expected: 3 services instalados.

- [ ] **Step 5: Parar stack dev (se estiver up) e iniciar services**

Fechar as 3 janelas PowerShell do `start-all.ps1` (ou Ctrl+C).

Run (Admin):
```powershell
Start-Service clipia-backend, clipia-worker, clipia-frontend
Start-Sleep -Seconds 10
Get-Service clipia-* | Select-Object Name, Status
```

Expected: os 3 em `Running`.

- [ ] **Step 6: Validar que respondem via tunnel**

Run:
```powershell
Invoke-WebRequest https://autoshorts.gbbragadev.com -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest https://api-autoshorts.gbbragadev.com/api/v1/health -UseBasicParsing | Select-Object StatusCode
```

Expected: `200` em ambos.

- [ ] **Step 7: Testar auto-restart**

Reiniciar o PC. Após login, esperar 2 min, rodar:
```powershell
Get-Service clipia-*, cloudflared | Select-Object Name, Status
```

Expected: todos `Running`.

- [ ] **Step 8: Commit**

```bash
git add scripts/install-windows-services.ps1
git commit -m "feat(scripts): NSSM installer for backend/worker/frontend services"
```

---

## Task 19: Esconder registro público (creator-first hardening)

**Files:**
- Modify: `frontend/src/components/Navbar.tsx`
- Modify: `frontend/src/components/hero/HeroSection.tsx`
- Modify: `frontend/src/components/Footer.tsx` (se tiver link)

- [ ] **Step 1: Localizar todos os links para `/auth/register` na landing**

Run:
```bash
grep -rn "auth/register\|Criar conta\|Cadastro" frontend/src/app/page.tsx frontend/src/components/ 2>/dev/null
```

Anotar cada arquivo/linha.

- [ ] **Step 2: Neutralizar links**

Para cada ocorrência em componente renderizado na landing pública (`Navbar`, `Hero`, `Footer`), envolver o elemento em condicional com env flag:

Exemplo — `frontend/src/components/Navbar.tsx` (ajustar path real com base no grep acima):

Se a linha atual é:
```tsx
<Link href="/auth/register">Criar conta</Link>
```

Trocar por:
```tsx
{process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
  <Link href="/auth/register">Criar conta</Link>
)}
```

Fazer o mesmo para `HeroSection.tsx` e qualquer outro componente da landing.

**Não mexer** na página `/auth/register/page.tsx` em si — ela continua funcional (caso precise criar user via URL direta pra teste).

- [ ] **Step 3: Atualizar `frontend/.env.local` (ou equivalente)**

Se Gui quiser liberar cadastro público mais tarde, bastará setar `NEXT_PUBLIC_PUBLIC_SIGNUP=true`. Por default (não setado), `undefined !== "true"` → link escondido.

Não precisa criar `.env.local` agora.

- [ ] **Step 4: Typecheck + build**

Run:
```powershell
cd frontend
npx tsc --noEmit
npm run build
cd ..
```

Expected: `tsc` sem erros; build sucesso.

- [ ] **Step 5: Validar na UI**

Abrir https://autoshorts.gbbragadev.com em janela anônima (sem login). Verificar que:
- Navbar: **sem** link "Criar conta"
- Hero section: **sem** botão "Criar conta grátis"
- Footer: **sem** link de cadastro

Login continua visível (necessário pro Gui entrar).

- [ ] **Step 6: Reiniciar frontend**

Run (Admin):
```powershell
Restart-Service clipia-frontend
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Navbar.tsx frontend/src/components/hero/HeroSection.tsx frontend/src/components/Footer.tsx
git commit -m "feat(landing): hide signup links unless NEXT_PUBLIC_PUBLIC_SIGNUP=true"
```

---

## Task 20: Atualizar `CLAUDE.md` com comandos Windows

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Reescrever o bloco "Comandos"**

No `CLAUDE.md`, localizar:
```markdown
## Comandos
```bash
# Backend (porta 8005, --reload ativo)
cd ~/projects/auto-shorts && source .venv/bin/activate
...
```

Substituir o bloco inteiro `## Comandos` + conteúdo até antes de `## Gotchas importantes` por:

````markdown
## Comandos (Windows — default em 2026-04-22+)

```powershell
# Setup unica vez
C:\Python312\python.exe -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up postgres redis -d
alembic upgrade head
python scripts/seed_admin.py
cd frontend; npm install; cd ..

# Dia-a-dia
.\scripts\start-all.ps1              # sobe backend+worker+frontend+postgres+redis
.\scripts\check-env.ps1              # valida env vars
.\scripts\backup-postgres.ps1        # backup manual

# Testes
.\.venv312\Scripts\Activate.ps1
pytest -q
cd frontend; npx tsc --noEmit
```

## Comandos Linux (legacy — srv01-bc, obsoleto 2026-04-15)

```bash
# Backend
cd ~/projects/auto-shorts && source .venv/bin/activate
uvicorn app.main:app --reload --port 8005

# Worker (CUDA preload)
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1
```
````

- [ ] **Step 2: Adicionar regra de env vars ao bloco "Gotchas"**

No bloco `## Gotchas importantes`, adicionar no topo:

```markdown
- **Secrets via env vars do Windows**: chaves de API ficam em env vars de User (GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY). `.env` do repo tem apenas DATABASE_URL/REDIS_URL/JWT_SECRET. Nunca duplicar chave em `.env`.
- **Whisper via Groq API (Fase A+)**: `app/services/transcriber.py` chama Groq; `transcriber_local.py.bak` preserva a versão antiga. Fallback para OpenAI Whisper ativado via `ASR_FALLBACK_ENABLED=true` no `.env`.
- **Celery em Windows**: worker precisa `--pool=solo` (prefork não funciona sem `fork()`).
```

- [ ] **Step 3: Adicionar bloco de estado atual no topo**

Logar um bloco `## Estado (2026-04-22)` após `## Projeto` e antes de `## Stack`:

```markdown
## Estado (2026-04-22)
- **Fase A completa** (ressurreicao Windows) em `feat/phase-a-windows-resurrection`
- Stack rodando no PC Windows do Gui via NSSM services + cloudflared
- **Creator-first**: SaaS vivo mas sem cadastro publico (`NEXT_PUBLIC_PUBLIC_SIGNUP!="true"`)
- Proxima fase: B — gpt-image-1 + novos templates (novelinha, curiosidade)
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md with Windows-first commands and Phase A state"
```

---

## Task 21: Validação final e PR

**Files:** None (validação)

- [ ] **Step 1: Rodar suite de testes Python**

Run:
```powershell
.\.venv312\Scripts\Activate.ps1
pytest -q 2>&1 | tail -30
```

Expected: maioria passa. Se alguns falharem por motivo não relacionado (ex: teste que esperava `faster-whisper` import), documentar o subset em commit message.

Se mais de 5 testes falharem sem relação óbvia, investigar antes de seguir.

- [ ] **Step 2: TypeScript check**

Run:
```powershell
cd frontend
npx tsc --noEmit
cd ..
```

Expected: sem erros.

- [ ] **Step 3: Gerar 2º vídeo para validar reprodutibilidade**

Login em https://autoshorts.gbbragadev.com, gerar vídeo tema `3 fatos sobre a Segunda Guerra Mundial` com template `story_time`.

Expected: completa em 2-5 min; MP4 reproduz bem.

- [ ] **Step 4: Verificar custo real de APIs**

Abrir:
- https://console.groq.com (Usage) — confirmar que tá abaixo do free tier
- https://platform.openai.com/usage — deve estar $0 se fallback não ativou
- https://elevenlabs.io/subscription — confirmar chars consumidos

Expected: custo acumulado ≤ $2.

- [ ] **Step 5: Revisar `docs/superpowers/specs/2026-04-22-clipia-pivot-phase-a-design.md` seção "Questões em aberto"**

Cada uma das 4 questões deve estar resolvida:
1. Env vars — `check-env.ps1` passa
2. Conta Groq — criada
3. DNS Cloudflare — `https://autoshorts.gbbragadev.com` responde
4. Admin password — em `.admin-credentials.local` + gerenciador de senhas

Se algum item pendente, fechar antes de PR.

- [ ] **Step 6: Atualizar spec com "status: COMPLETED"**

No topo de `docs/superpowers/specs/2026-04-22-clipia-pivot-phase-a-design.md`, trocar:
```
**Status:** Design aprovado, aguardando revisão antes de writing-plans
```

Por:
```
**Status:** COMPLETED — 2026-04-DD (data real)
```

- [ ] **Step 7: Commit final**

```bash
git add docs/superpowers/specs/2026-04-22-clipia-pivot-phase-a-design.md
git commit -m "docs: mark Phase A spec as completed"
```

- [ ] **Step 8: Criar PR**

Run:
```bash
git push -u origin feat/phase-a-windows-resurrection
gh pr create --title "Fase A: Windows resurrection (ClipIA creator-first)" --body "$(cat <<'EOF'
## Summary
- Ressuscita o MVP no PC Windows (GTX 1660) após devolução do srv01-bc Linux.
- Whisper local (CUDA) → Groq Whisper API (free tier) + OpenAI fallback opcional.
- Mantém SaaS vivo mas sem cadastro público (creator-first mode).
- Stack nativa Windows: venv 3.12, NSSM services, Task Scheduler, Cloudflared.

## Test plan
- [x] Gerar 2 vídeos end-to-end via https://autoshorts.gbbragadev.com
- [x] `pytest -q` verde (ou documentado o que quebrou)
- [x] `npx tsc --noEmit` limpo
- [x] Auto-start após reboot (NSSM + Cloudflared services)
- [x] Backup diário agendado (Task Scheduler)
- [x] Custo real APIs ≤ $2 durante a Fase A

Spec: docs/superpowers/specs/2026-04-22-clipia-pivot-phase-a-design.md
Plan: docs/superpowers/plans/2026-04-22-clipia-pivot-phase-a-plan.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" --base main
```

Expected: PR URL impressa. Revisar no GitHub.

- [ ] **Step 9: Merge para `main` (quando aprovar)**

Via GitHub UI ou:
```bash
gh pr merge --squash --delete-branch
```

---

## Self-Review (feito antes de fechar este plano)

**Spec coverage:**

| Spec ref | Task(s) que cobre |
|---|---|
| D1 (Groq primário + OpenAI fallback) | 6, 7, 8, 9 |
| D2 (ElevenLabs TTS) | já implementado; Task 10 docs, Task 14 valida |
| D3 (secrets via env vars Windows) | 3, 5, 10 |
| D4 (stack Windows: venv, Docker dados, NSSM) | 1, 2, 4, 13, 18 |
| D5 (base zera + seed admin) | 11, 12 |
| D6 (Cloudflare tunnel) | 17 |
| C1 transcriber_groq.py (nota: implementamos substituindo transcriber.py em vez de criar arquivo novo — menos imports a mudar) | 8 |
| C2 transcriber_local.py.bak | 6 |
| C3 tasks.py import update | N/A — substituição in-place em `transcriber.py` preserva o import |
| C4 gpu_models disable | 6 |
| C5 config.py fields | 5 |
| C6 .env/.env.example | 10 |
| C7 docker-compose profile prod | 4 |
| C8 seed_admin.py | 12 |
| C9 start-all.ps1 | 13 |
| C10 backup-postgres.ps1 | 16 |
| C11 RUN-WINDOWS.md | 15 |
| C12 CLAUDE.md update | 20 |
| C13 hide registro público | 19 |

Gap detectado na revisão: **nenhum** — C1/C3 foi revisado para "substituir in-place" o que elimina mudança em tasks.py e routes.py.

**Placeholder scan:** nenhum TBD/TODO/"Add appropriate". Todos os code blocks completos.

**Type consistency:**
- `transcribe_with_timestamps(audio_path: str) -> list[dict]` mantido idêntico ao contrato original
- `CREDENTIALS_PATH` em `seed_admin.py` é `Path` em implementação e no teste
- Campos do `User` validados contra `app/db/models.py:28-48`:
  - admin granted via `plan="admin"` (não `is_admin`); `app/auth/dependencies.py:34` confirma
  - `hash_password` vive em `app.auth.service`, não `app.auth.passwords`
  - `User.id` é `uuid.UUID` — `existing.id` no log de skip imprime como UUID string

**Scope check:** focado em Fase A apenas. Referência a B/C/D só como roadmap no final, não como trabalho.

---

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-04-22-clipia-pivot-phase-a-plan.md`.

**Opções de execução:**

**1. Subagent-Driven (recomendado)** — dispatch fresh subagent por task, review entre tasks, iteração rápida. Bom pra este plano que tem setup de SO (instalar Python, configurar NSSM) misturado com código — isolamento evita que um subagent "ache" que pode pular passos de ambiente.

**2. Inline Execution** — executar tasks nesta sessão com checkpoints de review. Mais rápido mas concentra todo o ruído de saída aqui.

**Qual você prefere?**
