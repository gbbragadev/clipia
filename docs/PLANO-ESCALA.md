# Plano de Escala — ClipIA (jul/2026)

Decisão do dono: **sem infra nova agora** — telemetria + gatilhos escritos. Quando um
gatilho disparar (dados da aba **Admin → Economia** e dos logs do worker), a ação
correspondente já está decidida e dimensionada. Nada aqui é especulativo: cada gatilho
tem número, fonte de medição e ação.

## Baseline (10/07/2026, pós-fix do compose)

- **Throughput**: 1 job por vez (Celery `--pool=solo`, concurrency=1, Windows).
- **Máquina**: PC do Gui (Ryzen 5700, GTX 1660 4GB, NVMe) — hostil a 24/7 (modo jogo
  derruba Docker; ver memória "Docker/WSL/Modo Jogo").
- **Tempos esperados por template** (validar na verificação final):
  stock ~3-4min · imagens IA ~5-7min · ai_video ~6-10min (dominado pela API Seedance).
- **Storage**: ~150-500MB/job em `storage/jobs/` + `storage/output/`; cleanup diário 4h
  (beat LIGADO em 10/07 — antes nunca rodava).
- **Custo API estimado/vídeo**: stock+edge ~$0.015 · elevenlabs ~$0.33 · imagens IA
  ~$0.40 · ai_video ~$1.20 (constantes `API_COST_*` em `app/config.py`; a aba Economia
  mostra o real acumulado).

## Gatilhos → Ações

### 1. Fila: espera média > 10min OU > 5 jobs aguardando com frequência
- **Medir**: `queue_position` no dashboard + `total_seconds` na aba Economia +
  logs do worker.
- **Ação**: 2º processo worker (outra janela do `_run-worker.ps1` com pool solo).
  ATENÇÃO: 2 composes FFmpeg simultâneos disputam CPU/NVENC (a 1660 tem limite de
  sessões NVENC) — medir antes de assumir 2× throughput. Se 2 workers não bastarem →
  gatilho 5 (VPS).
- **Custo**: R$ 0 (mesma máquina).

### 2. Storage: > 100 GB total OU crescimento > 50 GB/dia
- **Medir**: `du` de `storage/` (o admin dashboard já mostra storage usado).
- **Ação**: mover `storage/output/` (vídeos finais + thumbnails) para Cloudflare R2
  (S3-compatible, sem egress fee; o tunnel CF já existe). Jobs intermediários seguem
  locais (cleanup 4h já os limpa).
- **Custo**: ~US$ 1,50/100GB/mês.

### 3. LLM: OpenRouter 429/erros em > 5% das chamadas OU cascata caindo no free com frequência
- **Medir**: logs `LLM ... falhou/vazio — proximo provedor` + badge "qualidade reduzida"
  nos cards (Q7).
- **Ação**: recarregar créditos OpenRouter (a cascata OpenAI/xAI já cobre a transição) +
  cache de roteiro por (tema,template) se houver repetição real.
- **Custo**: recarga conforme uso (aba Economia dá o burn rate).

### 4. Margem: custo API > 20% da receita de créditos OU template com margem negativa
- **Medir**: aba **Admin → Economia** (margem por template; R$ 1,30/crédito de referência).
- **Ação**: reprecificar créditos do template (app/pricing.py) OU trocar provedor
  (ex.: gpt-image quality low; Seedance 480p). ElevenLabs é a margem mais apertada —
  vigiar primeiro.

### 5. Volume: > 30 vídeos/dia sustentado OU worker ocupado > 60% do dia
- **Medir**: contagem diária na aba Vídeos do admin + timestamps da Economia.
- **Ação**: VPS com GPU barata (ou CPU forte) rodando SÓ o worker (backend/DB podem
  ficar onde estão; Redis/Postgres via túnel ou gerenciado). Perfil: Hetzner/Contabo
  8vCPU ≈ €15-25/mês — o compose pós-fix é leve; NVENC é opcional (libx264 veryfast dá
  conta em CPU forte).
- **Pré-requisito**: secrets fora de env-vars Windows (dotenv/secret manager) e
  `docker-compose` de worker (o repo já tem compose de postgres/redis).

### 6. Confiabilidade: > 2 jobs/semana ceifados pelo watchdog
- **Medir**: alertas de dead-letter no e-mail admin + logs "Watchdog reaped".
- **Ação**: olhar o step recorrente na aba Economia (etapa mais lenta) e atacar a causa
  específica (timeout de provedor, retry, provedor alternativo) — não aumentar o limiar
  às cegas.

## Não fazer agora (decidido)

- ❌ Kubernetes/orquestração — 1 máquina, 1 worker; complexidade sem retorno.
- ❌ GPU dedicada nova — o compose pós-fix é CPU-friendly; a 1660 cobre CLIP/NVENC final.
- ❌ TTS próprio — ElevenLabs + Edge cobrem; problema é margem, não capacidade.
- ❌ Migrar DB — Postgres local atende; VPS (gatilho 5) leva o worker primeiro.

## Revisão

Reavaliar este plano quando qualquer gatilho disparar OU ao fim de cada mês com os
números da aba Economia (o que vier primeiro).
