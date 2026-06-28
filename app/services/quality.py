"""Quality gate pos-render — pega video mudo / majoritariamente preto / com duracao errada.

ponytail: inspeciona e devolve um QualityReport; quem chama grava `quality_warning` no job.
NAO faz retry cross-task (a causa de "mudo" e upstream — TTS — recompor nao corrige).
Falha dura de ffmpeg ja e tratada por _fail_job no pipeline. Inspecao e best-effort:
se ffprobe/ffmpeg nao rodar, retorna ok sem warning (nao bloqueia entrega).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SILENCE_DB = -50.0  # mean_volume <= isto = praticamente mudo
BLACK_FRACTION = 0.5  # >= metade do video preto = ruim
DURATION_TOLERANCE = 0.15  # +/-15% do alvo


@dataclass
class QualityReport:
    ok: bool
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0
    mean_volume: float | None = None
    black_fraction: float = 0.0


# ---------- parsers puros (testaveis offline) ----------


def _parse_mean_volume(stderr: str) -> float | None:
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    return float(m.group(1)) if m else None


def _parse_black_fraction(stderr: str, total_duration: float) -> float:
    if total_duration <= 0:
        return 0.0
    black = sum(float(d) for d in re.findall(r"black_duration:\s*(\d+(?:\.\d+)?)", stderr))
    return min(black / total_duration, 1.0)


def _parse_probe(probe_json: dict) -> tuple[bool, float]:
    """(tem stream de audio, duracao em segundos)."""
    streams = probe_json.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(probe_json.get("format", {}).get("duration", 0) or 0)
    return has_audio, duration


def evaluate(
    has_audio: bool,
    mean_volume: float | None,
    black_fraction: float,
    duration: float,
    target: float,
) -> QualityReport:
    warnings: list[str] = []
    if not has_audio or mean_volume is None or mean_volume <= SILENCE_DB:
        warnings.append("audio mudo ou ausente")
    if black_fraction >= BLACK_FRACTION:
        warnings.append(f"video majoritariamente preto ({black_fraction:.0%})")
    if target > 0 and abs(duration - target) / target > DURATION_TOLERANCE:
        warnings.append(f"duracao {duration:.0f}s fora do alvo {target:.0f}s")
    return QualityReport(
        ok=not warnings,
        warnings=warnings,
        duration=duration,
        mean_volume=mean_volume,
        black_fraction=black_fraction,
    )


# ---------- orquestracao (subprocess) ----------


def inspect_render(path: str, target_duration: float) -> QualityReport:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        has_audio, duration = _parse_probe(json.loads(probe.stdout or "{}"))

        # decodifica (sem encodar) coletando volume medio e trechos pretos
        det = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                path,
                "-af",
                "volumedetect",
                "-vf",
                "blackdetect=d=0.5:pic_th=0.98",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        mean_volume = _parse_mean_volume(det.stderr)
        black_fraction = _parse_black_fraction(det.stderr, duration)
        return evaluate(has_audio, mean_volume, black_fraction, duration, target_duration)
    except Exception as e:  # noqa: BLE001 — inspecao e best-effort, nunca bloqueia entrega
        logger.warning("quality gate nao rodou para %s: %s", path, e)
        return QualityReport(ok=True)
