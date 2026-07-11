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

    try:
        audio = Path(settings.OUTRO_AUDIO_PATH)
        logo = Path(settings.OUTRO_LOGO_PATH)
        if not audio.exists() or not logo.exists():
            logger.info("Outro pulado: asset ausente (audio=%s logo=%s)", audio.exists(), logo.exists())
            return video_path
        return _build_and_append(video_path, str(audio), str(logo))
    except Exception as e:  # o outro NUNCA derruba o job
        logger.warning("Outro falhou, mantendo video original: %s", e)
        return video_path


def _ffprobe(args: list[str]) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "quiet", *args], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()


def _probe_duration(path: str) -> float:
    return float(_ffprobe(["-show_entries", "format=duration", "-of", "csv=p=0", path]))


def _probe_dims(path: str) -> tuple[int, int, int]:
    out = _ffprobe(["-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path])
    s = json.loads(out)["streams"][0]
    try:
        num, den = (s["r_frame_rate"] + "/1").split("/")[:2]
        fps = int(round(float(num) / float(den))) if float(den) else settings.VIDEO_FPS
    except (ValueError, ZeroDivisionError):
        fps = settings.VIDEO_FPS
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
        f"[ov]drawtext=text='clipia.com.br':fontfile={font}:fontcolor=#f05340:borderw=2:bordercolor=black:"
        f"fontsize=52:x=(w-text_w)/2:y=h/2+90,fade=t=in:st=0:d=0.3,format=yuv420p[v];"
        f"[2:a]afade=t=in:st=0:d=0.08,afade=t=out:st={fade_out_st:.2f}:d=0.25[a]"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{dur}",
            "-i",
            frame_png,
            "-i",
            logo_path,
            "-i",
            audio_path,
            "-filter_complex",
            filt,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            enc,
            *enc_opts,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-r",
            f"{fps}",
            "-pix_fmt",
            "yuv420p",
            "-t",
            f"{dur}",
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
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            outro_mp4,
            "-filter_complex",
            concat,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            enc,
            *enc_opts,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            out_path,
        ],
        "concat-outro",
    )

    for tmp in (frame_png, outro_mp4):
        Path(tmp).unlink(missing_ok=True)
    return out_path
