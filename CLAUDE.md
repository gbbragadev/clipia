# Auto Shorts Generator

## Projeto
Plataforma de geracao automatizada de videos curtos (Shorts, Reels, TikTok) com IA. Recebe um tema, gera roteiro, seleciona midia, narra com TTS pt-BR, compoe video com legendas.

## Stack
- **Backend**: Python 3.12 + FastAPI + Celery
- **TTS**: XTTS v2 (Coqui) para narracao pt-BR natural
- **Legendas**: Whisper Large V3 (faster-whisper)
- **Video**: FFmpeg + MoviePy para composicao
- **Roteiros**: Claude API
- **Imagens**: Pexels API (stock gratuito) + SDXL (geracao local)
- **GPU**: RTX 3090 para TTS, Whisper, SDXL e renderizacao

## Infra disponivel (srv01-bc)
- GPU: RTX 3090 24GB VRAM
- RAM: 96GB DDR4
- Storage: NVMe rapido para temp files de video
- Cloudflare Tunnel: para expor o servico

## Referencia
- MoneyPrinterV2 (github.com/FujiwaraChoki/MoneyPrinterV2) como base/inspiracao

## Comandos
```bash
# Dev
uvicorn app.main:app --reload --port 8003

# Worker de video
celery -A app.worker worker -l info

# Testes
pytest tests/ -v
```

## Workflow
Usar gstack para todo o desenvolvimento. Comecar com /office-hours para planejar, /ship para implementar, /review antes de merge.

Sempre responder em portugues (pt-BR).
