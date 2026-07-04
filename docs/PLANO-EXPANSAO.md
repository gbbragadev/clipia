# Plano de Expansão — ClipIA (backlog priorizado por ROI × risco)

> Backlog de features para o Fable 5 consumir sprint a sprint via `docs/FABLE-ELEVACAO-FULLSTACK.md`.
> Ordem: **TIER 0 (FUNDAÇÃO)** → **TIER 1 ([QUICK WIN])** → **TIER 2 ([PRÓXIMO TIER])** →
> **TIER 3 ([MOONSHOT])**. Cada item traz **valor**, **pré-requisito**, **atalho técnico** (onde
> reaproveitar código existente) e **gate de validação**.
>
> Princípio: o ClipIA é pré-go-live, single-machine, GPU 4GB. O foco agora é **fechar a 1ª venda
> real** (paywall + marca d'água) e **elevar a UX ao nível profissional**. Moonshots ficam para após
> ~100 pagos (ROADMAP Eixo C).

---

## TIER 0 — FUNDAÇÃO (pré-requisito de tudo; fazer junto com a elevação de UX)

| # | Feature | Valor | Atalho técnico | Gate de validação |
|---|---------|-------|----------------|-------------------|
| **F0-1** | **Player dedicado + download confiável** | Acesso rápido ao vídeo final = razão de existir do produto. Hoje quebrado (dor real do fundador). | `lib/download.ts:35` (`fetchAuthenticatedBlobUrl`); novo modal `components/dashboard/VideoPlayerModal.tsx`; eliminar corrida do `ExportPanel.tsx:102-187`. | Botão de download só habilita pós-render; spinner+progresso; toast sucesso/erro; player abre num clique. |
| **F0-2** | **Grid reativa + progresso em tempo real** | Usuário vê o job acontecer; não fica imaginando se travou. | Polling `fetchJobStatus` (`lib/editor-api.ts:258`) com backoff; SSE opcional via `/jobs/{id}/status`. | Card vai de `queued → processing → completed` sem F5; badge de passo atual visível. |
| **F0-3** | **Design tokens unificados (fim do roxo residual)** | Tudo que vier depois herda consistência visual. | Migrar `globals.css:31-33,94-96`; definir `--accent-primary` em `:root`; eliminar `#222` hardcoded do `ExportPanel`. | `tsc` limpo; nenhuma cor hardcoded em `.tsx`; paleta idêntica landing↔dashboard↔editor. |
| **F0-4** | **Estados impecáveis (loading/empty/error)** | Produto parece pronto, não MVP. | Substituir `EmptyState.tsx` fraco; skeletons reais; reaproveitar `ui/feedback.tsx` (ToastProvider/InlineError) em todo lugar. | Smoke em 375px e 1280px sem nenhum estado "feio" ou sem tradução. |

---

## TIER 1 — [QUICK WIN] (backend pronto ou quase; alto ROI pós-go-live)

### Q1 — UI de áudio rico no editor
- **Valor:** vídeos saem mais profissionais sem novo backend. SFX/música/mood já existem
  (`app/services/sfx.py`, `music.py`) mas não têm toggle exposto no editor.
- **Atalho técnico:** aba "Elementos" do editor já tem `MusicSelector`; expor toggles de SFX
  (whoosh nas transições) e intensidade de música. Adicionar preview de áudio antes de renderizar.
- **Gate:** ouvir o whoosh no preview Remotion; música respeita `voiceover` (ducking).

### Q2 — Vozes pt-BR no diálogo (`dialogue_duo`)
- **Valor:** template de diálogo ainda usa vozes EN (`app/config.py:82` `DIALOGUE_VOICE_A/B`).
- **Atalho técnico:** 1 linha de config se as vozes pt-BR existirem na conta ElevenLabs; senão,
  voice design de 2 vozes pt-BR (já existe `design_voice` em `elevenlabs_provider.py:121`).
- **Gate:** gerar um diálogo e confirmar 2 locutores pt-BR distintos no áudio final.

### Q3 — UI de Voice Design no dashboard
- **Valor:** usuário cria voz personalizada sem pedir suporte. Backend `design_voice` já existe.
- **Atalho técnico:** `dashboard/voices/page.tsx` + formulário (gênero, idade, sotaque, tom) →
  `POST /api/v1/voices/design`. Custo: 5 créditos.
- **Gate:** criar voz, listá-la em `voices/`, usá-la num vídeo.

### Q4 — Mais templates (curiosidade, "você sabia", listas top-10)
- **Valor:** ICP principal é curiosidades/histórias; hoje 8 templates mas faltam os formatos virais.
- **Atalho técnico:** adicionar em `app/templates.py:57` reaproveitando `stock_narration`/`ai_visual`
  com prompt de roteiro específico (gancho forte + lista numerada + CTA).
- **Gate:** gerar "5 curiosidades sobre o espaço" e o roteiro vir no formato lista com gancho.

### Q5 — Brand kit por usuário (logo, cores, fonte, end-screen)
- **Valor:** diferencial vs concorrentes globais genéricos; abre segmento de agências.
- **Atalho técnico:** tabela `BrandKit` em `app/db/models.py`; upload de logo; `outro.py` já gera
  selo — parametrizar. Overlay `EndScreen` (`components/editor/overlays/EndScreen.tsx`) já aceita
  username/perfil.
- **Gate:** configurar brand kit, gerar vídeo, ver logo+end-screen personalizados.

### Q6 — Feedback de força de senha no register
- **Valor:** polimento, reduz conta abandonada, eleva segurança percebida.
- **Atalho técnico:** `zxcvbn` ou heurística simples; `auth/register/page.tsx` já tem Turnstile
  integrado.
- **Gate:** senha fraca bloqueia submit com mensagem clara e visual (barra colorida).

### Q7 — Fallback OpenAI no roteiro + flag de degradação visível
- **Valor:** cascata LLM cai pra fallback free sem avisar — usuário paga crédito por vídeo pior.
- **Atalho técnico:** `app/services/llm.py:90` só loga warning. Persistir `degraded: true` no `Job`
  e mostrar badge "qualidade reduzida — reembolso de 1 crédito" no card.
- **Gate:** simular queda do provider primário, ver badge, ver crédito devolvido.

---

## TIER 2 — [PRÓXIMO TIER] (cria categoria, esforço médio, após primeiro punhado de pagos)

### P1 — Geração em lote (1 tema → N variações)
- **Valor:** criador precisa de volume (1-3 Shorts/dia). Hoje é 1 por vez.
- **Pré-req:** worker suporta enfileirar; UX de "gerar 3 variações de gancho/voz/template" e mostrar
  lado a lado.
- **Atalho técnico:** `dispatch_pipeline` já é idempotente por job; criar `POST /generate/batch`
  que dispara N jobs com semente comum; grid mostra "variações de {tema}" agrupadas.
- **Gate:** gerar 3 variações de "mistérios do oceano", baixar as 3, comparar.
- **Risco:** burn de crédito — requer confirmação explícita do custo total antes de disparar.

### P2 — Agendador de postagem (fila de temas → X vídeos/dia)
- **Valor:** "canal no piloto automático" — promessa que vende assinatura recorrente.
- **Pré-req:** tabela `ScheduledJob` (tema, nicho, horário, recorrência); cron Celery `beat`.
- **Atalho técnico:** `celery_app.py` já tem infra; `app/worker/tasks.py` já limpa órfãos — adicionar
  `task_scheduled_generate`.
- **Gate:** agendar "1 vídeo de curiosidade todo dia 9h", ver nascer no horário.
- **Risco:** qualidade cai sem curadoria; limitar a 1-2/dia por usuário.

### P3 — Analytics de vídeo (views, CTR, retenção) via OAuth YouTube
- **Valor:** fecha o loop "tema → vídeo → performance → próximos temas". Diferencial absurdo.
- **Pré-req:** OAuth YouTube por usuário; tabela `VideoMetrics`.
- **Atalho técnico:** `app/auth/` já tem padrão JWT/OAuth-like; servidor OAuth YouTube →
  `accounts.google.com`.
- **Gate:** conectar canal, ver views de um vídeo publicado na grid do dashboard.
- **Risco:** escopo OAuth, refresh tokens, ToS YouTube API.

### P4 — Export multi-formato (9:16 / 1:1 / 16:9) do mesmo roteiro
- **Valor:** mesmo conteúdo serve Reels, Feed, YouTube, Shorts. Multiplica valor sem re-gerar.
- **Atalho técnico:** `compositor.py` já parametriza layout; adicionar `aspect_ratio` no `Job`;
  Remotion `composition` width/height por formato.
- **Gate:** exportar o mesmo vídeo em 9:16, 1:1 e 16:9, baixar os 3.
- **Risco:** legendas/overlays precisam reposicionar por formato.

### P5 — Biblioteca pessoal de mídia (upload do usuário + busca semântica)
- **Valor:** reaproveita o motor CLIP da biblioteca Drive (`drive_library.py`) para o acervo do próprio
  usuário. Diferencial "minha biblioteca de b-roll".
- **Atalho técnico:** `media_library.py` já tem esqueleto; embeddings 512-dim já existem; adicionar
  upload + indexação por usuário.
- **Gate:** subir 5 clipes, buscar "praia ao pôr do sol", ver os relevantes.
- **Risco:** storage/custo; moderação de conteúdo uploadado.

### P6 — Templates específicos por nicho (roteiro/mídia/voz diferenciados)
- **Valor:** hoje nicho é só SEO no frontend; backend não diferencia. Especialização real = "ClipIA
  Religioso", "ClipIA Finanças" viram sub-produtos.
- **Atalho técnico:** `templates.py` + `scriptwriter.py` recebem `niche_id`; prompt de roteiro ganha
  regras por nicho (ex: religioso cita versículo, finanças cita número real com fonte).
- **Gate:** gerar vídeo "religioso" e "finanças" do mesmo tema, ver diferença de tom/citação.

### P7 — Marca d'água no plano grátis + paywall visível
- **Valor:** fecha a 1ª venda real (ROADMAP Eixo D). Hoje grátis = mesmo que pago.
- **Atalho técnico:** `compositor.py` drawtext condicional em `plan != 'paid'`; dashboard mostra
  CTA "remova a marca d'água — compre créditos".
- **Gate:** gerar vídeo grátis, ver marca d'água; comprar crédito, regenerar, ver sumir.
- **Risco:** UX do paywall — não pode ser agressivo a ponto de afastar teste grátis.

---

## TIER 3 — [MOONSHOT] (redefinem produto; só após ~100 pagos, ROADMAP Eixo C)

### M1 — Publicação direta YouTube / TikTok / Reels
- **Valor:** usuário não sai do ClipIA. Mata o concorrente global.
- **Pré-req:** OAuth por plataforma; respeitar quotas/ToS; fallback de download manual.
- **Risco:** APIs instáveis, ToS de cada plataforma, moderação automática, revogação de token.

### M2 — Agente autônomo de canal ("canal inteiro operando sozinho")
- **Valor:** "aponte um nicho e o ClipIA publica 1 Short/dia pra sempre". Diferencial de categoria.
- **Pré-req:** P2 (agendador) + P3 (analytics fechando o loop de temas performáticos) + M1.
- **Risco:** qualidade cai sem curadoria humana; burn de crédito; responsabilidade de conteúdo
  gerado/Postado em nome do usuário.

### M3 — A/B testing de thumbnails / ganchos / roteiros
- **Valor:** otimização orientada a dados; retém power-user.
- **Pré-req:** P1 (lote) + P3 (analytics).
- **Risco:** custo de crédito × variação; complexidade de UI de comparação.

### M4 — Colaboração em equipe / workspaces
- **Valor:** abre segmento agências (ICP secundário do GTM).
- **Pré-req:** multi-tenant em `User`/`Job`; permissões; billing por seat.
- **Risco:** explosão de escopo; adia foco no ICP principal (criador individual).

---

## Como o Fable consome este plano

- **Sprint a sprint:** pegar 1 item [QUICK WIN] + 1 item de TIER 0 (fundação) por rodada do prompt
  `docs/FABLE-ELEVACAO-FULLSTACK.md`.
- **Não pular tiers:** [MOONSHOT] só após validação de product-market fit (~100 pagos, ROADMAP).
- **Cada feature vira commit próprio** com `feat(<area>): <feature>` em pt-BR, gate de build verde,
  smoke visual, screenshot em `/` como evidência.
- **Atualizar este doc ao concluir um item** — mover para a seção "Concluído" abaixo com data + commit
  hash + screenshot de evidência.

---

## Concluído

| Data | Item | Commit | Evidência |
|------|------|--------|-----------|
| 03/07 | **F0-1a** Player dedicado (`VideoPlayerModal`: blob único p/ player+download+share) | `39a9b03` | `LIVE-elevacao-player-modal-0307.png` — vídeo tocou 0:47 completo; download real baixou `clipia-a71af092.mp4` |
| 03/07 | **F0-1b** Download confiável (progresso por stream + toasts; ExportPanel state machine + fix da corrida no `POST /render`) | `e8ec1a2` + `c5cd5aa` | `LIVE-elevacao-export-statemachine-0307.png` — botão bloqueado c/ "Renderizando com Remotion… 0%" ao vivo |
| 03/07 | **F0-2** Grid reativa (polling c/ backoff, `/jobs` expõe progress/current_step, onJobCreated) | `2266988` | 3 testes `test_jobs_realtime.py`; barra de progresso visível no smoke |
| 03/07 | **F0-3** Tokens unificados (fim do roxo residual; `--accent-primary` real; -886 linhas dead code) | `3a9fd52` + `0c12491` + `b2eddd5` | `LIVE-elevacao-landing-0307.png` + `LIVE-elevacao-dashboard-grid-0307.png` — zero roxo de marca |
| 03/07 | **F0-4 (parcial)** EmptyState rico c/ CTA; toasts consistentes em download/render/grid | `3a9fd52` | tsc+build verdes; skeletons ricos ainda pendentes |
| 03/07 | **BÔNUS** Export por Remotion estava QUEBRADO em prod: mídia buscada via domínio público fazia hairpin de 30s > timeout 28s do delayRender → render local usa 127.0.0.1:8005 | (sprint 03/07) | erro real reproduzido e corrigido no smoke E2E |

### Follow-ups anotados pela revisão adversarial (03/07)
- **Watchdog de render**: se o worker morrer antes de consumir a task de re-render, o job fica
  `rendering` para sempre (polling infinito) e os `pending_credits` debitados não voltam
  (reembolso só dispara em exceção DENTRO da task). Precisa TTL/watchdog (ex.: cleanup marca
  `error`+refund após N min sem heartbeat). Mesma família: job preso em `cancelling` há 19d na
  conta admin.
- Jobs `cancelling` antigos deviam normalizar para `cancelled` na listagem (higiene de status).
