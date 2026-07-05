# Prompt de continuação — Estúdio de Marketing ClipIA (sessão 2+)

> **Como usar:** abra uma sessão nova (Fable 5) em `C:\Dev\clipia` e cole este arquivo
> como primeira mensagem (ou diga "leia docs/FABLE-MARKETING-PROXIMA-SESSAO.md e siga").
> A persona base permanente é `docs/FABLE-MARKETING-VIDEO-PROMPT.md` — leia-a PRIMEIRO
> e opere sob os 7 gates dela. Este arquivo é o ESTADO + BACKLOG da produção.

---

## ESTADO (04/07/2026 — fim da sessão 1)

**Hero ad v1 entregue e aprovado com nota 8/10 pelo fundador.**

- Conceito: **"Este vídeo foi feito por IA"** (hook de prova auto-referencial, TOFU).
  Roteiro completo com gates em `marketing/hero-ad/roteiro.md` (verdict GO).
- Entregáveis (no disco, fora do git): `marketing/hero-ad/renders/`
  - `clipia-hero-ad-9x16.mp4` — hero 49,5s (com vinheta oficial)
  - `cutA-teaser-wpp.mp4` (18s, hook+CTA) · `cutB-demo-wpp.mp4` (18s, demo+CTA)
  - Enviados no WhatsApp do Gui em 04/07.
- Assets prontos para reuso em `marketing/hero-ad/`:
  - **VO**: `audio/vo3-carla.mp3` (46,6s, usada) e `audio/vo3-daiane.mp3` (49,1s,
    variante A/B pronta, mesmo take) + `audio/words3-*.json` (timestamps word-level)
  - **Música**: `audio/music.mp3` (50s, Eleven Music sob medida, 124 BPM)
  - **SFX**: whoosh/riser/impact/click/keys (ElevenLabs)
  - **Clips IA**: `clips/b1|b2|b5-coral.mp4` (usados) + `clips/b1|b2|b5.mp4`
    (variantes roxo/azul NÃO usadas — paleta antiga)
  - **Capturas reais do produto**: `captures/*.webm` (dashboard, Em alta, editor
    desktop, landing) + scripts Playwright reproduzíveis
  - **Pipeline**: `compose.py` (segs→chain→finish), `make_ass.py` (legendas),
    `build_cuts.py` (cuts), `render_cta.py` + `cta.html` (arte CTA)

## FATOS TÉCNICOS (não redescobrir — já validado)

1. **OpenRouter GERA VÍDEO**: `POST https://openrouter.ai/api/v1/videos` com
   `{model:"bytedance/seedance-2.0-fast", prompt, duration, resolution:"720p",
   aspect_ratio:"9:16", generate_audio:false}` → 202 + polling_url → download em
   `<polling_url>/content?index=0`. **$0,60/clip** (5-6s). `chat/completions` dá 500
   (erro da sessão Traço Urbano). O listing `/models` NÃO mostra modelos de vídeo.
2. **Saldo OpenRouter: ~$6,44** (04/07). REGRA: estimar custo e pedir OK antes de
   gastar; teto por sessão só com autorização explícita do Gui.
3. **ElevenLabs** (key `ELEVEN_LABS_CLIPIA_KEY`, uso à vontade):
   TTS `POST /v1/text-to-speech/{voice}?output_format=mp3_44100_192`
   (`eleven_multilingual_v2`, stability 0.65, similarity 0.80, style 0.10,
   speaker_boost, speed 0.95, take ÚNICO contínuo com `<break time="0.6s" />`);
   Música `POST /v1/music` (`{prompt, music_length_ms}`);
   SFX `POST /v1/sound-generation` (`{text, duration_seconds ≥ 0.5}`).
4. **Casting pt-BR**: Carla `7eUAxNOneHxqfyRS77mW` (escolhida, registro comercial),
   Daiane Cândido `nHNZWlqUWtEKPr3hhFQP` (didática). NUNCA modelo turbo.
5. **Pronúncia da marca no TTS**: grafar "**Clipia**" (fala "Clípia"); NUNCA "ClipIA
   vê" (vira "clipe a ver" — usar "olha"). QA de pronúncia = transcrever no Groq
   Whisper (`GROQ_API_KEY`, free) com `timestamp_granularities[]=word`.
