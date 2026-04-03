from app.config import settings


def group_words(words: list[dict], max_words: int = 3) -> list[list[dict]]:
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = words[i:i + max_words]
        if chunk:
            chunks.append(chunk)
    return chunks


def build_subtitle_clips(words: list[dict]):
    """Retorna lista de TextClip do MoviePy para overlay de legendas."""
    from moviepy import TextClip

    chunks = group_words(words, max_words=3)
    clips = []
    for chunk in chunks:
        text = " ".join(w["word"] for w in chunk)
        start = chunk[0]["start"]
        end = chunk[-1]["end"]

        txt = (
            TextClip(
                text=text,
                font=str(settings.FONT_PATH),
                font_size=70,
                color="white",
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(900, None),
            )
            .with_start(start)
            .with_end(end)
            .with_position(("center", 1400))
        )
        clips.append(txt)
    return clips
