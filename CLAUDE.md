# ClipIA — Auto Shorts Generator

## Projeto
Plataforma de geracao automatizada de videos curtos (Shorts, Reels, TikTok) com IA. Recebe um tema, gera roteiro, seleciona midia, narra com TTS pt-BR, compoe video com legendas. Inclui editor interativo com Remotion para ajustes antes de publicar.

## Estado (2026-04-22)
- **Fase A em execucao** (ressurreicao Windows) em branch `feat/phase-a-windows-resurrection`
- Stack roda no PC Windows do Gui (GTX 1660 4GB) — servidor `srv01-bc` foi devolvido
- **Creator-first**: SaaS vivo mas sem cadastro publico (`NEXT_PUBLIC_PUBLIC_SIGNUP!="true"`)
- **ASR**: Groq Whisper API (free tier) substituiu Whisper local/CUDA
- **TTS**: ElevenLabs primario, EdgeTTS fallback
- Secrets vivem em env vars Windows User scope (ver `scripts/check-env.ps1`)
- Proxima fase: B — `gpt-image-1` + novos templates (novelinha, curiosidade)

## Stack
- **Backend**: Python 3.12 + FastAPI + Celery + Redis + PostgreSQL (async SQLAlchemy)
- **Frontend**: Next.js 16 + React 19 + Remotion 4 + Tailwind CSS 4
- **TTS**: Edge TTS (Microsoft) para narracao pt-BR (3 vozes: Antonio, Francisca, Thalita)
- **Legendas**: Whisper Large V3 (faster-whisper) com word-level timestamps
- **Video**: FFmpeg + NVENC para composicao (pipeline Celery)
- **Roteiros**: Claude API (Anthropic)
- **Media**: Pexels API (video stock gratuito)
- **GPU**: RTX 3090 — usada para Whisper (CUDA via ctypes preload)
- **Auth**: JWT (HS256, 24h expiry), token salvo como `clipia_token` no localStorage

## Arquitetura

### Pipeline de geracao (Celery)
```
generate_script → synthesize_audio → transcribe_audio → fetch_media → compose_video → finalize
```
- Status tracking via Redis hash `job:{id}`
- Arquivos intermediarios em `storage/jobs/{id}/` (script.json, narration.wav, words.json, media/)
- Video final copiado para `storage/output/{id}.mp4`
- Finalize salva script no Postgres (campo JSONB) e marca como "editable"

### Editor (Remotion)
- Player com preview 9:16 em tempo real
- EditorContext centraliza estado (playerRef, composition, undo/redo, auto-save)
- 5 abas: Cenas, Voz, Legendas, Elementos, IA
- Backend endpoints: /composition, /edit, /regenerate-tts, /ai-suggest, /render

### Paginas frontend
- `/` — Landing page
- `/auth/login`, `/auth/register` — Auth
- `/dashboard` — Gerar videos + lista de jobs + link para editor
- `/editor/[jobId]` — Editor interativo com Remotion

## Infra (srv01-bc)
- GPU: RTX 3090 24GB VRAM
- RAM: 96GB DDR4
- Storage: NVMe rapido para temp files
- Cloudflare Tunnel:
  - `autoshorts.gbbragadev.com` → localhost:3003 (frontend)
  - `api-autoshorts.gbbragadev.com` → localhost:8005 (backend)

## Comandos (Windows — default em 2026-04-22+)

```powershell
# Setup unica vez
& $env:CLIPIA_PYTHON312_EXE -m venv .venv312
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

## Gotchas importantes
- **Secrets via env vars do Windows**: chaves de API ficam em env vars de User (GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY). `.env` do repo tem apenas DATABASE_URL/REDIS_URL/JWT_SECRET. Nunca duplicar chave em `.env`.
- **Whisper via Groq API (Fase A+)**: `app/services/transcriber.py` chama Groq; `transcriber_local.py.bak` preserva a versao antiga. Fallback para OpenAI Whisper ativado via `ASR_FALLBACK_ENABLED=true` no `.env`.
- **Celery em Windows**: worker precisa `--pool=solo` (prefork nao funciona sem `fork()`).
- **Token localStorage**: Key e `clipia_token`, NAO `token`. Usar `getToken()` de `@/lib/auth`.
- **TTS async**: No FastAPI usar `synthesize_narration_async()`. A versao sync (`synthesize_narration`) e so para Celery worker.
- **Whisper CUDA**: `transcriber.py` pre-carrega `libcublas.so.12` via `ctypes.cdll.LoadLibrary` de `/usr/local/lib/ollama/cuda_v12/`. Sem isso, Whisper falha silenciosamente.
- **Job status**: Redis tem status real-time, Postgres pode estar stale. O endpoint `/jobs` cruza ambos.
- **Export nao re-renderiza**: O `/render` atual so copia `final.mp4` — NAO re-compoe com edicoes do editor. Precisa implementar re-render real via Celery.
- **Remotion Player ref**: Carregado via dynamic import SSR:false. Polling 100ms sincroniza playerFrame.

Sempre responder em portugues (pt-BR).
