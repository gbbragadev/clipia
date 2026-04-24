# Fase A — Ressurreição do ClipIA no Windows

**Data:** 2026-04-22
**Autor:** Gui + Claude (brainstorming)
**Status:** COMPLETED — 2026-04-23 (feat/phase-a-windows-resurrection merged via PR)
**Branch atual:** `backup/2026-04-15-srv01-final` (trabalho futuro sai daqui)

## Contexto

O MVP do ClipIA rodou no servidor Linux `srv01-bc` (RTX 3090) até 2026-04-15. O servidor foi devolvido. A máquina Windows do Gui (GTX 1660 4GB, Python 3.14, Docker Desktop, Node 24, FFmpeg 8.1) passa a ser o host permanente. O projeto nunca foi ao público — o MVP foi validado pelo próprio Gui, tem pipeline completo, editor Remotion, auth, créditos, Mercado Pago, CI/CD.

O último commit (`1b14796 chore: backup state before srv01-bc return`) é o ponto de retomada.

**Estratégia de negócio escolhida:** creator-first → híbrido em 60 dias. Gui opera 1-2 canais próprios (novelinhas + curiosidades), monetiza por AdSense + afiliados, e reabre SaaS com showcase real quando houver tração. Consequência: Fase A mantém o código SaaS vivo mas sem UI aberta — Gui é único usuário.

**Budget disponível:** ~$10 USD para APIs pagas durante toda a Fase A. Meta Fase A: gastar **zero** (usar free tiers de Groq + ElevenLabs).

## Objetivo da Fase A

Rodar o pipeline atual **end-to-end no Windows** com um único ponto de mudança funcional: trocar Whisper local (CUDA Linux) por Groq Whisper API. Todas as outras peças (FastAPI, Celery, Remotion, Postgres, Redis, Cloudflare tunnel) voltam a rodar com configuração Windows.

**Critério binário de sucesso da fase:** do navegador, via `autoshorts.gbbragadev.com`, gerar 1 vídeo 9:16 completo com narração, legenda sincronizada, mídia e trilha — baixar o MP4, reproduzir fim-a-fim sem erro.

## Fora de escopo

- Geração de imagem IA (fica para Fase B)
- Geração de vídeo AI / Kling / Veo / Runway (adiado indefinidamente)
- Scheduler de canal / auto-upload YouTube (Fase C)
- Novos templates de vídeo (Fase B)
- Stripe / Mercado Pago ativo no UI (fica dormindo no código)
- Onboarding público, registro aberto (fica dormindo)
- Otimização de qualidade visual / novos presets de legenda
- Migração de dados antigos (base zera; snapshot em `backup/2026-04-15-srv01-final`)

## Decisões-mestras

### D1. ASR: Groq Whisper API (primário) + OpenAI Whisper (fallback)

- Whisper local tá amarrado em CUDA Linux (`/usr/local/lib/ollama/cuda_v12/`). Não adapta para Windows sem refatoração.
- GTX 1660 4GB não cabe Large V3 (precisa ~10GB).
- Groq serve o mesmo modelo com free tier generoso (~28.800 s/dia). Latência ≤ 2x realtime.
- OpenAI Whisper API existe como backup pago ($0.006/min).
- `transcriber.py` atual passa a ser `transcriber_local.py.bak` (não é deletado — fica como referência histórica).
- Novo módulo `transcriber_groq.py` expõe a mesma função `transcribe_with_timestamps(audio_path) -> list[dict]` com schema idêntico (word, start, end).
- Seleção via env var `ASR_PROVIDER` (`groq` default, `openai` fallback).

### D2. TTS: ElevenLabs primário via chave projetada, EdgeTTS fallback

- `ElevenLabsProvider` já existe e está testado.
- Default de novos jobs = ElevenLabs (voz a ser escolhida no dashboard; default visual continua Antonio/Francisca/Thalita do EdgeTTS **só se ElevenLabs falhar**).
- EdgeTTS fica como fallback gratuito quando chave ElevenLabs não está setada ou API retorna erro.

### D3. Secrets: referenciar env vars do Windows, não duplicar no `.env`

