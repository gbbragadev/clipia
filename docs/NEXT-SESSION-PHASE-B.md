# Handoff — Fase B (próxima sessão)

**Data do handoff:** 2026-04-23
**Commit de partida:** `726e264` na branch `feat/phase-a-windows-resurrection`
**PR Fase A:** https://github.com/gbbragadev/clipia/pull/1 (aberto, 289 arquivos)

## Gatilho para retomar

> Cole no início da próxima sessão:
> "Lê `docs/NEXT-SESSION-PHASE-B.md`. Foco: Fase B (geração de imagem com gpt-image-1/2) + começar a monetização. Já tenho todas as env vars do Windows."

---

## 1. Estado atual (o que foi feito)

### Fase A — concluída
- **25 commits** entregues, branch `feat/phase-a-windows-resurrection` pushed
- Stack rodando no PC Windows: backend (`:8005`), worker Celery, frontend Next (`:3003`), Postgres 16 + Redis 7 em Docker
- Cloudflare tunnel `onwatch` estendido com `autoshorts.gbbragadev.com` + `api-autoshorts.gbbragadev.com`
- **1 vídeo gerado end-to-end**: `storage/phase-a-smoke-test.mp4` (45s, 1080x1920, H.264+AAC, 16.6MB)
- Admin user `gbbraga.dev@gmail.com`, senha em `.admin-credentials.local`
- Whisper local → Groq API, fontes Linux hardcoded → Montserrat bundled
- 198/199 testes passando (1 pre-existente sem relação)

### Pendente (admin-only, owner: Gui)
- `scripts/install-windows-services.ps1` (NSSM) — converter backend/worker/frontend em Windows services com auto-start
- Task Scheduler pro `scripts/backup-postgres.ps1` (comando no commit `505147f`)
- Merge PR #1 (ou recomendar estratégia de limpar histórico — ver "Decisões a validar" abaixo)

---

## 2. Opinião crítica — pra onde seguir

Vou ser honesto, não vendedor. O que vejo:

### 2.1. **A Fase A confirmou que o MVP é sólido, mas não é um produto comercializável ainda**

Razão dura: **o vídeo gerado hoje tem qualidade de MVP, não de conteúdo monetizável**. Stock do Pexels + narração EdgeTTS robótica + legendas genéricas é o que 50 outras plataformas (InVideo, Pictory, Opus Clip, Submagic, Crayo) entregam. Você não vai ganhar o mercado competindo nessa camada.

O que diferencia um canal automatizado que **bomba** hoje (novelinhas, fatos históricos, curiosidades nichadas) é:
1. **Imagens AI temáticas** (gpt-image-1 / Imagen / Flux) em vez de stock — qualidade visual consistente, narrativa visual coesa
2. **TTS com voz de personagem** (ElevenLabs clonado ou voz premium pt-BR bem escolhida) — não Edge
3. **Hook de 3s** nos primeiros frames que prende antes do scroll
4. **Roteiro com narrativa**, não listinha de 3 fatos

Por isso **Fase B (gpt-image) não é cosmética — é o salto que determina se o produto tem chance ou não**. Priorizar isso antes de qualquer feature de monetização.

### 2.2. **Monetização: não comece pelo Stripe**

O erro comum é implementar o checkout antes de ter alguém querendo pagar. A ordem que faz sentido:

**Etapa 1 (agora, Fase B):** Você mesmo produz **3-5 vídeos de cada nicho** (novelinha curta, curiosidade histórica, fato de ciência) usando `gpt-image` + ElevenLabs voz premium. **Posta em canal próprio no YouTube Shorts e TikTok**.
- Custo: ~$5-10/semana de API. Budget de $10 que você tem dá pra ~100 vídeos.
- Objetivo: provar que dá pra bater 10k views consistentes com esse pipeline. Se 3-5 vídeos do mesmo canal baterem 10k, você tem **caso de uso validado**.
- Se nenhum bater 5k após 20 vídeos postados: o problema **não é monetização, é o produto**. Itere na qualidade antes.

**Etapa 2 (Fase C):** Automatize a postagem (YouTube Data API + TikTok Content Posting API). 1 canal = 1 vídeo/dia automático. Custo ~$1/dia.

**Etapa 3 (Fase D, só se Etapas 1-2 validarem):** Reabrir SaaS com showcase *real*. "Esse canal fez 500k views em 30 dias, feito 100% com ClipIA. Pague $29/mês pra fazer o seu."
- Stripe/MP checkout
- Planos: $9 (10 vídeos/mês), $29 (50 vídeos/mês), $99 (ilimitado)
- Meta: 20 usuários pagantes em 60 dias = $580/mês recorrente

