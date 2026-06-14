# Outro Sting de Marca — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anexar a todo vídeo gerado um selo de marca de ~1.5s no final ("Freeze + blur": último frame congela/desfoca/escurece + logo ClipIA + "clipia.com.br") com um sussurro feminino pré-gravado tocando junto.

**Architecture:** Append em pós-processo, agnóstico ao motor de render. Um módulo `app/services/outro.py` com a função pública `append_outro(video_path)` encapsula todo o FFmpeg. Os dois chokepoints do worker (geração inicial e export do editor) passam a chamar um helper único `_copy_to_output` que aplica o outro antes de copiar pro diretório de saída. No-op-safe: desabilitado / asset ausente / qualquer erro → retorna o vídeo original. O sussurro e o logo são **assets fixos pré-gerados** (custo zero de API por vídeo).

**Tech Stack:** Python 3.12, FFmpeg 8.1 (NVENC com fallback libx264), ElevenLabs (`eleven_v3` `[whispers]`), Node + sharp (SVG→PNG), pytest.

**Branch:** `feat/outro-sting-marca` (criar no início da execução; ver superpowers:using-git-worktrees).

**Spec:** `docs/superpowers/specs/2026-06-14-outro-sting-marca-design.md`

**Voz travada (validada por WhatsApp 2026-06-14):** Fernanda PT-BR (`voice_id KHmfNHtEjHhLK9eER20w`), modelo `eleven_v3` tag `[whispers]`, texto "clipia.com.br", `atempo 1.60x` (~1.66s).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `app/config.py` (modify) | Settings `OUTRO_*` (enabled, duração, blur, darken, logo width, paths dos assets) |
| `app/services/outro.py` (create) | `append_outro()` + helpers FFmpeg (probe, extrair frame, montar clip, concatenar) |
| `frontend/scripts/render-outro-logo.mjs` (create) | Gera `app/assets/outro/logo.png` do SVG do logo via sharp |
| `scripts/generate_outro_whisper.py` (create) | Gera/promove `app/assets/outro/whisper.wav` (receita travada) |
| `app/assets/outro/logo.png` (create) | Asset visual (ícone do logo, transparente) |
| `app/assets/outro/whisper.wav` (create) | Asset de áudio (sussurro pré-gravado) |
| `app/worker/tasks.py` (modify) | Helper `_copy_to_output` + uso nos 2 chokepoints |
| `tests/test_outro.py` (create) | Testes unitários de `append_outro` |
| `tests/test_worker_output.py` (create) | Testes de `_copy_to_output` |
| `scripts/_outro_whisper_spike.py`, `scripts/_outro_whisper_fernanda.py` (delete) | Spikes temporários — remover |

---

## Task 1: Settings de configuração do outro

**Files:**
- Modify: `app/config.py:34-39` (bloco `# Video`, logo após `WATERMARK_TEXT`)
- Test: `tests/test_outro.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_outro.py` com:

```python
from app.config import settings


def test_outro_settings_defaults():
    assert settings.OUTRO_ENABLED is True
    assert settings.OUTRO_DURATION == 1.5
    assert settings.OUTRO_BLUR_SIGMA == 16.0
    assert settings.OUTRO_DARKEN == 0.30
    assert settings.OUTRO_LOGO_WIDTH == 520
    assert str(settings.OUTRO_AUDIO_PATH).replace("\\", "/").endswith("app/assets/outro/whisper.wav")
    assert str(settings.OUTRO_LOGO_PATH).replace("\\", "/").endswith("app/assets/outro/logo.png")
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_outro.py::test_outro_settings_defaults -v`
Expected: FAIL com `AttributeError: 'Settings' object has no attribute 'OUTRO_ENABLED'`

- [ ] **Step 3: Adicionar as settings**

Em `app/config.py`, logo após a linha `WATERMARK_TEXT: str = "clipia.com.br"` (linha 39), inserir:

```python

    # Outro sting de marca (selo de ~1.5s no final de cada video)
    OUTRO_ENABLED: bool = True
    OUTRO_DURATION: float = 1.5  # piso em segundos; cresce se o whisper for maior
    OUTRO_BLUR_SIGMA: float = 16.0
    OUTRO_DARKEN: float = 0.30  # delta de brightness aplicado ao frame congelado
    OUTRO_LOGO_WIDTH: int = 520  # largura do logo no selo (px)
    OUTRO_AUDIO_PATH: Path = BASE_DIR / "app" / "assets" / "outro" / "whisper.wav"
    OUTRO_LOGO_PATH: Path = BASE_DIR / "app" / "assets" / "outro" / "logo.png"
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_outro.py::test_outro_settings_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_outro.py
git commit -m "feat(outro): settings de configuracao do sting de marca"
```

