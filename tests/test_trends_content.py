"""Conteúdo pt-BR do painel de ideias: tradução de trends + temas prontos por IA."""

import json
from unittest.mock import MagicMock

import pytest

from app.services import trends as trends_mod
from app.services.trends import Trend, _translate_titles
from tests.conftest import FakeRedis


@pytest.fixture()
def redis_env(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(trends_mod, "_redis", fake)
    return fake


def _mock_llm(monkeypatch, payload: str):
    mock = MagicMock(return_value=payload)
    monkeypatch.setattr("app.services.llm.complete_text", mock)
    return mock


def test_translate_titles_fills_title_pt(monkeypatch):
    items = [
        Trend(title="Why the ocean is deep", source="reddit", score=1.0, url="u1"),
        Trend(title="Já está em português", source="reddit", score=0.9, url="u2"),
        Trend(title="Assunto do Brasil", source="google_trends", score=0.8, url="u3"),
    ]
    _mock_llm(monkeypatch, json.dumps({"traducoes": ["Por que o oceano é profundo", "Já está em português"]}))

    _translate_titles(items)

    assert items[0].title_pt == "Por que o oceano é profundo"
    assert items[1].title_pt == "Já está em português"
    # google_trends geo=BR já vem em pt — não entra no batch
    assert items[2].title_pt == ""


def test_translate_titles_ignores_mismatched_count(monkeypatch):
    items = [Trend(title="One", source="hackernews", score=1.0, url="u")]
    _mock_llm(monkeypatch, json.dumps({"traducoes": ["Um", "Extra que não devia estar aqui"]}))

    _translate_titles(items)

    assert items[0].title_pt == ""  # contagem errada = não confia em nada


def test_translate_titles_fails_open(monkeypatch):
    items = [Trend(title="One", source="reddit", score=1.0, url="u")]
    monkeypatch.setattr("app.services.llm.complete_text", MagicMock(side_effect=RuntimeError("LLM caiu")))

    _translate_titles(items)  # não pode levantar

    assert items[0].title_pt == ""


async def test_example_topics_generates_and_caches(monkeypatch, redis_env):
    _mock_llm(
        monkeypatch,
        json.dumps({"topics": [f"Tema pronto número {i} para o nicho" for i in range(1, 9)]}),
    )

    topics = await trends_mod.get_example_topics("curiosidades")

    assert len(topics) == 8
    assert topics[0].startswith("Tema pronto")
    # cacheado por 1h: segunda chamada não bate no LLM
    cached = redis_env.get("example_topics:curiosidades")
    assert cached and json.loads(cached) == topics


async def test_example_topics_unknown_niche_returns_empty(redis_env):
    assert await trends_mod.get_example_topics("nicho-que-nao-existe") == []


async def test_example_topics_fails_open(monkeypatch, redis_env):
    monkeypatch.setattr("app.services.llm.complete_text", MagicMock(side_effect=RuntimeError("sem crédito")))

    assert await trends_mod.get_example_topics("humor") == []


def test_br_subreddits_come_first():
    """Subs pt-BR na frente: o fetch corta em ~15 itens, a ordem decide o idioma do painel."""
    assert trends_mod.NICHE_SUBREDDITS["historias"][0] == "EuSouOBabaca"
    assert trends_mod.NICHE_SUBREDDITS["humor"][0] == "DiretoDoZapZap"
    assert trends_mod.NICHE_SUBREDDITS["financas"][0] == "investimentos"
    # todo nicho do painel tem sabor p/ os temas IA
    assert set(trends_mod.NICHE_FLAVOR) == set(trends_mod.NICHE_SUBREDDITS)
