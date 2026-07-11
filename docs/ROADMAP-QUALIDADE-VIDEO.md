# Roadmap de Qualidade de Vídeo — ClipIA

> Gerado 2026-07-05 por auditoria multi-agente (7 dimensões × audit + verificação adversarial + síntese). Alvo: levar o **output do produto** ao nível do anúncio hand-crafted (`marketing/concept3-anatomia/`, 9/10).

## ⚠️ Contexto de arquitetura (resolvido no código — leia primeiro)

Há **dois caminhos de saída** e isso decide quais gaps importam:

1. **Geração inicial** (o vídeo que TODO usuário recebe primeiro, ~15s) → **FFmpeg via `app/services/compositor.py`**. (`config.py:67` é explícito: "FFmpeg na geração inicial".)
2. **Export editado** (após mexer no editor, ~105s) → **Remotion** (`settings.RENDER_ENGINE="remotion"`, só governa `task_rerender_video`).

**A maioria dos fixes abaixo mira o caminho FFmpeg (geração inicial)** — é onde estão os gaps visíveis e é o que a maioria dos vídeos usa (nem todo mundo edita+exporta). O Remotion (export) já tem transições fade/slide/wipe, mas precisa de checagem paralela para o MESMO polish de áudio + para a vinheta (item 5).

> Nota de verificação: o agente da dimensão "composição" refutou o gap de xfade alegando que a geração inicial usa Remotion — **isso está errado** (confundiu `RENDER_ENGINE`, que é do export). O xfade **é** gap real na geração inicial FFmpeg. Corrigido aqui.

---

## TL;DR

O ClipIA **já tem toda a maquinaria** (Remotion, FFmpeg, legenda word-level, SFX, música automática, outro, CLIP rerank) — os gaps **não são features faltando, são tuning e polimento**: cor de marca errada (legenda amarela!), música quase inaudível (0.12), áudio sem ducking, Ken Burns só em imagem (não em vídeo), timing proporcional vs. beat. Caminho rápido: **~6 mudanças P0 triviais + 4 de áudio** sobem o output de ~6/10 para ~8,5/10.

---

## ✅ Já existe, NÃO mexer (evita retrabalho)

| Feature | Arquivo | Status |
|---|---|---|
| Transições no export | Remotion `ShortVideoComposition.tsx` | ✓ fade/slide/wipe wired (só no export, não na geração inicial) |
| Legenda word-level Groq | `transcriber.py`, `subtitles.py:43-122` | ✓ timestamps granulares, chunk até 3 palavras, `\kf` karaokê |
| Ken Burns em **imagens** | `compositor.py:122-159`, `SceneClip.tsx` | ✓ (falta só em **vídeos** — ver item 9) |
| Auto-música por template | `music.py`, `config.py:78` | ✓ 13 moods, loop |
| SFX whoosh automático | `sfx.py`, `tasks.py:759` | ✓ ElevenLabs, cacheado (mas só whoosh, cena-level — item 13) |
| Outro sting | `outro.py:21-171` | ✓ freeze+blur+logo+URL, no-op-safe (falta no export Remotion — item 5) |
| Watermark rodapé | `compositor.py:170-176` | ✓ clipia.com.br |
| Biblioteca Drive CLIP | `drive_library.py` | ✓ 10 tags, semântico cuda, anti-repetição |
| Imagem IA gpt-image-2 / Vídeo IA Seedance | `image_provider.py`, `video_gen_provider.py` | ✓ |
| Overlays CTA (endScreen/followCTA) | `compositor.py:179-242` | ⚠️ código existe mas **não wired** (item 6) |
| Guardrails MAX_SCENES / MAX_AI_VIDEO_PER_DAY | `config.py:144,152` | ✓ |

---

## 📋 Roadmap priorizado

### P0 — Quick wins (esforço S, impacto alto) — dias 1-2

> **Atualizado 2026-07-11 (verificação com evidência no código):** os 6 P0 já estão implementados. O trabalho aberto de áudio é o P1 (ducking, loudnorm).

| # | Gap | Mudança concreta | Arquivo | Imp | Status |
|---|---|---|---|---|---|
| 1 | Legenda destaca em **amarelo** `#FFFC00` (não coral) | `accent_color` default → `#F05340` | `subtitles.py:55/67` | 🔴 | ✅ FEITO |
| 2 | Texto do outro branco, não coral | `fontcolor=white` → coral/outline | `outro.py:90` | 🟡 | ✅ FEITO |
| 3 | **Música quase inaudível** (0.12 ≈ 4,6× baixo) | `AUTO_MUSIC_VOLUME 0.12 → 0.30` (escolhido 0.30, não 0.45 — "audível" sem competir com a voz enquanto não há ducking) | `config.py:79` | 🔴 | ✅ FEITO |
| 4 | Sample rate heterogêneo (24k/44k/48k) = artefato | `aresample=48000` antes de cada `[N:a]` — presente nos 3 caminhos de áudio | `compositor.py:328,392,613` | 🟡 | ✅ FEITO |
| 5 | **Vinheta some no export Remotion** | `append_outro()` na geração (`tasks.py:1042`) E no rerender (`tasks.py:1225`) | `tasks.py` | 🔴 | ✅ FEITO |
| 6 | Overlays CTA existem mas nunca invocados | rerender passa `overlays=comp_data.get("overlays")` (`tasks.py:1217` → `compositor.py:578`). Geração inicial não passa — overlays são artefato do editor, verificar se precisa | `tasks.py`, `compositor.py` | 🟡 | ✅ FEITO (export) |

### P1 — Esforço médio, impacto alto — dias 3-7