---

## Task 2: Asset visual — logo.png via sharp

**Files:**
- Create: `frontend/scripts/render-outro-logo.mjs`
- Create (output): `app/assets/outro/logo.png`

- [ ] **Step 1: Criar o script de render**

Criar `frontend/scripts/render-outro-logo.mjs` (roda a partir de `frontend/`, onde o `sharp` está instalado):

```js
// Renderiza o icone do logo ClipIA (mark, sem texto -> sem dependencia de fonte)
// para app/assets/outro/logo.png usando sharp (ja instalado no frontend).
import sharp from 'sharp'
import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(here, '../../app/assets/outro/logo.png')

const SVG = `<svg width="360" height="360" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8b5cf6"/><stop offset="50%" stop-color="#7c3aed"/><stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="s" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#c4b5fd"/><stop offset="100%" stop-color="#93c5fd"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="34" height="34" rx="8" fill="url(#g)"/>
  <rect x="6" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="6" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="6" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="9" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="18" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <rect x="31" y="27" width="3" height="4" rx="1" fill="#0a0a12" opacity="0.4"/>
  <polygon points="16,12 16,28 28,20" fill="white" opacity="0.95"/>
  <circle cx="32" cy="8" r="3" fill="url(#s)" opacity="0.9"/>
  <line x1="32" y1="4" x2="32" y2="12" stroke="white" stroke-width="1" opacity="0.6"/>
  <line x1="28" y1="8" x2="36" y2="8" stroke="white" stroke-width="1" opacity="0.6"/>
</svg>`

await mkdir(dirname(OUT), { recursive: true })
await sharp(Buffer.from(SVG)).png().toFile(OUT)
console.log('logo ->', OUT)
```

- [ ] **Step 2: Rodar o script**

Run: `cd frontend; node scripts/render-outro-logo.mjs; cd ..`
Expected: imprime `logo -> ...app/assets/outro/logo.png`

- [ ] **Step 3: Verificar o PNG gerado**

Run:
```bash
.\.venv312\Scripts\python.exe -c "from PIL import Image; im=Image.open('app/assets/outro/logo.png'); print(im.size, im.mode)"
```
Expected: `(360, 360) RGBA`

- [ ] **Step 4: Garantir que o asset não está gitignored e commitar**

Run: `git check-ignore app/assets/outro/logo.png; echo "exit=$?"`
Expected: `exit=1` (não ignorado). Se for ignorado (`exit=0`), ajustar `.gitignore`.

```bash
git add frontend/scripts/render-outro-logo.mjs app/assets/outro/logo.png
git commit -m "feat(outro): asset visual do logo (sharp SVG->PNG)"
```

---

## Task 3: Asset de áudio — whisper.wav (receita travada)

**Files:**
- Create: `scripts/generate_outro_whisper.py`
- Create (output): `app/assets/outro/whisper.wav`
- Delete: `scripts/_outro_whisper_spike.py`, `scripts/_outro_whisper_fernanda.py`

- [ ] **Step 1: Criar o script gerador final**

Criar `scripts/generate_outro_whisper.py`:

