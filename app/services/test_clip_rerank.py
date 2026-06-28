"""Check da normalizacao do CLIP rerank (pura, nao precisa de torch/sentence-transformers)."""

from app.services.clip_rerank import _minmax_norm


def test_minmax_norm():
    assert _minmax_norm([0.1, 0.5, 0.9]) == [0.0, 0.5, 1.0]
    assert _minmax_norm([]) == []
    assert _minmax_norm([0.3, 0.3]) == [0.0, 0.0]  # span 0 -> nao divide por zero


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