**Por que essa ordem?** Se você pular direto pro SaaS, vai gastar $500+ em ads pra ganhar 5 trial users que vão cancelar em 2 semanas. Se bobear gasta a runway inteira antes de achar PMF.

### 2.3. **Não construa o que você não vai usar**

Hoje o editor Remotion está implementado mas você nunca editou um vídeo de verdade. Quando a Fase B der mídia boa, **você vai querer ajustar** o timing de cena, trocar uma imagem que ficou ruim, mudar hook. Aí o editor vai ser usado.

Mas até lá, não adicionar feature ao editor. **Deixa ele dormindo** igual o SaaS.

Aliás: o mesmo vale pro sistema de créditos, Mercado Pago, referral, blog. Tudo código vivo mas **UI desativada no creator-first**. Vai ressuscitar em Fase D se monetização validar.

### 2.4. **Riscos técnicos pra ficar de olho**

- **GTX 1660 4GB não renderiza gpt-image-1 local** (nem Flux, nem SDXL). Todos via API paga. Isso **amarra o custo por vídeo**.
  - gpt-image-1 (1024x1536, baixa qualidade): ~$0.04/imagem. 5 imagens/vídeo = $0.20/vídeo
  - gpt-image-1 alta: ~$0.17/imagem. 5 imagens = $0.85/vídeo
  - **Decisão:** começar com quality baixa/média. Só subir se validar pipeline.
- **ElevenLabs free tier**: 10k chars/mês ≈ 13 vídeos. Se virar creator real, precisa Starter ($5/mês = 30k chars) ou Creator ($22/mês = 100k chars).
- **Cloudflare tunnel depende da máquina estar ligada 24/7**. Para 1 canal automático, OK. Para SaaS sério (Fase D), migrar stack pra VPS (Hetzner $5/mês) é quase obrigatório.

### 2.5. **Coisa esquisita que vi e você deveria revisitar**

- `test_tts_invalid_voice` já estava falhando antes da Fase A. Deveria ser investigado ou removido — testes quebrados envenenam a suite.
- A coluna `template_id` em `jobs` existia só em alguns ambientes porque foi adicionada por SQL ad-hoc, nunca via migration. Mesmo gap com `editor_state`/`exported_at`. **Auditar o schema inteiro**: rodar `alembic check` ou comparar `Base.metadata` com o banco, pegar todos os drifts de uma vez.
- Tem 3 guards no código que foram commits bem específicos mas podem estar desatualizados: `_refund_job_credit`, `_handle_soft_timeout`, `task_reject_on_worker_lost`. Rever se ainda fazem sentido com Groq API (lá era Whisper local que podia travar — agora é rede).

---

## 3. Plano Fase B (sugerido, para spec completa na próxima sessão)

### Escopo da Fase B

**Objetivo:** substituir Pexels por imagens geradas via gpt-image-1/2 como mídia primária. Criar 1 novo template ("novelinha") que use sequência de imagens em vez de vídeos.

### Tasks esboçadas

1. **Verificar gpt-image-2** — Gui pediu pra usar. **Na abertura da próxima sessão, rodar**:
   ```
   WebFetch https://developers.openai.com/api/docs/guides/image-generation
   ```
   Se gpt-image-2 existir, usar. Se não, usar gpt-image-1 (estado atual da API).
2. **Provider `OpenAIImageProvider`** — `app/services/image_provider.py`
   - Método: `generate(prompt, size="1024x1536", quality="medium") -> Path`
   - Usa `settings.OPENAI_API_KEY` (já tem)
   - Retorna PNG em `storage/jobs/{id}/images/scene_N.png`
   - Retry policy similar ao Groq
3. **Nova fase no pipeline** — entre `generate_script` e `fetch_media`:
   - `generate_images` task (Celery) — chama OpenAIImageProvider para cada cena
   - Se template usa `media_type: "ai_image"`, pula Pexels
4. **Template novo `novelinha_historica`** em `app/templates.py`
   - 6-8 cenas
   - media_type: ai_image
   - prompt template por cena: `"{topic} — cena {n}/{total}: {scene.visual_hint}. Estilo cinematográfico, composição vertical 1024x1536, cores saturadas."`
   - voice_provider: elevenlabs (voz "Adam" ou similar dramática)
   - script.needs_visual_hint = true (novo campo no roteiro)
5. **ScriptWriter expandido** — pedir `visual_hint` em cada cena do JSON do Claude
6. **Testes TDD** — mock OpenAI, testar provider
7. **Ken Burns effect** no compositor — imagens estáticas precisam de zoom/pan suave pra não ficarem paradas
8. **Validação:** gerar 3 vídeos de novelinha (budget ~$2), comparar com stock_narration, decidir se substitui ou coexiste

