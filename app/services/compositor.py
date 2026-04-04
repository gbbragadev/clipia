"""Video compositor using FFmpeg with NVENC GPU encoding."""

import json
import logging
import subprocess
from pathlib import Path

from app.config import settings
from app.services.subtitles import generate_ass_file

logger = logging.getLogger(__name__)


def _run(cmd: list[str], desc: str = "") -> subprocess.CompletedProcess:
    """Run FFmpeg command and log errors."""
    logger.info(f"FFmpeg [{desc}]: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"FFmpeg [{desc}] failed: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg {desc} failed: {result.stderr[-200:]}")
    return result


def _get_duration(path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _has_nvenc() -> bool:
    """Check if NVENC encoder is available."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True,
    )
    return "h264_nvenc" in result.stdout


def _prepare_scene(media_path: str, duration: float, output_path: str) -> str:
    """Prepare a single scene clip: resize to 1080x1920, loop if needed, set exact duration."""
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",  # loop input if shorter than duration
        "-i", media_path,
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"setsar=1"
        ),
        "-t", str(duration),
        "-an",  # no audio
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-r", str(settings.VIDEO_FPS),
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    _run(cmd, f"prepare scene")
    return output_path


def compose_short(
    scenes: list[dict],
    media_paths: list[str],
    audio_path: str,
    words: list[dict],
    output_path: str,
) -> str:
    """Compose final video using FFmpeg pipeline with NVENC encoding."""
    job_dir = Path(output_path).parent
    audio_duration = _get_duration(audio_path)

    # 1. Calculate proportional scene durations based on audio length
    total_hints = sum(s.get("duration_hint", 7) for s in scenes)
    scene_durations = []
    for s in scenes:
        ratio = s.get("duration_hint", 7) / total_hints
        scene_durations.append(round(ratio * audio_duration, 2))

    logger.info(f"Audio: {audio_duration:.1f}s, scenes: {scene_durations}")

    # 2. Prepare each scene clip (resize + duration)
    prepared = []
    for i, (scene, dur) in enumerate(zip(scenes, scene_durations)):
        if i >= len(media_paths):
            break
        clip_path = str(job_dir / f"clip_{i}.mp4")
        _prepare_scene(media_paths[i], dur, clip_path)
        prepared.append(clip_path)

    if not prepared:
        raise RuntimeError("No media clips prepared")

    # 3. Create concat file
    concat_file = str(job_dir / "concat.txt")
    with open(concat_file, "w") as f:
        for p in prepared:
            f.write(f"file '{p}'\n")

    # 4. Concatenate clips
    concat_output = str(job_dir / "concat.mp4")
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "copy",
        "-an",
        concat_output,
    ], "concat")

    # 5. Generate ASS subtitles
    ass_path = str(job_dir / "subtitles.ass")
    generate_ass_file(words, ass_path, total_duration=audio_duration)

    # 6. Final compose: video + subtitles + audio with NVENC
    use_nvenc = _has_nvenc()
    encoder = "h264_nvenc" if use_nvenc else "libx264"
    encoder_opts = (
        ["-preset", "p4", "-rc", "vbr", "-cq", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
        if use_nvenc
        else ["-preset", "veryfast", "-crf", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
    )

    logger.info(f"Encoding with {encoder}")

    _run([
        "ffmpeg", "-y",
        "-i", concat_output,
        "-i", audio_path,
        "-vf", f"ass={ass_path}",
        "-c:v", encoder, *encoder_opts,
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-r", str(settings.VIDEO_FPS),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ], "final encode")

    # Cleanup temp files
    for p in prepared:
        Path(p).unlink(missing_ok=True)
    Path(concat_file).unlink(missing_ok=True)
    Path(concat_output).unlink(missing_ok=True)

    final_duration = _get_duration(output_path)
    logger.info(f"Output: {output_path} ({final_duration:.1f}s)")
    return output_path
