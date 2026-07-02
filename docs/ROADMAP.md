# ClipIA — Mapa & Roadmap

> Atualizado em **2026-07-02** (pós-auditoria de go-live). Foto de onde o produto está e para onde seguir.
> Objetivo-norte: **plataforma de criação de vídeos curtos com IA para monetização** (creator-first).

---

## 1. Onde estou (estado real)

**clipia.com.br** no ar via Cloudflare Tunnel (single-machine, SPOF assumido). Branch ativa feat/frontend-elevacao.
**337 testes verdes**, pipeline validado ao vivo. Pós-auditoria de go-live (2026-07-02): webhook Stripe
normalizado (SDK>=15), MP oculto do checkout (sem registro no painel), auto-restart em todos os
launchers, backup Postgres diário agendado, créditos do admin reduzidos. Pendências do fundador: ligar
Turnstile, confirmar webhook Stripe/Pix no painel, uptime externo (ver SECURITY.md e GO-LIVE-CHECKLIST.md).

```
                         ┌──────────────────────────────────────┐
                         │           clipia.com.br              │
                         │   (Cloudflare Tunnel → :3003 prod)   │
                         └───────────────┬──────────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
     ┌──────▼──────┐            ┌────────▼────────┐          ┌────────▼────────┐
     │  FRONTEND   │            │     BACKEND     │          │     WORKER      │
     │ Next 16/R19 │  /api ───► │ FastAPI :8005   │ ───────► │ Celery (solo)   │
     │ Remotion 4  │ /storage   │ Postgres+Redis  │  enfileira│  pipeline IA    │
     └─────────────┘            └─────────────────┘          └─────────────────┘
```

### Pipeline de geração (Celery chain)
```
 trend? ─► generate_script ─► [generate_images] ─► synthesize_audio ─► transcribe ─►
          (LLM + tendência)     (gpt-image-2)      (ElevenLabs/Edge)   (Groq Whisper)
                                                                            │
          finalize  ◄──  compose_video  ◄──  fetch_media  ◄────────────────┘
          (+ VINHETA)    (FFmpeg/NVENC      (Pexels, scored)
                          + SFX + música
                          + quality gate)
```

---

## 2. O que o ClipIA já faz (capacidades por área)

| Área | Capacidade | Estado |
|---|---|---|
| **Roteiro** | LLM via OpenRouter (DeepSeek V4 Pro) + **fallback FREE Nemotron** | ✅ vivo |
| **Tendências** | Painel "Em alta" (Reddit/HN/Google Trends BR, sem chave) injeta contexto no roteiro | ✅ vivo |
| **Voz** | ElevenLabs (primário) + Edge TTS (fallback), 3 vozes pt-BR | ✅ vivo |
| **Legendas** | Word-level via Groq Whisper API (free tier) | ✅ vivo |
| **Mídia** | Pexels com **scoring** (sem repetir clipe, resolução/duração) + CLIP opcional | ✅ vivo |
| **Imagem IA** | gpt-image-2 + Ken Burns — template `ai_visual` p/ qualquer tema | ✅ vivo |
| **Áudio rico** | SFX (whoosh nas transições) + música automática por mood do template | ✅ vivo (sem UI) |
| **Diálogo** | 2 vozes alternando (`dialogue_duo`, ElevenLabs text_to_dialogue) | ⚠️ vozes EN |
| **Voice Design** | Criar voz por descrição (`POST /voices/design`) | ✅ vivo (só API) |
| **Qualidade** | Quality gate pós-render (mudo/preto/duração) → grava `quality_warning` | ✅ vivo |
| **Vinheta** | Selo de marca no fim (freeze+blur+logo+"clipia.com.br") | ✅ RESTAURADA |
| **Editor** | Remotion (preview 9:16, 5 abas, undo/redo, auto-save, export fiel) | ✅ vivo |
| **Render** | FFmpeg/NVENC (rápido) na geração; Remotion no export editado | ✅ vivo |
| **SEO** | 7 páginas `/criar/[nicho]` SSG + `/exemplos` + JSON-LD | ✅ vivo |
| **Mobile** | Editor com reflow nativo, hambúrguer, polish completo | ✅ vivo |
| **Auth/Deploy** | JWT, OTP via Resend, signup público, prod persistente (scheduled task) | ✅ vivo |

---

## 3. Quick wins — pronto mas subutilizado (baixo esforço, alto retorno)

Coisas que **já existem no backend** mas faltam expor/polir. Maior ROI imediato:

1. **UI para áudio rico** — SFX, música e seleção de mood não têm controle no editor/dashboard.
   Hoje ligam por flag de config. Expor 2-3 toggles = vídeos mais profissionais sem novo backend.
2. **Vozes pt-BR no diálogo** — `DIALOGUE_VOICE_A/B` ainda são premade EN (sotaque). Trocar por
   vozes pt-BR da conta ElevenLabs (1 linha de config + ids).