- Chaves vivem em `[Environment]::GetEnvironmentVariable('<NOME>','User')`.
- `.env` do repo contém apenas valores locais (DATABASE_URL, REDIS_URL, JWT_SECRET) e comentários apontando para quais env vars devem estar presentes.
- `app/config.py` (pydantic settings) lê tanto `.env` quanto env vars reais; env vars reais têm precedência.
- Pré-requisitos de env vars do usuário (devem estar setadas antes de rodar):
  - `OPEN_API_CLIPIA_TOKEN` (OpenAI — Whisper fallback + futuro gpt-image)
  - `ELEVEN_LABS_CLIPIA_KEY` (ElevenLabs TTS) — **atualmente ausente, precisa criar**
  - `ANTHROPIC_API_KEY` (Claude scripts) — **atualmente ausente, precisa criar**
  - `PEXELS_API_KEY` (stock media) — **atualmente ausente, precisa criar**
  - `GROQ_API_KEY` (Whisper primário) — **atualmente ausente, precisa criar**
  - `CF_API_TOKEN` + `CLOUDFLARE_API_TOKEN` (já setadas)
- Mapeamento no `config.py` (novo bloco):
  ```python
  ANTHROPIC_API_KEY: str = Field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
  OPENAI_API_KEY: str = Field(default_factory=lambda: os.environ.get("OPEN_API_CLIPIA_TOKEN", ""))
  ELEVENLABS_API_KEY: str = Field(default_factory=lambda: os.environ.get("ELEVEN_LABS_CLIPIA_KEY", ""))
  GROQ_API_KEY: str = Field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
  PEXELS_API_KEY: str = Field(default_factory=lambda: os.environ.get("PEXELS_API_KEY", ""))
  ```
  (nome canônico interno à esquerda, nome da env var Windows à direita).

### D4. Stack Windows

| Camada | Solução | Modo de execução |
|---|---|---|
| Postgres 16 | Container `postgres:16-alpine` | `docker compose up postgres -d` |
| Redis 7 | Container `redis:7-alpine` | `docker compose up redis -d` |
| Python | 3.12 instalado side-by-side com 3.14 | venv em `.venv312\` |
| Backend FastAPI | `uvicorn app.main:app --reload --port 8005` | dev: CMD manual; prod: NSSM como serviço Windows |
| Worker Celery | `celery -A app.worker.celery_app worker -l info --concurrency=1` | dev: CMD manual; prod: NSSM |
| Frontend Next | `npm run dev -- -p 3003` | dev: CMD manual; prod: `npm run build && npm start` como NSSM |
| Cloudflare Tunnel | `cloudflared` já conhecido | serviço Windows (`cloudflared service install`) |
| FFmpeg | 8.1 no PATH (já instalado) | `ffmpeg -version` |

**Não usar Docker Compose para backend/worker/frontend** em Fase A — os containers são para prod futura; em desenvolvimento, executar nativo para ter reload, debug e paths limpos.

### D5. Base de dados zera

- Volume Docker `pgdata` novo, sem dump de Linux.
- Seed script cria user `admin@gui` com email `gbbraga.dev@gmail.com`, password aleatória impressa no stdout, `plan="admin"` (mecanismo real de admin no código — `get_current_admin_user` checa `user.plan == "admin"`), `credits=999999`, `email_verified=True`.
- Tabelas de Credit Purchases, Jobs ficam vazias; Alembic migrate até o head atual.

### D6. Cloudflare Tunnel mantém domínios existentes

- `autoshorts.gbbragadev.com` → `http://localhost:3003`
- `api-autoshorts.gbbragadev.com` → `http://localhost:8005`
- `config.yml` do `cloudflared` atualizado na máquina Windows
- Mesma `CLOUDFLARE_API_TOKEN` usada para rotacionar se precisar

## Arquitetura pós-Fase A

```
Windows 11 (PC do Gui — on 24/7)
│
├── Docker Desktop
│   ├── postgres:16  (5435:5432)
│   └── redis:7      (6382:6379)
│
├── Python 3.12 venv (.venv312)
│   ├── uvicorn app.main:app        → :8005  [NSSM service: clipia-backend]
│   └── celery worker               → (Redis queue) [NSSM service: clipia-worker]
│
├── Node 24
│   └── next server                 → :3003  [NSSM service: clipia-frontend]
│
├── cloudflared (service)
│   ├── autoshorts.gbbragadev.com         → :3003
│   └── api-autoshorts.gbbragadev.com     → :8005
│
└── Task Scheduler
    └── backup-postgres.ps1 (diário 03:00) → storage/backups/
```

