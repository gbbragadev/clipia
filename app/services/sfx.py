"""Efeitos sonoros (SFX) via ElevenLabs — whoosh nas transições de cena.

ponytail: SFX entra como PRÉ-PROCESSAMENTO do áudio de narração (mix antes da composição),
sem tocar nos filter_complex de vídeo do compositor. O whoosh é gerado UMA vez e cacheado em
storage/sfx/. Sem ELEVENLABS_API_KEY ou sem transições -> no-op gracioso (devolve o áudio original).
"""

import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_SFX_DIR = settings.STORAGE_DIR / "sfx"
WHOOSH_PROMPT = "short clean whoosh transition swoosh, no music"


def _scaled_transitions(scene_durations: list[float], real_duration: float) -> list[float]:
    """Tempos (s) de início de cada cena exceto a primeira, escalados do script p/ a duração real."""
    durs = [float(d) for d in scene_durations if d]
    if len(durs) < 2:
        return []
    total = sum(durs)
    factor = (real_duration / total) if (real_duration and total) else 1.0
    acc, out = 0.0, []
    for d in durs[:-1]:
        acc += d
        out.append(round(acc * factor, 2))
    return out


def _probe_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        import json

        return float(json.loads(r.stdout or "{}").get("format", {}).get("duration", 0) or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def get_whoosh() -> Path | None:
    """Gera (e cacheia para sempre) o whoosh de transição. None se ElevenLabs indisponível."""
    _SFX_DIR.mkdir(parents=True, exist_ok=True)
    dest = _SFX_DIR / "whoosh.mp3"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    if not settings.ELEVENLABS_API_KEY:
        return None
    try:
        from app.services.elevenlabs_provider import _get_client

        client = _get_client()
        audio = client.text_to_sound_effects.convert(
            text=WHOOSH_PROMPT,
            duration_seconds=1.0,
            prompt_influence=0.4,
        )
        with open(dest, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        return dest if dest.stat().st_size > 1000 else None
    except Exception as e:  # noqa: BLE001 — SFX é enriquecimento, não pode quebrar a geração
        logger.warning("SFX whoosh falhou: %s", e)
        return None


def mix_transitions(audio_path: str, scene_durations: list[float], output_path: str, volume: float = 0.35) -> str:
    """Mixa um whoosh nas transições de cena. No-op (devolve audio_path) se sem whoosh/transições."""
    whoosh = get_whoosh()
    times = _scaled_transitions(scene_durations, _probe_duration(audio_path))
    if whoosh is None or not times:
        return audio_path

    n = len(times)
    parts = ["[1:a]asplit=" + str(n) + "".join(f"[w{i}]" for i in range(n))]
    for i, t in enumerate(times):
        ms = int(t * 1000)
        parts.append(f"[w{i}]adelay={ms}|{ms},volume={volume}[d{i}]")
    mix_in = "[0:a]" + "".join(f"[d{i}]" for i in range(n))
    parts.append(f"{mix_in}amix=inputs={n + 1}:duration=first:normalize=0[aout]")
    filter_complex = ";".join(parts)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                audio_path,
                "-i",
                str(whoosh),
                "-filter_complex",
                filter_complex,
                "-map",
                "[aout]",
                "-c:a",
                "pcm_s16le",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        logger.info("SFX: %d whooshes mixados em %s", n, output_path)
        return output_path
    except Exception as e:  # noqa: BLE001 — falhou? segue com a narração original
        logger.warning("SFX mix falhou, usando narração original: %s", e)
        return audio_path