```python
"""Gera o asset de audio do outro (sussurro 'clipia.com.br') e, com --promote,
copia para app/assets/outro/whisper.wav.

Receita travada (validada por WhatsApp 2026-06-14): voz Fernanda (PT-BR),
modelo eleven_v3 com tag [whispers], texto 'clipia.com.br', atempo 1.60x, WAV mono.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from elevenlabs import ElevenLabs

BASE_DIR = Path(__file__).resolve().parent.parent
TAKES_DIR = BASE_DIR / "storage" / "outro_takes"
ASSET_PATH = BASE_DIR / "app" / "assets" / "outro" / "whisper.wav"

VOICE_ID = "KHmfNHtEjHhLK9eER20w"  # Fernanda - PT-BR
MODEL = "eleven_v3"
TEXT = "clipia.com.br"
TEMPO = 1.60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=VOICE_ID)
    ap.add_argument("--tempo", type=float, default=TEMPO)
    ap.add_argument("--text", default=TEXT)
    ap.add_argument("--promote", action="store_true", help="copia o resultado p/ o asset oficial")
    args = ap.parse_args()

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        print("ELEVENLABS_API_KEY ausente", file=sys.stderr)
        return 1

    TAKES_DIR.mkdir(parents=True, exist_ok=True)
    raw_mp3 = TAKES_DIR / "outro_raw.mp3"
    final_wav = TAKES_DIR / "outro_final.wav"

    client = ElevenLabs(api_key=key)
    audio = client.text_to_speech.convert(
        voice_id=args.voice,
        text=f"[whispers] {args.text}",
        model_id=MODEL,
        output_format="mp3_44100_128",
    )
    with open(raw_mp3, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    print(f"TTS gerado: {raw_mp3}")

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_mp3),
         "-filter:a", f"atempo={args.tempo}",
         "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(final_wav)],
        check=True, capture_output=True,
    )
    dur = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(final_wav)],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"WAV final: {final_wav} ({dur}s)")

    if args.promote:
        ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_wav, ASSET_PATH)
        print(f"Promovido p/ asset oficial: {ASSET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Gerar e promover o asset** (requer `ELEVENLABS_API_KEY` no ambiente)

Run: `.\.venv312\Scripts\python.exe scripts/generate_outro_whisper.py --promote`
Expected: imprime `TTS gerado`, `WAV final: ... (~1.6s)` e `Promovido p/ asset oficial: ...whisper.wav`

- [ ] **Step 3: Verificar o WAV**

Run:
```bash
ffprobe -v quiet -show_entries format=duration:stream=channels,sample_rate -of default=nw=1 app/assets/outro/whisper.wav
```
Expected: `duration` ~1.5–1.8s, `channels=1`, `sample_rate=44100`

- [ ] **Step 4: Remover os spikes temporários**

```bash
git rm -f --ignore-unmatch scripts/_outro_whisper_spike.py scripts/_outro_whisper_fernanda.py
```
(Se não estiverem trackeados, remover do disco: `rm -f scripts/_outro_whisper_spike.py scripts/_outro_whisper_fernanda.py`.)

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_outro_whisper.py app/assets/outro/whisper.wav
git commit -m "feat(outro): asset de audio do sussurro (Fernanda eleven_v3, 1.60x)"
```

---

## Task 4: Serviço `append_outro` (núcleo)

**Files:**
- Create: `app/services/outro.py`
- Test: `tests/test_outro.py`

- [ ] **Step 1: Escrever os testes de no-op (que falham)**

Adicionar a `tests/test_outro.py`:

```python
import shutil
import subprocess

import pytest

from app.config import settings
from app.services import outro


def test_append_outro_noop_when_disabled(tmp_path, monkeypatch):
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x")
    monkeypatch.setattr(settings, "OUTRO_ENABLED", False)
    assert outro.append_outro(str(v)) == str(v)


def test_append_outro_noop_when_assets_missing(tmp_path, monkeypatch):
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x")
    monkeypatch.setattr(settings, "OUTRO_ENABLED", True)
    monkeypatch.setattr(settings, "OUTRO_AUDIO_PATH", tmp_path / "missing.wav")
    monkeypatch.setattr(settings, "OUTRO_LOGO_PATH", tmp_path / "missing.png")
    assert outro.append_outro(str(v)) == str(v)


def test_append_outro_returns_original_on_error(tmp_path, monkeypatch):
    v = tmp_path / "v.mp4"
    v.write_bytes(b"not a real video")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"a")
    logo = tmp_path / "l.png"
    logo.write_bytes(b"l")
    monkeypatch.setattr(settings, "OUTRO_ENABLED", True)
    monkeypatch.setattr(settings, "OUTRO_AUDIO_PATH", audio)
    monkeypatch.setattr(settings, "OUTRO_LOGO_PATH", logo)
    # assets existem mas o "video" é inválido → _build_and_append lança → no-op
    assert outro.append_outro(str(v)) == str(v)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_outro.py -k "noop or error" -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.outro'`

- [ ] **Step 3: Implementar `app/services/outro.py`**

