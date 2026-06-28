"""Check offline do scoring de midia (heuristica, sem CLIP/rede)."""

from app.services.media import order_candidates, pick_best_candidate


def _cand(url, width=1080, duration=8):
    return {"url": url, "width": width, "height": 1920, "duration": duration, "thumb": ""}


def test_penaliza_clipe_repetido():
    scene = {"duration_hint": 8, "keywords_en": ["ocean"]}
    cands = [_cand("a.mp4"), _cand("b.mp4")]
    # 'a' ja foi usado numa cena anterior -> 'b' deve vir na frente
    ordered = order_candidates(cands, scene, used_clips={"a.mp4"})
    assert ordered[0]["url"] == "b.mp4"
    # mas 'a' ainda aparece (so se nao houvesse alternativa seria escolhido)
    assert {c["url"] for c in ordered} == {"a.mp4", "b.mp4"}


def test_duracao_proxima_vence():
    scene = {"duration_hint": 8}
    cands = [_cand("long.mp4", duration=40), _cand("fit.mp4", duration=8)]
    assert pick_best_candidate(cands, scene, used_clips=set())["url"] == "fit.mp4"


def test_resolucao_maior_vence_empate_de_duracao():
    scene = {"duration_hint": 8}
    cands = [_cand("sd.mp4", width=540, duration=8), _cand("hd.mp4", width=1080, duration=8)]
    assert pick_best_candidate(cands, scene, used_clips=set())["url"] == "hd.mp4"


def test_lista_vazia():
    assert pick_best_candidate([], {"duration_hint": 8}, set()) is None


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
