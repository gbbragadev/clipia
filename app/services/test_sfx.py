"""Check offline do SFX — cálculo de tempos de transição (puro, sem rede/ffmpeg)."""

from app.services.sfx import _scaled_transitions


def test_escala_para_duracao_real():
    # 4 cenas de 5s (20s no script) esticadas p/ 40s reais -> fator 2
    assert _scaled_transitions([5, 5, 5, 5], real_duration=40) == [10.0, 20.0, 30.0]


def test_uma_cena_sem_transicao():
    assert _scaled_transitions([7], real_duration=7) == []


def test_comprime_quando_real_menor():
    assert _scaled_transitions([10, 10], real_duration=10) == [5.0]


def test_ignora_duracoes_zeradas():
    assert _scaled_transitions([0, 0], real_duration=10) == []


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
