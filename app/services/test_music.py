"""Check do mapa de música automática por template."""

import os

from app.services.music import _MUSIC_DIR, TEMPLATE_MOODS, resolve_auto_music
from app.templates import TEMPLATES


def test_mapa_cobre_todos_os_templates():
    # nenhum template fica sem mood (senão cai no DEFAULT silenciosamente)
    faltando = set(TEMPLATES) - set(TEMPLATE_MOODS)
    assert not faltando, f"templates sem mood: {faltando}"


def test_resolve_retorna_arquivo_do_mood():
    path = resolve_auto_music("story_time")
    assert path is not None
    assert os.path.basename(path) == "dark-ambient.mp3"


def test_template_desconhecido_cai_no_default():
    path = resolve_auto_music("nao_existe")
    assert path is not None
    assert os.path.basename(path) == "inspirational.mp3"


def test_moods_apontam_para_arquivos_reais():
    # garante que cada mood mapeado existe em frontend/public/music/
    for mood in set(TEMPLATE_MOODS.values()):
        assert (_MUSIC_DIR / f"{mood}.mp3").exists(), f"faixa ausente: {mood}.mp3"


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