Todas as dependências externas pagas ficam offloaded para APIs (Groq, ElevenLabs, Anthropic, OpenAI, Pexels) — nada precisa de GPU pesada local.

## Componentes e mudanças

### C1 — `app/services/transcriber_groq.py` (NOVO)

Função com a mesma assinatura do `transcriber.py` atual:

```python
def transcribe_with_timestamps(audio_path: str) -> list[dict]:
    """Transcribe audio via Groq Whisper API with word-level timestamps.

    Returns list of {"word": str, "start": float, "end": float}.
    """
```

Usa endpoint Groq `audio/transcriptions` com `response_format=verbose_json` e `timestamp_granularities=["word"]`. Modelo: `whisper-large-v3`. Language: `pt`.

Retry policy: 3 tentativas com backoff 2s, 4s, 8s. Em falha terminal, propaga exceção para Celery marcar job como failed e refund de créditos (logic já existe em `_refund_job_credit`).

Config toggle `ASR_FALLBACK_ENABLED` (lido de `.env` do projeto, **não** de env var do Windows): quando `true`, após esgotar retries no Groq, tenta OpenAI Whisper com mesma assinatura antes de falhar o job. Default `false` para evitar gasto surpresa.

### C2 — `app/services/transcriber.py` (RENOMEADO)

Arquivo atual movido para `app/services/transcriber_local.py.bak`. Não é importado por nada. Permanece no repo como referência histórica para o dia em que a gente quiser voltar a ter ASR local (improvável).

### C3 — `app/worker/tasks.py` (MUDANÇA MÍNIMA)

Linha 16 atual:
```python
from app.services.transcriber import transcribe_with_timestamps
```

Vira:
```python
from app.services.transcriber_groq import transcribe_with_timestamps
```

Se houver outra referência indireta (via `app/worker/gpu_models.py` ou similar), auditar e remover/desativar.

### C4 — `app/worker/gpu_models.py` (DESATIVAÇÃO)

Se este arquivo existe e só serve para carregar o modelo Whisper local, marcar a função `get_whisper_model()` com `raise NotImplementedError("local whisper disabled in Phase A; use transcriber_groq")`. Não deletar — pode servir em Fase B para outros modelos locais (ex: face swap, upscaler).

### C5 — `app/config.py` (ADIÇÃO DE FIELDS)

Adicionar os fields listados em D3. Garantir que `Settings()` não explode quando env var está ausente (default `""`) — falha verbosa só quando o provider tenta usar a chave vazia.

### C6 — `.env` e `.env.example` (REVISÃO)

- `.env.example` mostra apenas variáveis locais (DATABASE_URL, REDIS_URL, JWT_SECRET, porta) e **comenta** as env vars do Windows que precisam existir ("Required Windows user env vars: OPEN_API_CLIPIA_TOKEN, ELEVEN_LABS_CLIPIA_KEY, ...").
- `.env` (local, gitignored) contém valores de dev.
- Remove blocos duplicados de API keys do `.env` atual (se houver).

### C7 — `docker-compose.yml` (REVISÃO)

- Manter `postgres` e `redis` como estão.
- Colocar `backend` e `worker` sob profile `prod` (não sobe com `docker compose up`, só com `--profile prod`). Dev no Windows roda nativo; prod futura usa profile.
- Adicionar comentário no topo explicando.

### C8 — `scripts/seed_admin.py` (NOVO)

Script Python idempotente que cria user admin se não existir:

```python
# python scripts/seed_admin.py
# cria admin@gui / gbbraga.dev@gmail.com com crédito alto
```

Password aleatória, impressa na saída, salva em `.admin-credentials.local` (gitignored). Idempotente (não recria se já existe).

### C9 — `scripts/start-all.ps1` (NOVO)

Script PowerShell que sobe tudo para desenvolvimento:

```
1. docker compose up postgres redis -d
2. Espera healthcheck
3. Aplica alembic upgrade head
4. Confere env vars obrigatórias; lista faltantes
5. Abre 3 janelas: backend, worker, frontend
6. Lembra de iniciar cloudflared se desejado
```

### C10 — `scripts/backup-postgres.ps1` (NOVO, adaptação)

Porta do `scripts/backup-postgres.sh` existente:
- `pg_dump` via container `postgres:16-alpine` (docker exec)
- Output em `storage/backups/clipia-YYYY-MM-DD.sql.gz`
- Retém 14 dias
- Task Scheduler agenda diário às 03:00

