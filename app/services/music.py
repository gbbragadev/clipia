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
    "gameplay_split": "upbeat-energy",
    "character_narration": "happy-pop",
    "story_time": "dark-ambient",
    "novelinha_historica": "cinematic-tension",
    "ai_visual": "dreamy-space",
    "ai_video": "cinematic-tension",  # video IA premium = trilha épica
    "dialogue_duo": "lofi-chill",  # suave, não compete com as falas
}
DEFAULT_MOOD = "inspirational"


def resolve_auto_music(template_id: str) -> str | None:
    """Path do mp3 de fundo para o template, ou None se desabilitado/arquivo ausente."""
    if not settings.AUTO_MUSIC_ENABLED:
        return None
    mood = TEMPLATE_MOODS.get(template_id, DEFAULT_MOOD)
    path = _MUSIC_DIR / f"{mood}.mp3"
    return str(path) if path.exists() else None
