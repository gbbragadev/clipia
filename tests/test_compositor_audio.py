"""Filtro de audio compartilhado do compositor: ducking + loudnorm nos 3 layouts.

Validado com encode real 11/07: ducking mede -7.2dB na banda da musica sob voz
(alvo do roadmap: -7dB), transparente sem voz, loudness integrado -13.6 LUFS
(alvo -14). Estes testes garantem que o filtro nao regride estruturalmente.
"""

from app.services.compositor import _LOUDNORM_AF, _audio_mix_filter


def test_audio_mix_filter_tem_ducking_e_loudnorm():
    f = _audio_mix_filter(1, 2, 0.30)
    assert "sidechaincompress=threshold=0.035:ratio=7:attack=25:release=420" in f
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in f
    assert f.endswith("[aout]")
    # narracao alimenta o mix E o sidechain (asplit), musica passa pelo compressor
    assert "asplit=2[narr][sc]" in f
    assert "[mus][sc]sidechaincompress" in f
    assert "[narr][ducked]amix=inputs=2:duration=first" in f


def test_audio_mix_filter_indices_seguem_inputs():
    f = _audio_mix_filter(2, 3, 0.15)
    assert "[2:a]aresample=48000,volume=1.0" in f
    assert "[3:a]aresample=48000,volume=0.15" in f


def test_loudnorm_af_reamostra_de_volta_para_48k():
    # loudnorm sobe o stream para 192kHz; sem o aresample final o AAC sai em 192k
    assert _LOUDNORM_AF.endswith("aresample=48000")
    assert "loudnorm=I=-14" in _LOUDNORM_AF
