"""Generate ASS subtitle files for FFmpeg overlay."""


def group_words(words: list[dict], max_words: int = 3) -> list[list[dict]]:
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = words[i:i + max_words]
        if chunk:
            chunks.append(chunk)
    return chunks


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def generate_ass_file(words: list[dict], output_path: str, total_duration: float = 0) -> str:
    """Generate an ASS subtitle file from word timestamps.

    Style: TikTok-inspired — bold white text, semi-transparent black box background,
    centered near bottom of 1080x1920 portrait frame.
    """
    chunks = group_words(words, max_words=3)

    header = """[Script Info]
Title: ClipIA Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,52,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,4,2,0,2,40,40,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for chunk in chunks:
        text = " ".join(w["word"] for w in chunk)
        start = chunk[0]["start"]
        end = chunk[-1]["end"]

        if end <= start:
            continue
        if total_duration > 0 and start >= total_duration:
            break
        if total_duration > 0:
            end = min(end, total_duration - 0.01)

        start_ts = _format_ass_time(start)
        end_ts = _format_ass_time(end)
        # Uppercase for impact (TikTok style)
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text.upper()}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    return output_path


# Keep backward compat for any code that imports build_subtitle_clips
def build_subtitle_clips(words: list[dict], total_duration: float = 0):
    """Legacy — returns empty list. Use generate_ass_file instead."""
    return []
