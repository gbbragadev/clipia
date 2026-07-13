"""Música de fundo automática na geração inicial — mapa template → mood.

As faixas royalty-free vivem em frontend/public/music/ (mesmas que o editor usa); o backend
resolve o path local. Hoje a música só entrava no re-render do editor; isto liga uma trilha
adequada já na geração, sem o usuário precisar abrir o editor (ele ainda pode trocar/desligar lá).
"""

from pathlib import Path

from app.config import BASE_DIR, settings

_MUSIC_DIR = BASE_DIR / "frontend" / "public" / "music"

MUSIC_ASSET_IDS = frozenset(
    {
        "lofi-chill",
        "upbeat-energy",
        "dramatic-epic",
        "ambient-calm",
        "cinematic-tension",
        "happy-pop",
        "dark-ambient",
        "inspirational",
        "dreamy-space",
        "tech-pulse",
    }
)

# template_id -> nome do arquivo (sem .mp3) em frontend/public/music/
TEMPLATE_MOODS: dict[str, str] = {
    "stock_narration": "inspirational",
    # Templates virais Q4: energia de lista viral / curiosidade leve.
    "curiosidades_lista": "upbeat-energy",
    "voce_sabia": "inspirational",
    "gameplay_split": "upbeat-energy",
    "character_narration": "happy-pop",
    "story_time": "dark-ambient",
    "novelinha_historica": "cinematic-tension",
    "ai_visual": "dreamy-space",
    "ai_video": "cinematic-tension",  # video IA premium = trilha épica
    "dialogue_duo": "lofi-chill",  # suave, não compete com as falas
}
DEFAULT_MOOD = "inspirational"


def _mood_for(template_id: str) -> str:
    return TEMPLATE_MOODS.get(template_id, DEFAULT_MOOD)


def validate_music_asset_id(asset_id: str) -> str:
    """Validate an opaque public asset ID without accepting paths or URLs."""
    if asset_id not in MUSIC_ASSET_IDS:
        raise ValueError("Unknown music asset")
    return asset_id


def resolve_music_asset_path(asset_id: str) -> Path | None:
    """Resolve an allowlisted ID to a contained, server-owned file."""
    validate_music_asset_id(asset_id)
    root = _MUSIC_DIR.resolve()
    candidate = (root / f"{asset_id}.mp3").resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Music asset escaped its server-owned directory")
    return candidate if candidate.is_file() else None


def legacy_music_url_to_asset_id(value: object) -> str | None:
    """Migrate only the exact relative URLs emitted by older ClipIA builds."""
    if not isinstance(value, str):
        return None
    for asset_id in MUSIC_ASSET_IDS:
        if value == f"/music/{asset_id}.mp3":
            return asset_id
    return None


def sanitize_editor_state_assets(editor_state: object) -> dict | None:
    """Return legacy editor state with public paths replaced by opaque IDs."""
    if not isinstance(editor_state, dict):
        return None
    sanitized = dict(editor_state)
    composition = sanitized.get("composition")
    if not isinstance(composition, dict):
        return sanitized

    safe_composition = dict(composition)
    if "musicAssetId" in safe_composition:
        asset_id = safe_composition["musicAssetId"]
        if asset_id is not None:
            try:
                validate_music_asset_id(asset_id)
            except (TypeError, ValueError):
                safe_composition.pop("musicAssetId", None)
    elif "musicUrl" in safe_composition:
        legacy_value = safe_composition.pop("musicUrl")
        if legacy_value is None:
            safe_composition["musicAssetId"] = None
        else:
            asset_id = legacy_music_url_to_asset_id(legacy_value)
            if asset_id is not None:
                safe_composition["musicAssetId"] = asset_id

    safe_composition.pop("musicUrl", None)
    voice_config = safe_composition.get("voiceConfig")
    if isinstance(voice_config, dict):
        safe_composition["voiceConfig"] = {
            key: voice_config[key] for key in ("voiceId", "voiceProvider", "rate", "pitch") if key in voice_config
        }
    sanitized["composition"] = safe_composition
    return sanitized


def resolve_music_path(template_id: str) -> str | None:
    """Path FS do mp3 do mood do template (SEM checar a flag global; o caller decide)."""
    path = resolve_music_asset_path(_mood_for(template_id))
    return str(path) if path else None


def auto_music_asset_id(template_id: str) -> str | None:
    """Opaque ID for the template mood, only when its owned file exists."""
    asset_id = _mood_for(template_id)
    return asset_id if resolve_music_asset_path(asset_id) else None


def resolve_auto_music(template_id: str) -> str | None:
    """Path FS da musica do template respeitando a flag global AUTO_MUSIC_ENABLED."""
    if not settings.AUTO_MUSIC_ENABLED:
        return None
    return resolve_music_path(template_id)
