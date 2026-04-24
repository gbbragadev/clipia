"""Video compositor using FFmpeg with NVENC GPU encoding."""

import json
import logging
import subprocess
from pathlib import Path

from app.config import settings
from app.services.subtitles import generate_ass_file
from app.templates import LayoutConfig

logger = logging.getLogger(__name__)


def _get_drawtext_font() -> str:
    global _FONT_FOR_DRAWTEXT
    if not _FONT_FOR_DRAWTEXT:
        _FONT_FOR_DRAWTEXT = _init_drawtext_font()
    return _FONT_FOR_DRAWTEXT


_FONT_FOR_DRAWTEXT: str = ""  # lazy-populated at first use


def _ff_escape_path(path: str) -> str:
    """Escape a filesystem path for use inside an FFmpeg filtergraph.

    FFmpeg filter graph does **two** parse passes: first splitting on `:` and
    `,`, then parsing option args. A single `\\:` survives the first pass but
    is re-interpreted in the second, so the drive letter `C:` still looks
    like a `key:value` split. `\\\\:` survives both passes as a literal `:`.
    Also converts `\\` to `/` because bare backslashes are escape chars inside
    filter syntax.

    Example: `C:\\foo.ass` becomes `C\\\\:/foo.ass` (in raw string terms,
    `C\\:/foo.ass` on the command line).
    """
    return path.replace("\\", "/").replace(":", r"\\:")


def _init_drawtext_font() -> str:
    """Pick a usable font for ``drawtext`` filters.

    Prefer the repo's bundled Montserrat-Bold (Phase A brings it from
    ``settings.FONT_PATH``). ``drawtext`` needs the path inside a filter
    graph, so it must go through :func:`_ff_escape_path` too.
    """
    return _ff_escape_path(str(settings.FONT_PATH))


def _ass_filter(ass_path: str) -> str:
    """Build an ``ass=`` filter string with fontsdir so libass finds fonts on
    Windows without a Fontconfig default config (which FFmpeg Windows builds
    lack). Uses ``settings.FONT_PATH.parent`` — the repo ``fonts/`` dir.
    """
    fonts_dir = str(settings.FONT_PATH.parent)
    return f"ass={_ff_escape_path(ass_path)}:fontsdir={_ff_escape_path(fonts_dir)}"


