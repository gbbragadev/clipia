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
- **Render hibrido (Fase 2+)**: geracao inicial usa FFmpeg/NVENC (~15s); o export editado (`POST /render` → `task_rerender_video`) renderiza via **Remotion** (`app/services/remotion.py` + `frontend/scripts/render-composition.mjs`, ~105s) para fidelidade editor==export. Flag `RENDER_ENGINE` (remotion|ffmpeg) em `app/config.py`.
- **Remotion Player ref**: Carregado via dynamic import SSR:false. Polling 100ms sincroniza playerFrame.

Sempre responder em portugues (pt-BR).

## ACE Learned Strategies

<!-- ACE:START - Do not edit manually -->
```json
{"skills": [
  {"id": "1", "section": "RUNTIME", "content": "Se FFmpeg filter ass reclamar 'Error applying option original_size' em paths Windows, o colon do drive esta colidindo com o separador de opcao; use double-escape (C\\\\:/path) + fontsdir=<fonts_dir> explicito (FFmpeg Windows nao tem fontconfig default).", "helpful": 1, "harmful": 0, "neutral": 0},
  {"id": "2", "section": "RUNTIME", "content": "Celery worker em Windows precisa --pool=solo; o default prefork exige fork() que Windows nao tem. Sintoma: worker sobe, fica ready, mas tasks enfileiram sem consumir.", "helpful": 1, "harmful": 0, "neutral": 0},
  {"id": "3", "section": "WORKFLOW", "content": "Env vars User-scope criadas via [Environment]::SetEnvironmentVariable(...,'User') NAO propagam para processos filhos ja rodando; todo launcher deve ter um prelude que copia de User para Process antes de spawn (ver scripts/_run-backend.ps1).", "helpful": 1, "harmful": 0, "neutral": 0},
  {"id": "4", "section": "API", "content": "Groq SDK audio.transcriptions.create retorna response.words como lista de DICTS ({word,start,end}), nao objetos; parsers devem aceitar ambos (isinstance(w,dict) branch). MagicMock em testes mascara essa diferenca — rodar smoke test real antes de remover branches 'defensivos'.", "helpful": 1, "harmful": 0, "neutral": 0},
  {"id": "5", "section": "PREFERENCE", "content": "Chaves de API do usuario (Gui) vivem em env vars Windows User scope. Aliases conhecidos: OPENAI_API_KEY <- OPEN_API_CLIPIA_TOKEN, ELEVENLABS_API_KEY <- ELEVEN_LABS_CLIPIA_KEY. Docs: https://developers.openai.com/api/docs/guides/image-generation. Nunca duplicar chave em .env commitado.", "helpful": 1, "harmful": 0, "neutral": 0},
  {"id": "6", "section": "WORKFLOW", "content": "Next.js 16 exige 'npx next typegen' antes de 'tsc --noEmit' funcionar (tipo PageProps e gerado em runtime). next dev e next build rodam typegen automaticamente.", "helpful": 1, "harmful": 0, "neutral": 0}
]}
```
<!-- ACE:END -->