### Budget estimado Fase B
- Testes: $3
- 3 vídeos novelinha production: $3
- Buffer: $4
- **Total: $10** (exatamente o orçamento inicial)

### Não fazer em Fase B
- YouTube auto-upload (é Fase C)
- Novo template "fact-check" (pode ser Fase B.2 se tiver tempo)
- Editor de imagens (edição manual pós-geração)
- Variantes de voz ou tradução

---

## 4. Plano Fase C (roadmap só, após B validar)

- Entidade `Channel` no Postgres (tema, template, voz, horário, quota diária)
- Celery Beat agendando geração diária
- YouTube Data API v3 upload (OAuth conta do Gui)
- TikTok Content Posting API (aprovação é chata, deixar pro fim)
- Dashboard mostrando stats de views/watch time via YouTube Analytics API

## 5. Plano Fase D — Fork de decisão (60 dias após C)

Decisão que deve ser tomada com dados reais:

- **Se 1+ canal bater 1000 inscritos:** continuar creator, escalar 3-5 canais paralelos. Manter SaaS dormente.
- **Se nenhum canal engajar mas existe demanda validada externamente** (posts no Twitter/Linkedin gerando contatos): reabrir SaaS com showcase, Stripe, planos.
- **Se nada engajar:** considerar se o produto tem saída ou se é hora de pivotar.

---

## 6. Decisões a validar com o Gui na próxima sessão

1. **PR #1 merge strategy** — mergear como está (big bang, 289 arquivos) ou primeiro mergear `backup/2026-04-15-srv01-final` em `main` e criar PR limpo só da Fase A?
2. **gpt-image-1 vs gpt-image-2** — verificar se a v2 existe e qual a diferença de custo/qualidade. Se v2 for demasiado caro, usar v1.
3. **Persistência via NSSM** — rodar scripts agora ou pode esperar? Sem NSSM, reiniciar o PC mata a stack.
4. **Canal piloto tema** — Novelinha curta (polarizado, tipo Tramas Cinematograficas) ou Curiosidades científicas (amplo, tipo Minutephysics)? Ou ambos em paralelo?
5. **Voz ElevenLabs** — você tem uma voz favorita clonada ou vamos usar uma default premium pt-BR?

---

## 7. Pontos técnicos pra relembrar (cola rápida)

- Python venv: `.venv312` (3.12.10), Python 3.14 existe side-by-side mas **não usar**
- Backend: `uvicorn app.main:app --host 127.0.0.1 --port 8005`
- Worker: `celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo` (solo obrigatório no Windows)
- Frontend: `npm run dev -- -p 3003`
- Subir tudo dev: `.\scripts\start-all.ps1`
- Wrappers que propagam env vars: `scripts/_run-backend.ps1`, `_run-worker.ps1`, `_run-frontend.ps1`
- Script que valida env vars: `.\scripts\check-env.ps1` (deve retornar exit 0)
- Admin: `gbbraga.dev@gmail.com` / senha em `.admin-credentials.local` (gitignored)
- Groq Whisper: `settings.GROQ_WHISPER_MODEL = "whisper-large-v3"`, retorna dicts (não objects)
- FFmpeg path escape: double-escape no filter graph (`_ff_escape_path` em `app/services/compositor.py`)
- DNS: `autoshorts.gbbragadev.com` e `api-autoshorts.gbbragadev.com` → tunnel `onwatch` (config em `~\.cloudflared\config.yml`)
- Tunnels do Gui (não quebrar): `voice-api`, `seniormcp`, `usage`, `fluxo`, `gbbragadev.com`

---

## 8. O que NÃO fazer

- Não commitar `.env`, `.admin-credentials.local`, `storage/jobs/*`, `storage/service-logs/*`
- Não criar novo tunnel Cloudflare — usar `onwatch` existente
- Não mexer em credenciais via `.env` — sempre User scope env var
- Não adicionar feature ao editor Remotion antes de haver vídeos pra editar
- Não implementar Stripe/pagamentos antes de ter canal validado
- Não deletar `transcriber_local.py.bak` — preservação histórica
- Não rodar pip install sem venv ativo (instalaria no Python 3.14 global)

---

## 9. Referência rápida de gpt-image

**Doc oficial:** https://developers.openai.com/api/docs/guides/image-generation

**Via MCP `context7`:**
```
query-docs: openai image generation
```

**Via WebFetch:**
```
WebFetch url="https://developers.openai.com/api/docs/guides/image-generation" prompt="What's the current model ID for image generation, pricing, and sizes supported?"
```

**Chave de API:** `OPENAI_API_KEY` (alias de `OPEN_API_CLIPIA_TOKEN`, já setado em User scope).

---

**Boa. Quando chegar lá, entre na sessão com este doc aberto e invoke `/brainstorming` pra cravar o escopo exato da Fase B.**
