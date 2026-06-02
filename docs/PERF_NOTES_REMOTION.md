# Remotion render spike — perf notes (Fase 1)

Data: 2026-06-02
Hardware: PC Windows do Gui, GPU GTX 1660 4GB, Celery `--pool=solo`.

## O que foi testado

`frontend/scripts/render-composition.mjs` renderizando a composição Remotion
`ShortVideo` (registrada em `frontend/src/remotion/Root.tsx`) a partir de um job
real gerado pelo pipeline (`6f9bcc62`, 30.5s, 1080×1920, 5 cenas — uma delas com
um clip Pexels de 131MB). Props montados por `scripts/build_remotion_props.py`.

Assets (narração.wav, media/scene_*.mp4) servidos por **HTTP** pelo backend que já
roda (`/storage/jobs` StaticFiles, `app/main.py:88`) — `http://127.0.0.1:8005/...`.
Não foi preciso `file://`, `publicDir` nem `staticFile()`. O alias `@/` foi
resolvido via `webpackOverride` (`@` → `src`) no `bundle()`.

## Resultados

| Métrica | Valor |
|---|---|
| Bundle (1ª vez / cache) | 3.3s / 1.1s |
| Download chrome-headless-shell | 108 MB (só na 1ª vez) |
| **Render steady-state** | **~105s** (1ª run 124s incluía o download) |
| Output | h264 + aac, 1080×1920, 30.55s, **31 MB** (crf 23) |
| Comparativo FFmpeg/NVENC | ~15s, 10.6 MB |

→ Remotion CPU é ~7x mais lento que FFmpeg/NVENC. O Remotion **não usa NVENC**
(encode libx264 em CPU). Parte do tempo é download+extração de frames das mídias
HTTP (o clip de 131MB pesa); jobs com mídia menor tendem a ser mais rápidos.

## Fidelidade

Frame a frame (ver `storage/remotion-spike/frame_*.png`): o render Remotion
reproduz **o que o editor mostra** — legenda no estilo `minimal` configurado
(caixa preta, texto branco), acento "É" correto, mídia e layout 9:16 corretos.
O FFmpeg divergia (legenda karaoke amarela no rodapé). **Watermark ausente** no
Remotion (gap conhecido — portar componente na Fase 2).

## Tuning disponível

- `crf` 23 → 31MB; subir para ~28 reduz bastante o tamanho com perda mínima.
- `concurrency` (default usou auto); ajustável ao CPU.
- `jpegQuality`, `pixelFormat=yuv420p` (já setado).

## Veredito: GO

A arquitetura Remotion-como-motor é **viável** na máquina do Gui. Custo: ~90s a
mais por render.

### Decisão em aberto para a Fase 2

- **A) Full Remotion**: tudo renderiza via Remotion (purista, escolha registrada).
  Fidelidade total; toda geração fica ~90s mais lenta.
- **B) Híbrido por etapa**: FFmpeg/NVENC na **geração inicial** (rápida, usuário
  esperando no dashboard) + Remotion no **export editado** (fiel, onde importa).
  O preview do editor já é Remotion, então editor==export continua fiel; só o
  primeiro rascunho auto-gerado usa FFmpeg. Melhor UX, mantém a fidelidade onde
  conta.

## Bug colateral encontrado

O worker escreve `script.json` (e provavelmente `words.json`) em **cp1252**
(default do Windows), não UTF-8 — quebrou leitura utf-8 no byte do "É". Corrigir
no pipeline (escrever com `encoding="utf-8"`) na Fase 2.
