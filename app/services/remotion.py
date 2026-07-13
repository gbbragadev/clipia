"""Remotion server-side render integration (Fase 2 — hybrid export path).

O export editado (`POST /render` -> `task_rerender_video`) renderiza via Remotion
para que o que o usuario edita no preview (que ja e Remotion) seja exatamente o que
sai no MP4. A geracao inicial continua no FFmpeg/NVENC (rapido).

Assets (narration.wav, media/scene_*.mp4) sao servidos por HTTP pelo backend
(StaticFiles em /storage/jobs); musica (frontend/public/music) resolve via o
publicDir do bundle Remotion, entao fica como URL relativa.
"""

import json
import logging
import subprocess
from pathlib import Path

from app.config import BASE_DIR, settings
from app.services.music import legacy_music_url_to_asset_id, validate_music_asset_id
from app.utils.media_url import sign_media_url

logger = logging.getLogger(__name__)

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
    "accentColor": "#F05340",
    "strokeWidth": 0,
    "animationStyle": "pop",
}

DEFAULT_VOICE_CONFIG = {
    "voiceId": "pt-BR-AntonioNeural",
    "voiceProvider": "edge",
    "rate": -10,
    "pitch": 5,
}

# Fields the editor may have changed that we trust from editor_state.composition.
_EDITABLE_KEYS = ("subtitleStyle", "overlays", "musicVolume", "layoutType")


def _read_json(path: Path):
    """Read JSON tolerating non-UTF-8 legacy files (older worker wrote cp1252)."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def _backend_url(explicit: str | None = None) -> str:
    return explicit or settings.BACKEND_URL or "http://127.0.0.1:8005"


def scene_sort_key(p: Path) -> int:
    """Sort key para scene_N.* tolerante a nomes fora do padrao (vao para o fim)."""
    try:
        return int(p.stem.split("_")[1])
    except (ValueError, IndexError):
        return 10**9


def build_composition_props(
    job_id: str,
    backend_url: str | None = None,
    audio_filename: str = "narration.wav",
    default_music_asset_id: str | None = None,
) -> dict:
    """Build the Remotion CompositionData for a job.

    Authoritative asset URLs come from the job files; edited fields (caption
    style, overlays, music, voice) are overlaid from editor_state.json if present.
    """
    backend = _backend_url(backend_url)
    job_dir = settings.STORAGE_DIR / "jobs" / job_id

    script = _read_json(job_dir / "script.json")
    words_raw = _read_json(job_dir / "words.json")
    words = words_raw["words"] if isinstance(words_raw, dict) and "words" in words_raw else words_raw

    media_dir = job_dir / "media"
    images_dir = job_dir / "images"
    bg = media_dir / "background.mp4"
    if bg.exists():
        media_files = [bg]
    else:
        media_files = sorted(media_dir.glob("scene_*.mp4"), key=scene_sort_key)
        if not media_files and images_dir.exists():
            # Jobs ai_image (novelinha): cenas sao PNGs 1-based gerados pelo worker
            media_files = sorted(images_dir.glob("scene_*.png"), key=scene_sort_key)

    def url(rel: str) -> str:
        return sign_media_url(f"{backend}/storage/jobs/{job_id}/{rel}")

    scenes = [
        {
            "text": s.get("text", ""),
            "keywords_en": s.get("keywords_en", []),
            "duration_hint": s.get("duration_hint", 5),
            "transition": s.get("transition", "none"),
        }
        for s in script.get("scenes", [])
    ]

    props: dict = {
        "title": script.get("title", ""),
        "scenes": scenes,
        "words": words,
        "audioUrl": url(audio_filename),
        "mediaUrls": [url(f"{p.parent.name}/{p.name}") for p in media_files],
        "subtitleStyle": DEFAULT_SUBTITLE_STYLE,
        "voiceConfig": DEFAULT_VOICE_CONFIG,
        "fps": settings.VIDEO_FPS,
        "width": settings.VIDEO_WIDTH,
        "height": settings.VIDEO_HEIGHT,
        "overlays": [],
        "musicAssetId": default_music_asset_id,
        "musicVolume": settings.AUTO_MUSIC_VOLUME,
        "isRendering": True,
        "layoutType": "fullscreen",
    }

    state_path = job_dir / "editor_state.json"
    if state_path.exists():
        comp = (_read_json(state_path) or {}).get("composition", {}) or {}
        for key in _EDITABLE_KEYS:
            if comp.get(key) is not None:
                props[key] = comp[key]

        if "musicAssetId" in comp:
            asset_id = comp["musicAssetId"]
            if asset_id is None:
                props["musicAssetId"] = None
            else:
                try:
                    props["musicAssetId"] = validate_music_asset_id(asset_id)
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid music asset ID for job %s", job_id)
        elif "musicUrl" in comp:
            legacy_value = comp["musicUrl"]
            if legacy_value is None:
                props["musicAssetId"] = None
            else:
                migrated_id = legacy_music_url_to_asset_id(legacy_value)
                if migrated_id is not None:
                    props["musicAssetId"] = migrated_id

        voice_config = comp.get("voiceConfig")
        if isinstance(voice_config, dict):
            props["voiceConfig"] = {
                key: voice_config[key] for key in ("voiceId", "voiceProvider", "rate", "pitch") if key in voice_config
            }

    if settings.WATERMARK_ENABLED and settings.WATERMARK_TEXT:
        props["watermark"] = settings.WATERMARK_TEXT

    return props


def invoke_remotion_render(
    job_id: str,
    output_path: str,
    on_progress=None,
    timeout: int | None = None,
    audio_filename: str = "narration.wav",
    default_music_asset_id: str | None = None,
) -> str:
    """Render a job's composition to output_path via the Remotion CLI helper.

    on_progress(pct: int) is called with 0..100 during rendering. Raises on failure.
    """
    timeout = timeout or settings.REMOTION_RENDER_TIMEOUT
    job_dir = settings.STORAGE_DIR / "jobs" / job_id

    # Render server-side roda NA MESMA maquina do backend (worker local, deploy=checkout):
    # buscar midia por BACKEND_URL publico faz hairpin localhost->Cloudflare->tunnel->localhost
    # que ja passou de 30s por asset — estoura o delayRender de 28s do Remotion e mata o export.
    # URLs publicas continuam valendo para o browser (composition endpoint usa BACKEND_URL).
    local_backend = "http://127.0.0.1:8005"
    props = build_composition_props(
        job_id,
        backend_url=local_backend,
        audio_filename=audio_filename,
        default_music_asset_id=default_music_asset_id,
    )
    # Public music asset IDs are resolved by Remotion's staticFile mapping inside
    # the frontend bundle; the backend never accepts or constructs a client path.
    props_path = job_dir / "remotion_props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    frontend_dir = BASE_DIR / "frontend"
    script_path = frontend_dir / "scripts" / "render-composition.mjs"
    cmd = ["node", str(script_path), "--props", str(props_path), "--out", str(output_path)]

    logger.info("[remotion] render job %s -> %s", job_id, output_path)
    proc = subprocess.Popen(
        cmd,
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    last_event: dict = {}
    try:
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.info("[remotion] %s", line)
                continue
            last_event = event
            status = event.get("status")
            if status == "rendering" and on_progress:
                on_progress(int(event.get("progress", 0)))
            elif status == "error":
                logger.error("[remotion] error: %s", str(event.get("message"))[:1000])
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Remotion render timed out after {timeout}s")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed (exit {proc.returncode}): {str(last_event.get('message', ''))[:500]}"
        )
    if not Path(output_path).exists():
        raise RuntimeError("Remotion render finished but output file is missing")

    return output_path