3. **UI de Voice Design** — endpoint pronto, sem tela. Aba "IA" do editor → criar voz por descrição.
4. **`/noise.svg` 404** — textura decorativa faltando em `frontend/public/`. Trivial.
5. **Fallback OpenAI p/ roteiro** — quando OpenRouter cai (já temos Nemotron FREE; um 2º elo barato fecha).

---

## 4. Para onde seguir — eixos de melhoria

> **Ordem pós-go-live (2026-07-02):** antes A->B->C->D. Reordenado para **D -> A -> B -> E**, com
> **C (Distribuição) adiado** até haver ~100 pagos. Racional: sem monetização fechada e operação estável,
> investimento em escala/distribuição é prematuro.

```
                         ┌─────────────────────────┐
                         │   OBJETIVO: MONETIZAR    │
                         │  criação de vídeos curtos│
                         └────────────┬─────────────┘
         ┌──────────────────┬─────────┴────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
  ┌────────────┐    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ A. QUALIDADE│    │ B. ESCALA/   │   │ C. DISTRIBUI-│   │ D. NEGÓCIO/  │
  │  do vídeo   │    │  VOLUME      │   │  ÇÃO         │   │  RECEITA     │
  └────────────┘    └──────────────┘   └──────────────┘   └──────────────┘
```

### Diferencial competitivo (por que pagar o ClipIA vs Vidnoz/Pictory/InVideo)
- **Voz pt-BR nativa** (ElevenLabs + Edge, 3 vozes BR) — concorrentes globais soam gringo.
- **Editor Remotion fiel** (editor == export): o que se vê no preview é o que renderiza.
- **Custo baixo por GPU local** + cascata LLM com fallback graceful (não quebra, degrada honesto).
- Nichos BR + templates de alto engajamento (novelinha, ai_video Seedance, curiosidade).

### Eixo A — Qualidade do vídeo
- Expor áudio rico no editor (quick win #1) + presets de "estilo" por nicho.
- B-roll mais inteligente: usar o CLIP rerank por padrão (avaliar custo/GPU) p/ casar cena↔clipe.
- Mais templates de alto engajamento (curiosidade, novelinha, "você sabia", listas).
- Brand kit por usuário (logo/cor/fonte na vinheta) — base p/ plano pago.

### Eixo B — Escala / volume (creator que posta todo dia)
- **Geração em lote**: 1 tema → N variações (hooks/ângulos diferentes) numa tacada.
- **Agendador**: fila de temas → gera X vídeos/dia automaticamente.
- Reaproveitar tendências: do painel "Em alta" direto p/ geração em 1 clique.

### Eixo C — Distribuição (foi ADIADA de propósito — retomar quando núcleo maduro)
- Publicação/agendamento direto (YouTube Shorts / TikTok / Reels APIs).
- Export multi-formato (9:16 + 1:1 + 16:9) da mesma timeline.
- Legendas/hashtags/título otimizados por plataforma (já temos LLM).

### Eixo D — Negócio / receita (transformar uso em dinheiro)
- **Planos + créditos**: já há contagem de créditos por template; falta paywall/billing real.
- Marca d'água removível só no plano pago (vinheta já é o gancho).
- Métricas de uso por conta → upsell. Onboarding do creator (do signup ao 1º vídeo).

### Eixo E — Operação & Confiabilidade (novo — base para tudo)
- **Uptime externo** (UptimeRobot batendo /api/v1/health/deep) — teria pego o downtime de 18h. **Pendência do fundador.**
- Backup automático do Postgres (OK diário 02:00 desde 2026-07-02) + **cópia externa via rclone** (pendente).
- Auto-restart dos launchers (OK 2026-07-02); **Turnstile ligado** (pendente de chave CF).
- Runbook de DR + resposta a abuso (ver SECURITY.md).
- SLA/SLO documentado quando houver tráfego pago sustentado.

---

## 5. Recomendação de próxima sessão

**Sprint sugerido (ordem de ROI, pós-go-live):**
1. **Eixo E** — uptime externo + Turnstile ligado + backup externo (fecha operação; pré-requisito de tráfego pago).
2. **Eixo D** — paywall/billing visível + marca d'água no plano grátis (fecha monetização; 1ª venda real).
3. **Eixo A** — quick wins #1/#2 (UI áudio rico + vozes pt-BR) → salto de qualidade percebida.
4. **Eixo B** — geração em lote → ferramenta de creator que posta todo dia.

> **Eixo C (Distribuição) adiado** até A+B+D+E sólidos e ~100 pagos — publicar vídeo ruim não escala.

---

### Referências de contexto (memórias)
- Estado git/branches → `git-branches-local-only`
- Deploy/prod → `clipia-deploy`
- Features desta leva → `trends-quality-elevenlabs`
- LLM/OpenRouter → `llm-openrouter-deepseek`
- Plano de retomada original → `revival-plan-vitrine-qualidade`
