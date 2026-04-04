"""Generate ASS subtitle files for FFmpeg overlay."""
import re


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


def _hex_to_ass_color(hex_color: str) -> str:
    """Convert #RRGGBB to ASS &H00BBGGRR format."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}"
    return "&H00FFFFFF"


def _rgba_to_ass_bg(rgba: str) -> str:
    """Convert rgba(r,g,b,a) to ASS &HAABBGGRR format."""
    m = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+),?\s*([\d.]+)?\)', rgba)
    if not m:
        return "&H96000000"
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) else 1.0
    # ASS alpha: 00=opaque, FF=transparent (inverted)
    alpha = hex(int((1 - a) * 255))[2:].upper().zfill(2)
    return f"&H{alpha}{b:02X}{g:02X}{r:02X}"


def generate_ass_file(
    words: list[dict],
    output_path: str,
    total_duration: float = 0,
    font_name: str = "Montserrat",
    font_size: int = 52,
    primary_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    bg_color: str = "rgba(0, 0, 0, 0.6)",
    margin_v: int = 180,
    stroke_width: int = 2,
    position: str = "bottom",
    accent_color: str = "#FFFC00",
) -> str:
    """Generate an ASS subtitle file from word timestamps.

    Style parameters map to editor subtitle settings.
    Uses karaoke fill (\\kf) tags for word-by-word highlighting.
    PrimaryColour = accent (fill-to color during karaoke).
    SecondaryColour = normal text color (fill-from color).
    """
    chunks = group_words(words, max_words=3)

    # For karaoke: text starts as SecondaryColour and fills to PrimaryColour
    primary_ass = _hex_to_ass_color(accent_color)   # highlight / fill-to
    secondary_ass = _hex_to_ass_color(primary_color)  # normal text / fill-from
    outline = _hex_to_ass_color(outline_color)
    back = _rgba_to_ass_bg(bg_color)
    # Alignment: 2=bottom-center, 5=middle-center
    alignment = 5 if position == "center" else 2
    # BorderStyle: 4=opaque box background, 1=outline only
    border_style = 4 if bg_color != "transparent" else 1

    header = f"""[Script Info]
Title: ClipIA Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_ass},{secondary_ass},{outline},{back},-1,0,0,0,100,100,0,0,{border_style},{stroke_width},0,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for chunk in chunks:
        start = chunk[0]["start"]
        end = chunk[-1]["end"]

        if end <= start:
            continue
        if total_duration > 0 and start >= total_duration:
            break
        if total_duration > 0:
            end = min(end, total_duration - 0.01)

        # Build karaoke text with \kf tags for each word
        karaoke_parts = []
        for i, w in enumerate(chunk):
            duration_cs = max(1, round((w["end"] - w["start"]) * 100))
            word_text = w["word"].upper()
            if i < len(chunk) - 1:
                word_text += " "
            karaoke_parts.append(f"{{\\kf{duration_cs}}}{word_text}")
        text = "".join(karaoke_parts)

        start_ts = _format_ass_time(start)
        end_ts = _format_ass_time(end)
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    return output_path


# Keep backward compat for any code that imports build_subtitle_clips
def build_subtitle_clips(words: list[dict], total_duration: float = 0):
    """Legacy — returns empty list. Use generate_ass_file instead."""
    return []
