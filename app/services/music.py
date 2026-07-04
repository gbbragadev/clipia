"""Música de fundo automática na geração inicial — mapa template → mood.

As faixas royalty-free vivem em frontend/public/music/ (mesmas que o editor usa); o backend
resolve o path local. Hoje a música só entrava no re-render do editor; isto liga uma trilha
adequada já na geração, sem o usuário precisar abrir o editor (ele ainda pode trocar/desligar lá).
"""

from app.config import BASE_DIR, settings

_MUSIC_DIR = BASE_DIR / "frontend" / "public" / "music"

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


def resolve_music_path(template_id: str) -> str | None:
    """Path FS do mp3 do mood do template (SEM checar a flag global; o caller decide)."""
    path = _MUSIC_DIR / f"{_mood_for(template_id)}.mp3"
    return str(path) if path.exists() else None


def auto_music_url(template_id: str) -> str | None:
    """URL relativa (/music/<mood>.mp3) do mood do template, ou None se a faixa nao existe."""
    mood = _mood_for(template_id)
    return f"/music/{mood}.mp3" if (_MUSIC_DIR / f"{mood}.mp3").exists() else None


def resolve_auto_music(template_id: str) -> str | None:
    """Path FS da musica do template respeitando a flag global AUTO_MUSIC_ENABLED."""
    if not settings.AUTO_MUSIC_ENABLED:
        return None
    return resolve_music_path(template_id)