```python
"""Outro sting de marca: anexa um selo de ~1.5s no final de cada video.

Conceito 'Freeze + blur': congela o ultimo frame, desfoca/escurece, sobrepoe o
logo + 'clipia.com.br', e toca o sussurro pre-gravado (Fernanda PT-BR).

Append em pos-processo, agnostico ao motor (FFmpeg/Remotion). No-op-safe: se
desabilitado, assets ausentes ou qualquer erro, retorna o video original intacto.
"""

import json
import logging
import subprocess
from pathlib import Path

from app.config import settings
from app.services.compositor import _get_drawtext_font, _get_encoder_config

logger = logging.getLogger(__name__)


def append_outro(video_path: str) -> str:
    """Anexa o sting de marca ao final do video. Retorna o path do novo arquivo
    final, ou o `video_path` original se desabilitado / asset ausente / erro."""
    if not settings.OUTRO_ENABLED:
        return video_path

    audio = Path(settings.OUTRO_AUDIO_PATH)
    logo = Path(settings.OUTRO_LOGO_PATH)
    if not audio.exists() or not logo.exists():
        logger.info("Outro pulado: asset ausente (audio=%s logo=%s)", audio.exists(), logo.exists())
        return video_path

    try:
        return _build_and_append(video_path, str(audio), str(logo))
    except Exception as e:  # o outro NUNCA derruba o job
        logger.warning("Outro falhou, mantendo video original: %s", e)
        return video_path


def _ffprobe(args: list[str]) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "quiet", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _probe_duration(path: str) -> float:
    return float(_ffprobe(["-show_entries", "format=duration", "-of", "csv=p=0", path]))


def _probe_dims(path: str) -> tuple[int, int, int]:
    out = _ffprobe(
        ["-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path]
    )
    s = json.loads(out)["streams"][0]
    num, den = (s["r_frame_rate"] + "/1").split("/")[:2]
    fps = int(round(float(num) / float(den))) if float(den) else settings.VIDEO_FPS
    return int(s["width"]), int(s["height"]), fps or settings.VIDEO_FPS


def _run(cmd: list[str], desc: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg {desc} falhou: {r.stderr[-400:]}")


def _build_and_append(video_path: str, audio_path: str, logo_path: str) -> str:
    job_dir = Path(video_path).parent
    w, h, fps = _probe_dims(video_path)
    dur = round(max(settings.OUTRO_DURATION, _probe_duration(audio_path) + 0.25), 2)

    enc, enc_opts = _get_encoder_config()
    font = _get_drawtext_font()
    blur = settings.OUTRO_BLUR_SIGMA
    darken = settings.OUTRO_DARKEN
    logo_w = settings.OUTRO_LOGO_WIDTH
    fade_out_st = max(0.0, dur - 0.25)

    # 1) extrai o ultimo frame
    frame_png = str(job_dir / "_outro_last.png")
    _run(
        ["ffmpeg", "-y", "-sseof", "-0.2", "-i", video_path, "-frames:v", "1", "-q:v", "2", frame_png],
        "last-frame",
    )

    # 2) monta o clip do sting (frame borrado/escurecido + logo + URL + sussurro)
    outro_mp4 = str(job_dir / "_outro_clip.mp4")
    filt = (
        f"[0:v]scale={w}:{h},setsar=1,gblur=sigma={blur},"
        f"eq=brightness=-{darken}:saturation=0.92[bg];"
        f"[1:v]scale={logo_w}:-1[logo];"
        f"[bg][logo]overlay=(W-w)/2:(H-h)/2-70[ov];"
        f"[ov]drawtext=text='clipia.com.br':fontfile={font}:fontcolor=white:"
        f"fontsize=52:x=(w-text_w)/2:y=h/2+90,fade=t=in:st=0:d=0.3,format=yuv420p[v];"
        f"[2:a]afade=t=in:st=0:d=0.08,afade=t=out:st={fade_out_st:.2f}:d=0.25[a]"
    )
    _run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{dur}", "-i", frame_png,
            "-i", logo_path,
            "-i", audio_path,
            "-filter_complex", filt,
            "-map", "[v]", "-map", "[a]",
            "-c:v", enc, *enc_opts,
            "-c:a", "aac", "-b:a", "128k",
            "-r", f"{fps}", "-pix_fmt", "yuv420p", "-t", f"{dur}",
            outro_mp4,
        ],
        "build-outro",
    )

    # 3) concatena [principal][outro] normalizando dimensoes/fps/audio
    out_path = str(job_dir / "final_with_outro.mp4")
    concat = (
        f"[0:v]scale={w}:{h},fps={fps},setsar=1,format=yuv420p[v0];"
        f"[1:v]scale={w}:{h},fps={fps},setsar=1,format=yuv420p[v1];"
        f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
        f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    _run(
        [
            "ffmpeg", "-y",
            "-i", video_path, "-i", outro_mp4,
            "-filter_complex", concat,
            "-map", "[v]", "-map", "[a]",
            "-c:v", enc, *enc_opts,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ],
        "concat-outro",
    )

    for tmp in (frame_png, outro_mp4):
        Path(tmp).unlink(missing_ok=True)
    return out_path
```