def _run(cmd: list[str], desc: str = "") -> subprocess.CompletedProcess:
    """Run FFmpeg command and log errors."""
    logger.info(f"FFmpeg [{desc}]: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"FFmpeg [{desc}] FULL CMD: {cmd}")
        logger.error(f"FFmpeg [{desc}] FULL STDERR: {result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg {desc} failed: {result.stderr[-500:]}")
    return result


def _get_duration(path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _has_nvenc() -> bool:
    """Check if NVENC encoder is available."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return "h264_nvenc" in result.stdout


def _prepare_video_scene(media_path: str, duration: float, output_path: str) -> str:
    """Prepare a single scene clip: resize to 1080x1920, loop if needed, set exact duration."""
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",  # loop input if shorter than duration
        "-i",
        media_path,
        "-vf",
        ("scale=1080:1920:force_original_aspect_ratio=increase," "crop=1080:1920," "setsar=1"),
        "-t",
        str(duration),
        "-an",  # no audio
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-r",
        str(settings.VIDEO_FPS),
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]
    _run(cmd, "prepare scene")
    return output_path


def _prepare_scene(media_path: str, duration: float, output_clip: str, scene_index: int = 0) -> None:
    """Route to video or static-image preparation. Full router in Task 15."""
    _prepare_video_scene(media_path, duration, output_clip)


def _watermark_filter() -> str:
    """Return a drawtext filter for the ClipIA watermark, or empty string if disabled."""
    if not settings.WATERMARK_ENABLED:
        return ""
    text = settings.WATERMARK_TEXT.replace("'", "'\\''")
    font = _get_drawtext_font()
    return f"drawtext=text='{text}':fontfile={font}" f":fontsize=22:fontcolor=white@0.5:x=w-text_w-30:y=h-50"


def _build_overlay_filters(overlays: list[dict], fps: int = 30) -> str:
    """Build FFmpeg drawtext filters for overlay elements (EndScreen, FollowCTA, QuestionBox)."""
    filters = []
    for ov in overlays:
        ov_type = ov.get("type", "")
        start_sec = ov.get("startFrame", 0) / fps
        end_sec = ov.get("endFrame", 0) / fps
        config = ov.get("config", {})
        enable = f"between(t,{start_sec:.2f},{end_sec:.2f})"

        if ov_type == "endScreen":
            username = config.get("username", "@clipia").replace("'", "'\\''")
            text = config.get("text", "Gostou? Siga para mais!").replace("'", "'\\''")
            # Dark overlay background
            filters.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.85:t=fill:enable='{enable}'")
            # Username
            filters.append(
                f"drawtext=text='{username}':fontfile={_get_drawtext_font()}"
                f":fontsize=28:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-40"
                f":enable='{enable}'"
            )
            # CTA text
            filters.append(
                f"drawtext=text='{text}':fontfile={_get_drawtext_font()}"
                f":fontsize=36:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2+20"
                f":enable='{enable}'"
            )
            # SEGUIR button (red box + text)
            filters.append(f"drawbox=x=(iw-240)/2:y=ih/2+80:w=240:h=50:color=0xFE2C55@1:t=fill:enable='{enable}'")
            filters.append(
                f"drawtext=text='SEGUIR':fontfile={_get_drawtext_font()}"
                f":fontsize=22:fontcolor=white:x=(w-text_w)/2:y=h/2+90"
                f":enable='{enable}'"
            )

        elif ov_type == "followCTA":
            text = config.get("text", "SIGA PARA MAIS").replace("'", "'\\''")
            # Red pill button at bottom
            filters.append(f"drawbox=x=(iw-300)/2:y=ih*0.78:w=300:h=52:color=0xFE2C55@1:t=fill:enable='{enable}'")
            filters.append(
                f"drawtext=text='{text}':fontfile={_get_drawtext_font()}"
                f":fontsize=24:fontcolor=white:x=(w-text_w)/2:y=h*0.78+12"
                f":enable='{enable}'"
            )

        elif ov_type == "questionBox":
            label = config.get("label", "VOCE SABIA?").replace("'", "'\\''")
            text = config.get("text", "").replace("'", "'\\''")
            # Dark box background at top
            filters.append(f"drawbox=x=iw*0.06:y=ih*0.18:w=iw*0.88:h=140:color=black@0.75:t=fill:enable='{enable}'")
            # Label (yellow)
            filters.append(
                f"drawtext=text='{label}':fontfile={_get_drawtext_font()}"
                f":fontsize=24:fontcolor=0xFFCC00:x=iw*0.08:y=ih*0.19+10"
                f":enable='{enable}'"
            )
            if text:
                filters.append(
                    f"drawtext=text='{text}':fontfile={_get_drawtext_font()}"
                    f":fontsize=32:fontcolor=white:x=iw*0.08:y=ih*0.19+50"
                    f":enable='{enable}'"
                )

    return ",".join(filters)


def _get_encoder_config() -> tuple[str, list[str]]:
    """Return (encoder_name, encoder_opts) based on NVENC availability."""
    use_nvenc = _has_nvenc()
    encoder = "h264_nvenc" if use_nvenc else "libx264"
    opts = (
        ["-preset", "p4", "-rc", "vbr", "-cq", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
        if use_nvenc
        else ["-preset", "veryfast", "-crf", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
    )
    return encoder, opts


def _prepare_looped_background(media_path: str, duration: float, width: int, height: int, output_path: str) -> str:
    """Prepare a single clip looped to exact duration, resized to target dimensions."""
    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        media_path,
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1",
        "-t",
        str(duration),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-r",
        str(settings.VIDEO_FPS),
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]
    _run(cmd, "prepare looped background")
    return output_path


def _compose_split_screen(
    bg_path: str,
    audio_path: str,
    ass_path: str,
    split_ratio: float,
    output_path: str,
    music_path: str | None = None,
    music_volume: float = 0.15,
) -> str:
    """Compose split-screen: dark top region with subtitles + gameplay bottom."""
    top_h = int(settings.VIDEO_HEIGHT * split_ratio)
    bot_h = settings.VIDEO_HEIGHT - top_h
    w = settings.VIDEO_WIDTH

    encoder, encoder_opts = _get_encoder_config()

    # Filter: crop gameplay to bottom region, add dark top, overlay ASS on top
    wm = _watermark_filter()
    wm_part = f",{wm}" if wm else ""
    filter_complex = (
        f"[0:v]scale={w}:{bot_h}:force_original_aspect_ratio=increase,crop={w}:{bot_h},setsar=1[bg];"
        f"color=c=#0D0D0D:s={w}x{top_h}:d=9999:r={settings.VIDEO_FPS}[top];"
        f"[top][bg]vstack=inputs=2[stacked];"
        f"[stacked]{_ass_filter(ass_path)}{wm_part}[vout]"
    )

    inputs = ["-i", bg_path, "-i", audio_path]
    maps_and_audio = ["-map", "[vout]"]

    if music_path and Path(music_path).exists():
        inputs += ["-stream_loop", "-1", "-i", music_path]
        filter_complex += (
            f";[1:a]volume=1.0[narr];[2:a]volume={music_volume}[mus];[narr][mus]amix=inputs=2:duration=first[aout]"
        )
        maps_and_audio += ["-map", "[aout]"]
    else:
        maps_and_audio += ["-map", "1:a"]

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        *maps_and_audio,
        "-c:v",
        encoder,
        *encoder_opts,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-r",
        str(settings.VIDEO_FPS),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd, "split-screen compose")
    return output_path


def _compose_character_overlay(
    bg_path: str,
    character_path: str,
    audio_path: str,
    ass_path: str,
    output_path: str,
    music_path: str | None = None,
    music_volume: float = 0.15,
) -> str:
    """Compose video with character image overlaid on background + subtitles."""
    w = settings.VIDEO_WIDTH
    h = settings.VIDEO_HEIGHT
    char_w = 350
    char_x = 40
    char_y = h - char_w - 250

    encoder, encoder_opts = _get_encoder_config()

    wm = _watermark_filter()
    wm_part = f",{wm}" if wm else ""
    filter_complex = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[bg];"
        f"[1:v]scale={char_w}:-1[char];"
        f"[bg][char]overlay={char_x}:{char_y}[with_char];"
        f"[with_char]{_ass_filter(ass_path)}{wm_part}[vout]"
    )

    inputs = ["-stream_loop", "-1", "-i", bg_path, "-i", character_path, "-i", audio_path]
    maps_and_audio = ["-map", "[vout]"]

    if music_path and Path(music_path).exists():
        inputs += ["-stream_loop", "-1", "-i", music_path]
        filter_complex += (
            f";[2:a]volume=1.0[narr];[3:a]volume={music_volume}[mus];[narr][mus]amix=inputs=2:duration=first[aout]"
        )
        maps_and_audio += ["-map", "[aout]"]
    else:
        maps_and_audio += ["-map", "2:a"]

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        *maps_and_audio,
        "-c:v",
        encoder,
        *encoder_opts,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-r",
        str(settings.VIDEO_FPS),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run(cmd, "character overlay compose")
    return output_path


def compose_short(
    scenes: list[dict],
    media_paths: list[str],
    audio_path: str,
    words: list[dict],
    output_path: str,
    music_path: str | None = None,
    music_volume: float = 0.15,
    subtitle_style: dict | None = None,
    overlays: list[dict] | None = None,
    fps: int = 30,
    layout: LayoutConfig | None = None,
) -> str:
    """Compose final video. Dispatches to layout-specific pipeline."""
    job_dir = Path(output_path).parent
    audio_duration = _get_duration(audio_path)

    # For non-fullscreen layouts with a single looped media, dispatch to specialized composers
    if layout and layout.type != "fullscreen" and len(media_paths) == 1:
        ss = subtitle_style or {}

        # For split-screen, position subtitles in the top region
        position = ss.get("position", "bottom")
        margin_v = ss.get("marginBottom", 180)
        if layout.type == "split_horizontal":
            position = "center"
            # Center subtitles within the top region
            top_h = int(settings.VIDEO_HEIGHT * layout.split_ratio)
            margin_v = max(20, top_h // 4)

        ass_path = str(job_dir / "subtitles.ass")
        generate_ass_file(
            words,
            ass_path,
            total_duration=audio_duration,
            font_name=ss.get("fontFamily", "Montserrat").split(",")[0].strip(),
            font_size=ss.get("fontSize", 52),
            primary_color=ss.get("color", "#FFFFFF"),
            outline_color=ss.get("outlineColor", "#000000"),
            bg_color=ss.get("backgroundColor", "rgba(0, 0, 0, 0.6)"),
            margin_v=margin_v,
            stroke_width=ss.get("strokeWidth", 2),
            position=position,
            accent_color=ss.get("accentColor", "#FFFC00"),
        )

        bg_path = str(job_dir / "bg_loop.mp4")
        _prepare_looped_background(media_paths[0], audio_duration, settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT, bg_path)

        if layout.type == "split_horizontal":
            result = _compose_split_screen(
                bg_path,
                audio_path,
                ass_path,
                layout.split_ratio,
                output_path,
                music_path,
                music_volume,
            )
        elif layout.type == "character_overlay" and layout.character_image:
            char_path = str(settings.STORAGE_DIR / "library" / "characters" / layout.character_image)
            if Path(char_path).exists():
                result = _compose_character_overlay(
                    bg_path,
                    char_path,
                    audio_path,
                    ass_path,
                    output_path,
                    music_path,
                    music_volume,
                )
            else:
                logger.warning(f"Character image not found: {char_path}, falling back to fullscreen")
                Path(bg_path).unlink(missing_ok=True)
                # Fall through to fullscreen below
                result = None
        else:
            result = None

        if result is not None:
            Path(bg_path).unlink(missing_ok=True)
            final_duration = _get_duration(output_path)
            logger.info(f"Output [{layout.type}]: {output_path} ({final_duration:.1f}s)")
            return result

    # === FULLSCREEN (original behavior) ===

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
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c:v",
            "copy",
            "-an",
            concat_output,
        ],
        "concat",
    )

    # 5. Generate ASS subtitles (with editor style if available)
    ass_path = str(job_dir / "subtitles.ass")
    ss = subtitle_style or {}
    generate_ass_file(
        words,
        ass_path,
        total_duration=audio_duration,
        font_name=ss.get("fontFamily", "Montserrat").split(",")[0].strip(),
        font_size=ss.get("fontSize", 52),
        primary_color=ss.get("color", "#FFFFFF"),
        outline_color=ss.get("outlineColor", "#000000"),
        bg_color=ss.get("backgroundColor", "rgba(0, 0, 0, 0.6)"),
        margin_v=ss.get("marginBottom", 180),
        stroke_width=ss.get("strokeWidth", 2),
        position=ss.get("position", "bottom"),
        accent_color=ss.get("accentColor", "#FFFC00"),
    )

    # 6. Build video filter chain: subtitles + overlays + watermark
    vf_parts = [f"{_ass_filter(ass_path)}"]  # escaped for FFmpeg filtergraph
    overlay_filters = _build_overlay_filters(overlays or [], fps)
    if overlay_filters:
        vf_parts.append(overlay_filters)
    wm = _watermark_filter()
    if wm:
        vf_parts.append(wm)
    vf_chain = ",".join(vf_parts)

    # 7. Final compose: video + subtitles + overlays + audio with NVENC
    use_nvenc = _has_nvenc()
    encoder = "h264_nvenc" if use_nvenc else "libx264"
    encoder_opts = (
        ["-preset", "p4", "-rc", "vbr", "-cq", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
        if use_nvenc
        else ["-preset", "veryfast", "-crf", "28", "-maxrate", "3000k", "-bufsize", "6000k"]
    )

    logger.info(f"Encoding with {encoder}, overlays: {len(overlays or [])}")

    if music_path and Path(music_path).exists():
        # Mix narration + background music
        logger.info(f"Mixing music at volume {music_volume}")
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                concat_output,
                "-i",
                audio_path,
                "-stream_loop",
                "-1",
                "-i",
                music_path,
                "-filter_complex",
                f"[1:a]volume=1.0[narr];[2:a]volume={music_volume}[mus];[narr][mus]amix=inputs=2:duration=first[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-vf",
                vf_chain,
                "-c:v",
                encoder,
                *encoder_opts,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                "-r",
                str(settings.VIDEO_FPS),
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                output_path,
            ],
            "final encode with music",
        )
    else:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                concat_output,
                "-i",
                audio_path,
                "-vf",
                vf_chain,
                "-c:v",
                encoder,
                *encoder_opts,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                "-r",
                str(settings.VIDEO_FPS),
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                output_path,
            ],
            "final encode",
        )

    # Cleanup temp files
    for p in prepared:
        Path(p).unlink(missing_ok=True)
    Path(concat_file).unlink(missing_ok=True)
    Path(concat_output).unlink(missing_ok=True)

    final_duration = _get_duration(output_path)
    logger.info(f"Output: {output_path} ({final_duration:.1f}s)")
    return output_path
