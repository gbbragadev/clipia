"""Check offline do trends.py — parsers + ranking + dedup + guard de segurança. Sem rede."""

import pytest

from app.services.trends import (
    Trend,
    _parse_google_trends,
    _parse_hn,
    _parse_reddit_rss,
    _parse_traffic,
    _rank,
    _similar,
)

_REDDIT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Fato curioso sobre o oceano</title><link href="https://www.reddit.com/r/x/comments/1/"/></entry>
  <entry><title>Segundo post em alta</title><link href="https://www.reddit.com/r/x/comments/2/"/></entry>
</feed>"""


def test_parse_reddit_rss_uses_feed_order_as_score():
    out = _parse_reddit_rss(_REDDIT_ATOM)
    assert len(out) == 2
    assert out[0].title == "Fato curioso sobre o oceano"
    assert out[0].url == "https://www.reddit.com/r/x/comments/1/"
    assert out[0].source == "reddit"
    # feed 'top' ja vem ordenado -> primeiro post tem score maior
    assert out[0].score > out[1].score


_REDDIT_ATOM_SELFPOST = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>TIFU por deixar o bolo no forno</title>
    <link href="https://www.reddit.com/r/tifu/comments/9/"/>
    <content type="html">&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;Ontem decidi fazer um bolo pra familia toda e esqueci ele no forno por tres horas. A casa inteira ficou tomada de fumaca preta.&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt; submitted by &lt;a href="x"&gt;/u/foo&lt;/a&gt;</content>
  </entry>
  <entry>
    <title>Post so de link sem corpo</title>
    <link href="https://www.reddit.com/r/x/comments/2/"/>
    <content type="html">&lt;!-- SC_OFF --&gt;&lt;!-- SC_ON --&gt; submitted by &lt;a href="x"&gt;/u/bar&lt;/a&gt;</content>
  </entry>
</feed>"""


def test_parse_reddit_rss_extracts_selfpost_body_as_context():
    out = _parse_reddit_rss(_REDDIT_ATOM_SELFPOST)
    # self-post: corpo vira context (fundamentacao do roteiro), sem rodape nem tags
    assert "bolo" in out[0].context and "forno" in out[0].context
    assert "submitted by" not in out[0].context
    assert "<" not in out[0].context
    # link-post sem corpo util -> context vazio (o titulo ja basta)
    assert out[1].context == ""


def test_parse_reddit_rss_rejects_dtd():
    import pytest as _pt

    with _pt.raises(ValueError):
        _parse_reddit_rss('<!DOCTYPE x [<!ENTITY a "b">]><feed></feed>')


def test_parse_hn_fallback_url():
    out = _parse_hn({"hits": [{"title": "Show HN", "points": 120, "objectID": "42", "url": None}]})
    assert out[0].url == "https://news.ycombinator.com/item?id=42"
    assert out[0].score == 120.0


def test_parse_traffic():
    assert _parse_traffic("20,000+") == 20000.0
    assert _parse_traffic("") == 0.0


def test_google_trends_rejects_dtd():
    with pytest.raises(ValueError):
        _parse_google_trends('<!DOCTYPE x [<!ENTITY a "b">]><rss></rss>')


def test_rank_normalizes_across_sources_and_dedups():
    # reddit tem scores grandes, hn pequenos; apos normalizar, o topo de cada fonte compete em pe de igualdade
    reddit = [Trend("Tubarao gigante encontrado", "reddit", 10000, ""), Trend("Gato fofo", "reddit", 100, "")]
    hn = [Trend("Novo modelo de IA bate recorde", "hackernews", 50, "")]
    dup = [Trend("Tubarao gigante foi encontrado hoje", "google_trends", 999, "")]  # ~ ao reddit[0]

    ranked = _rank([reddit, hn, dup], limit=10)
    titles = [t.title for t in ranked]
    # o duplicado do tubarao nao aparece duas vezes
    assert sum("ubarao" in t for t in titles) == 1
    # reddit[0] (score 1.0 normalizado) e hn[0] (1.0) ficam no topo, acima de "Gato fofo" (0.01)
    assert titles[-1] == "Gato fofo"


def test_similar():
    assert _similar("Tubarao gigante encontrado", "Tubarao gigante foi encontrado hoje")
    assert not _similar("Receita de bolo", "Mercado financeiro hoje")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