- [ ] **Step 4: Rodar os testes de no-op e ver passar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_outro.py -k "noop or error" -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Escrever o teste de integração FFmpeg (duração aumenta)**

Adicionar a `tests/test_outro.py`:

```python
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg necessario")
def test_append_outro_adds_duration(tmp_path, monkeypatch):
    video = tmp_path / "content.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=navy:s=540x960:r=30:d=1",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)],
        check=True, capture_output=True,
    )
    whisper = tmp_path / "whisper.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-ac", "1", str(whisper)],
        check=True, capture_output=True,
    )
    logo = tmp_path / "logo.png"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=white:s=200x80", "-frames:v", "1", str(logo)],
        check=True, capture_output=True,
    )
    monkeypatch.setattr(settings, "OUTRO_ENABLED", True)
    monkeypatch.setattr(settings, "OUTRO_AUDIO_PATH", whisper)
    monkeypatch.setattr(settings, "OUTRO_LOGO_PATH", logo)
    monkeypatch.setattr(settings, "OUTRO_DURATION", 1.5)

    out = outro.append_outro(str(video))
    assert out != str(video)
    dur = float(
        subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", out],
            capture_output=True, text=True,
        ).stdout.strip()
    )
    assert 2.2 <= dur <= 2.9  # ~1.0 (conteudo) + 1.5 (outro), com tolerancia de encode
```

- [ ] **Step 6: Rodar o teste de integração e ver passar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_outro.py::test_append_outro_adds_duration -v`
Expected: PASS (gera ~2.5s)

- [ ] **Step 7: Commit**

```bash
git add app/services/outro.py tests/test_outro.py
git commit -m "feat(outro): servico append_outro (freeze+blur+logo+sussurro)"
```

---

## Task 5: Integração no worker (2 chokepoints)

**Files:**
- Modify: `app/worker/tasks.py` (imports; `task_finalize` ~637-639; `task_rerender_video` ~779-782)
- Test: `tests/test_worker_output.py`

- [ ] **Step 1: Escrever os testes do helper (que falham)**

Criar `tests/test_worker_output.py`:

```python
from app.worker import tasks


def test_copy_to_output_noop_append_copies_source(tmp_path, monkeypatch):
    src = tmp_path / "render.mp4"
    src.write_bytes(b"VIDEO")
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(tasks, "append_outro", lambda p: p)  # no-op
    monkeypatch.setattr(tasks, "get_output_dir", lambda: out)

    final = tasks._copy_to_output(str(src), "job123")

    assert final == str(out / "job123.mp4")
    assert (out / "job123.mp4").read_bytes() == b"VIDEO"


def test_copy_to_output_copies_append_result(tmp_path, monkeypatch):
    src = tmp_path / "render.mp4"
    src.write_bytes(b"RAW")
    stung = tmp_path / "with_outro.mp4"
    stung.write_bytes(b"STUNG")
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(tasks, "append_outro", lambda p: str(stung))
    monkeypatch.setattr(tasks, "get_output_dir", lambda: out)

    tasks._copy_to_output(str(src), "j")

    assert (out / "j.mp4").read_bytes() == b"STUNG"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_worker_output.py -v`
Expected: FAIL com `AttributeError: module 'app.worker.tasks' has no attribute '_copy_to_output'`

- [ ] **Step 3: Adicionar o import de `append_outro`**

Em `app/worker/tasks.py`, junto aos outros imports `from app.services...` (topo do arquivo), adicionar:

```python
from app.services.outro import append_outro
```

- [ ] **Step 4: Adicionar o helper `_copy_to_output`**

Em `app/worker/tasks.py`, adicionar (perto das outras helpers de módulo, ex. logo antes de `task_compose_video`):

```python
def _copy_to_output(src_path: str, job_id: str) -> str:
    """Aplica o outro sting (no-op-safe) e copia o resultado para o diretorio de
    saida `output/{job_id}.mp4`. Retorna o path final."""
    final_src = append_outro(src_path)
    final_path = str(get_output_dir() / f"{job_id}.mp4")
    shutil.copy2(final_src, final_path)
    return final_path
