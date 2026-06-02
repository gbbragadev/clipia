"""Build Remotion CompositionData (props.json) from a generated job's artifacts.

Fase 1 spike helper. Assets are served over HTTP by the running backend
(StaticFiles mount at /storage/jobs), so the headless Remotion renderer can
fetch narration.wav and the per-scene media clips.

Usage:
    python -m scripts.build_remotion_props <job_id> [out_path] [backend_url]
"""

import json
import sys
from pathlib import Path

from app.config import settings

DEFAULT_SUBTITLE_STYLE = {
    "fontFamily": "Montserrat, sans-serif",
    "fontSize": 52,
    "color": "#FFFFFF",
    "outlineColor": "#000000",
    "backgroundColor": "rgba(0, 0, 0, 0.6)",
    "position": "bottom",
    "marginBottom": 180,
    "maxWordsPerChunk": 3,
    "preset": "minimal",
    "accentColor": "#FFFC00",
    "strokeWidth": 0,
    "animationStyle": "pop",
}

DEFAULT_VOICE_CONFIG = {
    "voiceId": "pt-BR-AntonioNeural",
    "voiceProvider": "edge",
    "rate": -10,
    "pitch": 5,
}


def _read_json(path: Path):
    """Read JSON tolerating non-UTF-8 files (worker writes cp1252 on Windows)."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def build_props(job_id: str, backend_url: str = "http://127.0.0.1:8005") -> dict:
    base = settings.STORAGE_DIR / "jobs" / job_id
    script = _read_json(base / "script.json")
    words_raw = _read_json(base / "words.json")
    words = words_raw["words"] if isinstance(words_raw, dict) and "words" in words_raw else words_raw

    media_dir = base / "media"
    media = sorted(media_dir.glob("scene_*.mp4"), key=lambda p: int(p.stem.split("_")[1]))

    def url(rel: str) -> str:
        return f"{backend_url}/storage/jobs/{job_id}/{rel}"

    scenes = [
        {
            "text": s.get("text", ""),
            "keywords_en": s.get("keywords_en", []),
            "duration_hint": s.get("duration_hint", 5),
            "transition": s.get("transition", "none"),
        }
        for s in script.get("scenes", [])
    ]

    return {
        "title": script.get("title", ""),
        "scenes": scenes,
        "words": words,
        "audioUrl": url("narration.wav"),
        "mediaUrls": [url(f"media/{p.name}") for p in media],
        "subtitleStyle": DEFAULT_SUBTITLE_STYLE,
        "voiceConfig": DEFAULT_VOICE_CONFIG,
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "overlays": [],
        "musicUrl": None,
        "musicVolume": 0.15,
        "isRendering": True,
        "layoutType": "fullscreen",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m scripts.build_remotion_props <job_id> [out_path] [backend_url]")
        sys.exit(2)
    job_id = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("storage/remotion-spike/props.json")
    backend = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8005"
    props = build_props(job_id, backend)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {out_path}: {len(props['scenes'])} scenes, {len(props['words'])} words, {len(props['mediaUrls'])} media"
    )
