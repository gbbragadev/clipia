# Outro Sting de Marca — Design

**Data:** 2026-06-14
**Status:** Aprovado (aguardando review do spec antes do plano)
**Branch sugerida:** `feat/outro-sting-marca`

## Problema / Motivação

Todo vídeo gerado pelo ClipIA sai sem nenhuma assinatura forte de origem. A marca
d'água textual atual (`WATERMARK_ENABLED`, "clipia.com.br" no canto) é discreta e fácil
de ignorar/cortar. Queremos um **sting de outro** — igual ao clipe de ~1s que o TikTok
anexa ao exportar — que feche todo vídeo com a marca de forma **marcante mas rápida**,
incluindo **áudio** (um sussurro), pra reforçar `clipia.com.br` como canal de aquisição.

## Visão geral da solução

No final de **todo** vídeo gerado, anexar um selo de marca de ~1.5s (**conceito "Freeze +
blur"**):

1. O último frame do vídeo **congela**, **desfoca** (`gblur`) e **escurece**.
2. Por cima, o **logo ClipIA** (film-frame + play + sparkle) + **"clipia.com.br"** surgem
   com **fade-in**.
3. Simultaneamente toca um **sussurro feminino "clipia.com.br"** (voz ElevenLabs,
   **pré-gravada uma vez** e congelada como asset — custo zero de API por vídeo).

A inserção é feita por **append em pós-processo**, **agnóstico ao motor** de render
(FFmpeg/NVENC na geração inicial, Remotion no export editado). Uma única implementação
cobre os dois caminhos.

### Decisões de produto (fechadas no brainstorming)

| Decisão | Escolha |
|---|---|
| Visual do card | **A — Freeze + blur** (congela o último frame do próprio conteúdo) |
| Voz do sussurro | Pré-gravo **2-3 takes** (ElevenLabs), usuário ouve e escolhe; vira asset fixo |
| Marca d'água de canto | **Mantida** (selo discreto durante o vídeo + outro no final) |
| Preview no editor | **Não** aparece no editor; só no export final (selo fixo, não-editável) |
| Liga/desliga | **Sempre ligado** via env flag (`OUTRO_ENABLED=True`); sem toggle por usuário (YAGNI) |
| Música de fundo no corte | **Fade-out** da música no início do sting |

## Arquitetura

### Princípio
Lógica isolada num módulo (`app/services/outro.py`) com **uma função pública**
(`append_outro`). Os call sites no worker só chamam essa função; toda a complexidade de
FFmpeg fica encapsulada. O sting é um **selo fixo de marca**, não um elemento editável —
por isso vive em pós-processo, fora do estado do editor.

### Componentes

#### 1. Asset de áudio pré-gravado — `app/assets/outro/whisper.wav`
- Texto **fixo** "clipia.com.br" → gerado **1x** e versionado no repo. Custo zero por vídeo.
- WAV mono, mesma família de formato do resto do pipeline (`pcm_s16le`), curto (~1.0–1.3s).

#### 2. Script gerador da voz — `scripts/generate_outro_whisper.py`
- Gera **2-3 takes** em `storage/outro_takes/take_{n}.wav` variando voz e settings
  (ex.: `stability` baixa + `style`/exaggeration alto pra ficar breathy/sussurrado;
  opcionalmente pós-processo FFmpeg leve — highpass + de-ess — se precisar reforçar o
  caráter de sussurro).
- Usa o `ElevenLabsProvider.synthesize()` existente (`app/services/elevenlabs_provider.py`).
- Modo **promote**: ao escolher o take vencedor, copia pra `app/assets/outro/whisper.wav`.
- Reexecutável quando quisermos trocar a voz no futuro.

#### 3. Asset visual do logo — `app/assets/outro/logo.png`
- PNG **transparente** do logo (mark + wordmark "ClipIA"), gerado a partir do SVG
  (`frontend/src/components/brand/Logo.tsx` / `frontend/public/logo.svg`).
- Gerado por script (one-off; ferramenta a definir no plano — ex. resvg/cairosvg ou
  screenshot headless). Dimensão alvo: ~520px de largura (nítido em 1080×1920).

#### 4. Builder do sting — `app/services/outro.py`
```
def append_outro(video_path: str) -> str
```
Fluxo:
1. **Guard / no-op**: se `not settings.OUTRO_ENABLED`, ou `whisper.wav`/`logo.png`
   ausentes → retorna `video_path` **intacto** (sem erro).
2. Extrai o **último frame** do vídeo (`ffmpeg -sseof -0.2 -i video -frames:v 1 last.png`).
3. Determina a duração: `dur = max(settings.OUTRO_DURATION, dur(whisper) + pad)`.
4. Monta o **clip do sting** (`outro.mp4`, mesmas dims/fps do vídeo, NVENC com fallback
   libx264 — reutilizar `_get_encoder_config()` do compositor):
   - `last.png` loop por `dur` → `gblur=sigma=…` + `eq=brightness=-0.30:saturation=0.9`;
   - overlay do `logo.png` centralizado + `drawtext` "clipia.com.br" abaixo;
   - **fade-in** do logo/URL (`fade=in` / alpha) nos primeiros ~0.3s;
   - áudio = `whisper.wav` (com `afade` curto nas pontas).
5. **Concatena** `[video_path][outro.mp4]` num `final_with_outro.mp4` via filter `concat`
   (re-encode pra garantir mesmos parâmetros de codec/áudio entre as duas partes).
6. Retorna o path do `final_with_outro.mp4`.

**Robustez:** qualquer exceção dentro de `append_outro` é capturada, **logada**, e a
função retorna `video_path` original — o sting **nunca derruba** a geração do vídeo.

#### 5. Configuração — `app/config.py`
```
OUTRO_ENABLED: bool = True
OUTRO_DURATION: float = 1.5      # segundos (piso; cresce se o whisper for maior)
OUTRO_BLUR_SIGMA: float = 16.0
OUTRO_DARKEN: float = 0.30       # brightness delta
OUTRO_AUDIO_PATH: Path = ASSETS_DIR / "outro" / "whisper.wav"
OUTRO_LOGO_PATH: Path  = ASSETS_DIR / "outro" / "logo.png"
```
(Segue o mesmo padrão das settings `WATERMARK_*`.)

### Integração no pipeline (2 chokepoints)

Os dois caminhos convergem no mesmo padrão `shutil.copy2(<render>, output/{job_id}.mp4)`:

- **Geração inicial** — `app/worker/tasks.py` → `task_finalize` (~linha 638):
  ```python
  final_src = append_outro(video_path)      # no-op-safe
  shutil.copy2(final_src, final_path)
  ```
- **Export do editor** — `app/worker/tasks.py` → `task_rerender_video` (~linha 781):
  ```python
  final_src = append_outro(output_path)     # cobre Remotion e FFmpeg fallback
  shutil.copy2(final_src, final_path)
  ```

Como `task_rerender_video` roda **depois** do Remotion **ou** do FFmpeg fallback, um único
ponto cobre ambos. O editor/preview não é tocado.

## Fluxo de dados

```
[geração] compose_short → job/final.mp4 ─┐
                                          ├─► append_outro() ─► final_with_outro.mp4 ─► output/{id}.mp4
[export]  Remotion|FFmpeg → job/final_* ─┘
                                          (whisper.wav + logo.png  →  outro.mp4)
```

## Tratamento de erros / bordas

- **Asset ausente / `OUTRO_ENABLED=false` / sem ElevenLabs key:** no-op silencioso (log
  em nível INFO), vídeo segue sem sting.
- **Falha no FFmpeg do sting:** capturada, log WARNING, retorna vídeo original.
- **Vídeo muito curto:** sem problema — o append sempre soma `dur` ao final.
- **Sem NVENC:** cai pra `libx264` (mesma lógica de `_get_encoder_config()`).
- **Whisper mais longo que `OUTRO_DURATION`:** duração do clip = `dur(whisper)+pad`.
- **Música de fundo:** já terminou no conteúdo; no sting toca só o whisper (com fade).

## Testes

- **Unit (`tests/test_outro.py`):**
  - no-op quando `OUTRO_ENABLED=false`;
  - no-op quando `whisper.wav`/`logo.png` ausentes (retorna o mesmo path);
  - com assets dummy: gera arquivo cuja duração ≈ `dur(original) + OUTRO_DURATION`
    (±tolerância) via `ffprobe`;
  - exceção interna → retorna path original (mock que força erro no subprocess).
- **Regressão:** `tests/test_regression_pipeline.py` continua verde (sem outro quando
  desabilitado nos fixtures).
- **Smoke real (manual):** gerar 1 vídeo curto com assets reais; conferir via `ffprobe`
  (+1.5s) e inspeção do último frame + áudio do sting.

## Fora de escopo (YAGNI)

- Toggle por usuário/plano no editor.
- Outro animado mais elaborado (partículas, motion graphics).
- Outro renderizado dentro do Remotion (preview do editor).
- Variações de outro por nicho/template.

## Arquivos afetados (resumo)

| Arquivo | Mudança |
|---|---|
| `app/services/outro.py` | **novo** — `append_outro()` + helpers FFmpeg |
| `scripts/generate_outro_whisper.py` | **novo** — gera/promove takes do sussurro |
| `app/assets/outro/whisper.wav` | **novo** — asset de áudio (gerado, versionado) |
| `app/assets/outro/logo.png` | **novo** — asset visual (gerado, versionado) |
| `app/config.py` | settings `OUTRO_*` + `ASSETS_DIR` se ainda não existir |
| `app/worker/tasks.py` | 2 chamadas a `append_outro` (finalize + rerender) |
| `tests/test_outro.py` | **novo** — testes unitários |
```