```

- [ ] **Step 5: Usar o helper em `task_finalize`**

Em `app/worker/tasks.py`, no `task_finalize`, substituir:

```python
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        shutil.copy2(video_path, final_path)
```

por:

```python
        final_path = _copy_to_output(video_path, job_id)
```

- [ ] **Step 6: Usar o helper em `task_rerender_video`**

Em `app/worker/tasks.py`, no `task_rerender_video`, substituir:

```python
        # Copy to output dir (becomes downloadable version)
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        shutil.copy2(output_path, final_path)
```

por:

```python
        # Copy to output dir (becomes downloadable version) — aplica o outro sting
        final_path = _copy_to_output(output_path, job_id)
```

- [ ] **Step 7: Rodar os testes do helper e ver passar**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_worker_output.py -v`
Expected: PASS (2 testes)

- [ ] **Step 8: Garantir que a regressão do pipeline continua verde**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_regression_pipeline.py -v`
Expected: PASS (sem regressões)

- [ ] **Step 9: Commit**

```bash
git add app/worker/tasks.py tests/test_worker_output.py
git commit -m "feat(outro): integra append_outro nos 2 chokepoints do worker"
```

---

## Task 6: Smoke test real, doc e fechamento

**Files:**
- Modify: `CLAUDE.md` (seção Gotchas)

- [ ] **Step 1: Smoke test real do sting** (assets reais já promovidos nas tasks 2-3)

Gerar um clipe de teste e aplicar o outro de ponta a ponta:

```bash
ffmpeg -y -f lavfi -i "color=c=teal:s=1080x1920:r=30:d=2" -f lavfi -i "sine=frequency=220:duration=2" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest storage/_smoke_content.mp4
.\.venv312\Scripts\python.exe -c "from app.services.outro import append_outro; print(append_outro('storage/_smoke_content.mp4'))"
ffprobe -v quiet -show_entries format=duration -of csv=p=0 storage/final_with_outro.mp4
```
Expected: duração ~3.6s (2.0 conteúdo + ~1.66 outro). Abrir `storage/final_with_outro.mp4` e conferir visual (logo + URL no fim) + áudio (sussurro). Limpar: `rm -f storage/_smoke_content.mp4 storage/final_with_outro.mp4`.

- [ ] **Step 2: Documentar o gotcha no CLAUDE.md**

Em `CLAUDE.md`, na seção `## Gotchas importantes`, adicionar um bullet:

```markdown
- **Outro sting de marca (pos-processo)**: `app/services/outro.py` → `append_outro()` anexa um selo de ~1.5s (freeze+blur do ultimo frame + logo + sussurro "clipia.com.br") no final de TODO video. Roda nos 2 chokepoints via `_copy_to_output` (geracao inicial e export do editor), nao no editor. No-op-safe (flag `OUTRO_ENABLED`, assets em `app/assets/outro/`). Regenerar a voz: `python scripts/generate_outro_whisper.py --promote` (Fernanda PT-BR, eleven_v3 [whispers], atempo 1.60x).
```

- [ ] **Step 3: Rodar a suíte completa**

Run: `.\.venv312\Scripts\python.exe -m pytest -q`
Expected: tudo verde (incluindo `tests/test_outro.py` e `tests/test_worker_output.py`)

- [ ] **Step 4: Commit final**

```bash
git add CLAUDE.md
git commit -m "docs(outro): registra gotcha do sting no CLAUDE.md"
```

---

## Notas de execução

- **NVENC**: na máquina do Gui (GTX 1660) o encode do outro usa `h264_nvenc`; em ambiente sem NVENC cai para `libx264` automaticamente (via `_get_encoder_config()`).
- **Reuso DRY**: `append_outro` reaproveita `_get_drawtext_font()` e `_get_encoder_config()` do `compositor.py` — não duplicar lógica de fonte/encoder.
- **`storage/outro_takes/`** fica sob `storage/` (gitignored); só `app/assets/outro/{whisper.wav,logo.png}` são versionados.
- **Selo de canto**: `WATERMARK_ENABLED` continua `True` (decisão: manter os dois). Nenhuma mudança necessária.