| # | Gap | Mudança concreta | Arquivo | Imp |
|---|---|---|---|---|
| 7 | ~~**Sem ducking**~~ ✅ FEITO 11/07 — `_audio_mix_filter()` compartilhado pelos 3 layouts; medido −7,2dB na música sob a voz (encode real) | `sidechaincompress=threshold=0.035:ratio=7:attack=25:release=420` | `compositor.py` (helper único) | 🔴 |
| 8 | ~~Loudness flutuante~~ ✅ FEITO 11/07 — `loudnorm` no bus final de TODOS os caminhos (com e sem música); medido −13,6 LUFS (encode real) | `loudnorm=I=-14:TP=-1.5:LRA=11` + aresample 48k pós-loudnorm | `compositor.py` (`_LOUDNORM_AF`) | 🟡 |
| 9 | Vídeos Pexels sem drift (Ken Burns só em imagem) | `zoompan` em `_prepare_video_scene`, campo `zoom_drift` (0.03) | `compositor.py:92-119`, `templates.py` | 🟡 |
| 10 | Imagens/screenshots full-cover (crop) vs card | novo `_prepare_card_scene` (gblur 42 + eq + fg centrado + drift) — ref `marketing/concept3-anatomia/compose.py:74-90` | `compositor.py:161-167` | 🟡 |
| 11 | Legenda cobre money-shot | `suppress_windows` (pular chunks numa janela) | `subtitles.py:43-122`, `tasks.py:769-778` | 🟡 |
| 12 | **Geração inicial = hard cuts** (sem xfade) | `tpad`+`xfade` (dissolve/fadeblack por beat) — ref `compose.py:xfade()` | `compositor.py:532-550` | 🔴 |
| 13 | SFX cena-level, não beat/word | `mix_transitions(words=...)` map SFX aos word timestamps | `sfx.py:75-88`, `tasks.py:759-789` | 🟡 |

### P2 — Complexo ou impacto médio

| # | Gap | Mudança | Arquivo | Esf/Imp |
|---|---|---|---|---|
| 14 | Sem "money-shot" (captura do próprio app) | `scripts/screenshot_app.py` (Playwright + JWT mock) → injeta cena 2-3 | novo + `tasks.py:task_fetch_media` | M/🟡 |
| 15 | CTA card coral nunca gerado | `render_cta_card()` (HTML coral→PNG) overlay antes do outro | `outro.py`, `tasks.py` | M/🟡 |
| 16 | CLIP rerank não é default | ativar `MEDIA_RERANK='clip'` se `DEVICE=='cuda'` (+15-20% relevância, ~30ms) | `config.py:72`, `media.py:77` | S/🟡 |
| 17 | Transição sempre genérica | campo `transition_type` (auto/fadeblack/dissolve); scriptwriter já suporta | `templates.py`, `compositor.py:535-545` | S/🟡 |
| 18 | Fonte Montserrat 52 vs Geist 96 | default `Geist` + `96` (checar `FONT_PATH`) | `subtitles.py:49`, `SubtitleEditor.tsx` | S/🟡 |
| 19 | MarginV 180 vs 300 | default `margin_v=300` | `subtitles.py:52` | S/🟡 |
| 20 | Palavra ativa não "salta" (só `\kf` fill) | modo 'pop': N eventos/chunk com color-swap + `\fad(30,0)` | `subtitles.py:103-115` | M/🟡 |
| 21 | Timing proporcional vs beat/word | derivar duração de cena de `words.json` (refator estrutural) | `compositor.py:506-510`, `scriptwriter.py` | L/🟡 |
| 22 | Sem anti-seed LLM (roteiro repete) | `seed=hash(topic+style)` no payload | `llm.py:57-67` | S/🔵 |

---

## 🎯 Sequenciamento sugerido

- **Dias 1-2 (P0 cores+volume+export):** itens 1,2,3,5 — 30 min de mudança, impacto perceptível imediato (marca coral + som audível + vinheta no export). Testar gerando 1 vídeo novo.
- **Dias 3-4 (áudio pro):** itens 7,8,4 — ducking + loudnorm + aresample. Testar no fone/celular.
- **Dia 5 (transições):** item 12 (xfade na geração inicial).
- **Dias 6-7 (legendas):** itens 11,18,19 + item 6 (overlays wired).
- **Dias 8-9 (Ken Burns + card):** itens 9,10.
- **Dia 10+ (P2 conforme prazo):** money-shot, CTA card, CLIP default, beat-snapping.

## Métricas de sucesso

| Métrica | Baseline | Alvo | Como verificar |
|---|---|---|---|
| Cor destaque legenda | amarelo `#FFFC00` | coral `#F05340` | frame do render |
| Ducking | plano (música×voz 1:1) | música −7dB sob a voz | waveform/SPL |
| Transições (geração inicial) | hard cut | dissolve/fadeblack 0.3-0.5s | frame-a-frame |
| Volume música | 0.12 (inaudível) | 0.45 + ducking | ouvir no celular |
| Vinheta no export | ausente | presente | duração/tail do arquivo |

## 🚨 Não fazer
- ❌ Refazer tudo em Remotion (a geração inicial FFmpeg funciona; melhorar > reescrever).
- ❌ Trocar FFmpeg por NVENC SDK / IA text-to-motion (custo × ganho ruim).
- ❌ Virar o output do usuário num anúncio (branding sutil, não hard-sell).

---

**Próximo passo recomendado:** executar **P0 (itens 1,3,5) + áudio P1 (item 7)** — os 4 que mais mudam a percepção no celular (marca coral + som audível com ducking + vinheta no export), tudo com teste de regressão (`pytest -q` + gerar 1 vídeo).