### C11 — `docs/RUN-WINDOWS.md` (NOVO)

Documento vivo com os passos reais testados:

1. Pré-requisitos (software + env vars)
2. Clone + setup venv + deps
3. `docker compose up postgres redis -d`
4. `alembic upgrade head`
5. `python scripts/seed_admin.py`
6. `npm install` (primeira vez)
7. `.\scripts\start-all.ps1`
8. Smoke test (gerar 1 vídeo)
9. Cloudflare Tunnel setup
10. NSSM install (quando for botar como serviço)
11. Troubleshooting

### C12 — `CLAUDE.md` (ATUALIZAÇÃO)

- Comandos principais passam a ser Windows (PowerShell).
- Bloco de comandos Linux vira apêndice com título "Linux legacy (srv01-bc, obsoleto)".
- Adicionar regra: "Secrets em env vars do Windows, não duplicar em `.env`."
- Adicionar nota: "Fase A → creator-first; SaaS dormente."

### C13 — `app/main.py` / `app/api/routes.py` (VERIFICAÇÃO, não mudança)

Confirmar que o path `/api/v1/auth/register` continua aceitando novos usuários (caso Gui queira criar user secundário de teste), mas **remover link "Registrar" da landing page** para esconder da aquisição pública. Logar acessos ao endpoint para eventual fechamento futuro.

## Fluxo de dados — inalterado

```
Gui abre autoshorts.gbbragadev.com
  → login admin@gui
  → dashboard: tema + template + voz → POST /api/v1/jobs/dispatch
    → Celery task (backend → Redis → worker)
        1. generate_script    (Anthropic)
        2. synthesize_audio   (ElevenLabs [default] ou EdgeTTS)
        3. transcribe_audio   (Groq Whisper API) ← única mudança Fase A
        4. fetch_media        (Pexels)
        5. compose_video      (FFmpeg+NVENC local, continua sem precisar de GPU nova)
        6. finalize           (salva MP4 + Postgres)
    → front polling status
  → abre /editor/{jobId} (opcional)
  → download MP4 do /storage/output/{id}.mp4
```

## Error handling

Sem mudanças de lógica — o pipeline atual já tem:
- Dead letter queue no Redis
- `_refund_job_credit` para estornar em falhas
- `task_reject_on_worker_lost` (commit `72350e9`)
- Admin alert por email (SMTP)

**Novo ponto de falha:** Groq API 429 / 5xx → fallback para OpenAI Whisper **só se** `ASR_FALLBACK_ENABLED=true` no `.env` local. Default: fallback desligado para evitar gasto surpresa; Gui ativa manualmente editando o `.env` se o free tier estourar.

## Testing strategy

### Testes automáticos (pytest)
- `tests/services/test_transcriber_groq.py`: mock de resposta Groq, valida parsing e schema
- Reusar tests existentes que mockam `transcribe_with_timestamps` (nome da função é o mesmo → sem quebra)
- `pytest -q` no boot da Fase A para capturar o baseline quebrado (aceitável se algum teste Linux-specific quebrar; documentar quais e por quê)

### Testes manuais (obrigatórios antes de fechar a fase)
1. Gerar vídeo com tema "curiosidades sobre o espaço", template `stock_narration`, voz ElevenLabs → baixa MP4 → abre → tem narração + legenda + stock + trilha
2. Gerar vídeo segundo com template `story_time` + voz EdgeTTS → confirma fallback TTS funciona
3. Injetar `GROQ_API_KEY=invalid` **apenas no processo do worker** (via `.env` local ou `$env:GROQ_API_KEY="invalid"` na janela daquele worker) e rodar → confirma erro claro no job, refund de crédito, dead letter. Não mexer na env var persistida do Windows.
4. Reiniciar serviços NSSM → confirma que subem sozinhos
5. Acessar `autoshorts.gbbragadev.com` de celular (4G, fora da rede local) → confirma tunnel funciona

### TypeScript
`cd frontend && npx tsc --noEmit` limpo antes de fechar fase.

## Critérios de aceitação