6. **Marca ATUAL = CORAL/grafite** (`#f05340` sobre `#0b0a0e`), wordmark "Clip"+"IA",
   fonte **Geist** (`frontend/node_modules/geist/dist/fonts/geist-sans`). O gradiente
   roxo→azul do CLAUDE.md é a marca ANTIGA — não usar em visuais novos.
7. **Vinheta**: `app.services.outro.append_outro(path)` (venv312, `sys.path` no repo)
   funciona em qualquer mp4 — usar em todo entregável.
8. **Capturas logadas**: JWT via `app.auth.service.create_access_token(user_id)` →
   localStorage `clipia_token`. User admin: `f921be8a-2689-418a-b302-c736624ef3e5`
   (gbbraga.dev). Job demo bom p/ editor: `8f4686a3-07ed-4c32-a4a0-dc9ec29e60fb`.
   Editor DESKTOP (1440×900) mostra o player; no mobile ele não aparece.
   NÃO clicar em Resetar/Gerar/Exportar às cegas (custam créditos).
9. **Envio WhatsApp**: skill `enviarwpp`. Vídeo >16MB recomprimir (crf 22).
   Se conexão falhar com container Up: `docker.exe restart evolution_api`
   (port-forward 8081 wedga). Instância `grafana-alerts`, estado deve ser "open".
10. **Gotchas gerais**: OpenAI keys 401 em 04/07 (gpt-image indisponível; avisar Gui
    se precisar); RTK quebra `git commit -m` → usar `-F arquivo`; frontend prod =
    `restart-frontend.ps1` via schtask temporária (`.next` já foi apagado uma vez);
    hook reescreve `docker`/`pip` → usar `docker.exe` / `python -m pip`.

## O QUE SEPARA O 8 DO 9-10 (hipóteses de iteração, em ordem de alavancagem)

1. **Hook A/B**: só temos o hook de prova no ar. Testar hook 2 (dor: "Três horas
   editando pra um vídeo de trinta segundos") com os MESMOS assets (custo ~zero).
2. **Voz A/B**: montar o hero com `vo3-daiane.mp3` (precisa só re-rodar make_ass +
   finish com os words dela — 20 min, $0).
3. **Editor tocando de verdade**: a captura atual do editor está estática (play do
   Remotion não disparou no headless). Conseguir o player rodando com legendas
   animando = money shot mais forte no b4.
4. **Motion design nos overlays**: as legendas têm fad+cor; falta kinetic typography
   nos momentos-chave (ex.: "palavra por palavra" estourando na tela).
5. **Grading por cena** + vibração humana (b-roll UGC de creator usando o produto,
   se o Gui gravar 10s de tela de celular na mão).
6. **Cortes no beat medidos** (hoje são nos tempos da VO; detectar onsets da música
   e ajustar ±100ms).

## BACKLOG DE DISTRIBUIÇÃO (depende de decisão do Gui — perguntar antes)

- Publicação orgânica: Reels/TikTok/Shorts (o Postiz do Traço Urbano existe;
  instância própria p/ ClipIA não está configurada).
- Meta Ads: hero como criativo TOFU (KPI: 3s view ≥25%, kill <15% / CTR <0,8%
  após ~2k impressões — declarado no roteiro.md).
- Variantes por plataforma (áudio/CTA/legenda nativos — gate G5).

## MODO DE OPERAÇÃO DA PRÓXIMA SESSÃO

1. Leia `docs/FABLE-MARKETING-VIDEO-PROMPT.md` (persona + gates) e este arquivo.
2. Pergunte ao Gui QUAL frente: iterar o hero (8→9), variantes A/B, novo conceito,
   ou distribuição. Se ele não especificar, recomende: **A/B de hook + voz**
   (maior alavancagem por dólar, ~$0-1,20).
3. Todo entregável novo: gates G1-G7 → QA visual por frames → enviar no WhatsApp
   (skill enviarwpp) como feito na sessão 1.
4. Custo: estimar ANTES, pedir OK para API paga (regra permanente do Gui).
