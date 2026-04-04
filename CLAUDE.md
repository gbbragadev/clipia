# ClipIA — Auto Shorts Generator

## Projeto
Plataforma de geracao automatizada de videos curtos (Shorts, Reels, TikTok) com IA. Recebe um tema, gera roteiro, seleciona midia, narra com TTS pt-BR, compoe video com legendas. Inclui editor interativo com Remotion para ajustes antes de publicar.

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

## Comandos
```bash
# Backend (porta 8005, --reload ativo)
cd ~/projects/auto-shorts && source .venv/bin/activate
uvicorn app.main:app --reload --port 8005 --log-file /tmp/clipia-backend.log

# Worker Celery (precisa CUDA libs para Whisper)
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1

# Frontend
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# TypeScript check
cd ~/projects/auto-shorts/frontend && npx tsc --noEmit

# Testar endpoint com auth
TOKEN=$(curl -s -X POST http://localhost:8005/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"gui@clipia.com","password":"test123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

## Gotchas importantes
- **Token localStorage**: Key e `clipia_token`, NAO `token`. Usar `getToken()` de `@/lib/auth`.
- **TTS async**: No FastAPI usar `synthesize_narration_async()`. A versao sync (`synthesize_narration`) e so para Celery worker.
- **Whisper CUDA**: `transcriber.py` pre-carrega `libcublas.so.12` via `ctypes.cdll.LoadLibrary` de `/usr/local/lib/ollama/cuda_v12/`. Sem isso, Whisper falha silenciosamente.
- **Job status**: Redis tem status real-time, Postgres pode estar stale. O endpoint `/jobs` cruza ambos.
- **Export nao re-renderiza**: O `/render` atual so copia `final.mp4` — NAO re-compoe com edicoes do editor. Precisa implementar re-render real via Celery.
- **Remotion Player ref**: Carregado via dynamic import SSR:false. Polling 100ms sincroniza playerFrame.

Sempre responder em portugues (pt-BR).
