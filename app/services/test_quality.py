"""Check offline do quality gate — parsers de saida ffmpeg/ffprobe + regra de avaliacao."""

from app.services.quality import (
    _parse_black_fraction,
    _parse_mean_volume,
    _parse_probe,
    evaluate,
)


def test_parse_mean_volume():
    assert _parse_mean_volume("[Parsed_volumedetect] mean_volume: -23.4 dB") == -23.4
    assert _parse_mean_volume("sem dados") is None


def test_parse_black_fraction():
    stderr = "blackdetect: black_start:0 black_end:6 black_duration:6\n"
    assert _parse_black_fraction(stderr, total_duration=10) == 0.6
    assert _parse_black_fraction("", total_duration=10) == 0.0


def test_parse_probe():
    probe = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}], "format": {"duration": "42.5"}}
    has_audio, duration = _parse_probe(probe)
    assert has_audio is True
    assert duration == 42.5


def test_evaluate_video_bom():
    r = evaluate(has_audio=True, mean_volume=-20.0, black_fraction=0.0, duration=45, target=45)
    assert r.ok
    assert r.warnings == []


def test_evaluate_pega_mudo():
    r = evaluate(has_audio=True, mean_volume=-80.0, black_fraction=0.0, duration=45, target=45)
    assert not r.ok
    assert any("mudo" in w for w in r.warnings)


def test_evaluate_pega_preto_e_duracao():
    r = evaluate(has_audio=True, mean_volume=-20.0, black_fraction=0.9, duration=10, target=45)
    assert not r.ok
    assert any("preto" in w for w in r.warnings)
    assert any("duracao" in w for w in r.warnings)


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