- [ ] Gui consegue gerar vídeo fim-a-fim via `autoshorts.gbbragadev.com` de qualquer rede
- [ ] Transcrição Groq funcionando em pelo menos 3 vídeos consecutivos
- [ ] TTS ElevenLabs default + fallback EdgeTTS validado
- [ ] Backend, worker, frontend reiniciam sozinhos em caso de reboot do PC (NSSM)
- [ ] Backup diário do Postgres agendado e com retenção de 14 dias
- [ ] `docs/RUN-WINDOWS.md` escrito com passos **que o Gui mesmo seguiu** (não especulação)
- [ ] `CLAUDE.md` atualizado; Linux legacy em apêndice
- [ ] `pytest -q` executa (mesmo que alguns testes Linux-specific falhem, documentados)
- [ ] `npx tsc --noEmit` sem erros
- [ ] Custo real gasto em APIs durante toda a Fase A ≤ $2 USD

## Riscos e mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Python 3.14 única versão disponível e 3.12 não instalar limpo | M | A | Usar instalador oficial python.org (MSI) em `C:\Python312`, venv explícito sem depender de `py -3.12` |
| `faster-whisper` / `torch` / outras deps não instalarem no Windows | B | M | Deps novas de ASR sumiram (usamos Groq API só); torch só é usado se voltar Whisper local — improvável. Remover de `requirements.txt`. |
| Cloudflare Tunnel perder config antiga | B | A | Refazer config a partir do dashboard CF (tem token); documentar no RUN-WINDOWS |
| ElevenLabs free tier estourar no meio da Fase A | M | B | Monitorar uso pelo dashboard; ativar fallback EdgeTTS (já está no código) |
| Groq free tier com throttling / instabilidade | B | M | Fallback OpenAI Whisper ativa por env var (`ASR_FALLBACK_ENABLED=true`) |
| Postgres container perder dados (volume Docker) | B | A | Backup diário `pg_dump` + branch `backup/2026-04-15-srv01-final` como origem |
| Task Scheduler / NSSM teimosa (Windows quirks) | M | B | Em último caso, rodar stack via Docker Compose com profile `prod` — já preparado |
| PC dormir / perder rede → tunnel cai | M | A | Windows "Never sleep on AC power" + wake-on-LAN; documentar |

## Roadmap após Fase A (preview, specs futuras)

### Fase B — Upgrade de mídia (budget $2-3)
- Provider `OpenAIImageProvider` (`gpt-image-1`) para gerar imagens 9:16 de cena específica
- Novo template `novelinha_ia` com sequência de cenas geradas em vez de Pexels
- Novo template `curiosidade_historica` otimizado para hooks rápidos
- Teste A/B: vídeo Pexels vs vídeo `gpt-image-1` → qual dá mais retenção?

### Fase C — Pipeline automática de canal (budget $0-2)
- Entidade `Channel` (tema, voz, template, horário)
- Celery Beat para disparar geração diária
- YouTube Data API v3 upload (OAuth pela conta do Gui)
- Feed de ideias: brainstorm via Claude (lista 20 hooks/dia por tema)

### Fase D — Fork de negócio (decisão em 60 dias)
- **D1:** um canal bateu 1000 inscritos → continua creator, escala 3-5 canais
- **D2:** canais não engajaram → reabre SaaS com showcase dos vídeos gerados, Stripe ativo, landing nova
- **D3:** híbrido — canais próprios + 5 usuários beta testando SaaS fechado

## Questões em aberto (responder antes do writing-plans)

1. **`GROQ_API_KEY`, `ELEVEN_LABS_CLIPIA_KEY`, `ANTHROPIC_API_KEY`, `PEXELS_API_KEY`, `OPEN_ROUTER_API_KEY`, `RUN_POD_API_KEY`** não apareceram no scope User do Windows ao validar via PowerShell. As imagens que o Gui compartilhou mostravam algumas delas. Antes de começar a implementação, Gui precisa confirmar em `[Environment]::GetEnvironmentVariable('<NOME>','User')` que estão persistidas e, se não estiverem, criar via Painel de Controle ou `[Environment]::SetEnvironmentVariable`.

2. **Conta Groq criada?** Se não, é um passo no capítulo "Pré-requisitos" do `RUN-WINDOWS.md`.

3. **Subdomínio `autoshorts.gbbragadev.com`** ainda aponta para o IP do servidor antigo. Precisa atualizar o túnel Cloudflare para a máquina Windows — usar o dashboard ou a `CLOUDFLARE_API_TOKEN`.

4. **Admin password** — salvar onde? Proposta: `.admin-credentials.local` (gitignored) na raiz do repo, com nota no `.gitignore`.
