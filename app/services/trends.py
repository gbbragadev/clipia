"""Descoberta de tendencias — temas em alta de fontes gratuitas SEM chave de API.

Alimenta o painel "Em alta" e fundamenta roteiros com dados reais (fact-grounding).
Fontes: Reddit (top/mes por nicho), Hacker News (front page), Google Trends BR (RSS).

ponytail: tudo free/sem-chave; cada fonte degrada graciosamente (falhou -> [] , nunca
derruba o resto). Ranking linear + dedup por overlap de tokens; trocar por embeddings
se a qualidade virar gargalo.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from xml.etree import ElementTree

import httpx

from app.redis_pool import get_redis

logger = logging.getLogger(__name__)
_redis = get_redis()

CACHE_TTL = 4 * 60 * 60  # 4h — tendencias mudam devagar
# UA de browser: Reddit responde 403 a UAs que "parecem script" (ate no .json). RSS+browser passa.
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
_TIMEOUT = 15.0
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# nicho slug -> subreddits. Espelha os slugs de frontend/src/lib/niches.ts.
# Mainstream EN pelo volume de temas; o roteiro e gerado em pt-BR depois.
NICHE_SUBREDDITS: dict[str, list[str]] = {
    "curiosidades": ["todayilearned", "interestingasfuck", "Damnthatsinteresting"],
    "religioso": ["Christianity", "religion", "TrueChristian"],
    "motivacional": ["GetMotivated", "selfimprovement", "decidingtobebetter"],
    "financas": ["personalfinance", "Frugal", "financialindependence"],
    "historias": ["stories", "tifu", "nosleep"],
    "humor": ["funny", "ContagiousLaughter", "Whatcouldgowrong"],
    "drama": ["history", "HistoryMemes", "todayilearned"],
}
DEFAULT_SUBREDDITS = ["todayilearned", "interestingasfuck", "Damnthatsinteresting"]

_STOPWORDS = {
    # pt
    "que",
    "com",
    "uma",
    "para",
    "por",
    "dos",
    "das",
    "como",
    "mais",
    "sobre",
    "este",
    "esta",
    "esse",
    "essa",
    "seu",
    "sua",
    "the",
    "and",
    "for",
    "you",
    "are",
    "was",
    "this",
    "that",
    "with",
    "from",
    "have",
    "what",
    "your",
    "but",
    "not",
    "all",
}


@dataclass
class Trend:
    title: str
    source: str
    score: float
    url: str
    context: str = ""


# ---------- parsers puros (testaveis offline) ----------


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"\w+", title.lower()) if len(w) > 2 and w not in _STOPWORDS}


def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= threshold


def _parse_traffic(text: str) -> float:
    """'20,000+' -> 20000.0 ; '' -> 0.0"""
    digits = re.sub(r"[^\d]", "", text or "")
    return float(digits) if digits else 0.0


def _clean_reddit_body(raw_html: str) -> str:
    """Extrai o corpo textual util de um <content> Atom do Reddit (self-posts: stories,
    tifu, nosleep — onde o corpo E o roteiro). Descarta o rodape 'submitted by' e as tags.
    Vazio p/ link-posts (todayilearned etc), cujo titulo ja e o fato. Limita p/ nao inflar o prompt."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.split(r"submitted by", text, maxsplit=1)[0]  # corta o rodape padrao do Reddit
    text = re.sub(r"<[^>]+>", " ", text)  # strip HTML
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] if len(text) >= 40 else ""


def _parse_reddit_rss(xml_text: str, source: str = "reddit") -> list[Trend]:
    """Reddit bloqueia o .json (403); o feed Atom (.rss) passa. Atom nao traz upvotes,
    entao o score vem da ordem do feed 'top' (ja ordenado por relevancia). O <content> vira
    context (fundamentacao do roteiro) quando e um self-post com corpo util."""
    if "<!DOCTYPE" in xml_text or "<!ENTITY" in xml_text:
        raise ValueError("XML com DTD/ENTITY rejeitado")
    root = ElementTree.fromstring(xml_text)
    entries = root.findall("atom:entry", _ATOM_NS)
    total = len(entries)
    out: list[Trend] = []
    for i, e in enumerate(entries):
        title = (e.findtext("atom:title", default="", namespaces=_ATOM_NS) or "").strip()
        if not title:
            continue
        link = e.find("atom:link", _ATOM_NS)
        url = (link.get("href") if link is not None else "") or ""
        context = _clean_reddit_body(e.findtext("atom:content", default="", namespaces=_ATOM_NS) or "")
        out.append(Trend(title=title, source=source, score=float(total - i), url=url, context=context))
    return out


def _parse_hn(data: dict) -> list[Trend]:
    out: list[Trend] = []
    for hit in data.get("hits", []):
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        oid = hit.get("objectID", "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        out.append(Trend(title=title, source="hackernews", score=float(hit.get("points") or 0), url=url))
    return out


_GT_NS = {"ht": "https://trends.google.com/trending/rss"}


def _parse_google_trends(xml_text: str) -> list[Trend]:
    out: list[Trend] = []
    # ponytail: sem defusedxml (dep nova) — rejeitar DTD/ENTITY mata XXE e billion-laughs,
    # que sao os unicos vetores do ElementTree. Fonte e endpoint fixo do Google, mas guard barato.
    if "<!DOCTYPE" in xml_text or "<!ENTITY" in xml_text:
        raise ValueError("XML com DTD/ENTITY rejeitado")
    root = ElementTree.fromstring(xml_text)
    items = root.findall(".//item")
    total = len(items)
    for i, item in enumerate(items):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = item.findtext("ht:approx_traffic", default="", namespaces=_GT_NS)
        score = _parse_traffic(traffic) or float(total - i)  # fallback: rank decrescente
        news = (item.findtext("ht:news_item/ht:news_item_title", default="", namespaces=_GT_NS) or "").strip()
        link = (item.findtext("link") or "").strip()
        out.append(Trend(title=title, source="google_trends", score=score, url=link, context=news))
    return out


def _rank(groups: list[list[Trend]], limit: int) -> list[Trend]:
    """Normaliza score por fonte (0..1), funde, dedup por titulo similar, top `limit`."""
    merged: list[Trend] = []
    for trends in groups:
        if not trends:
            continue
        mx = max((t.score for t in trends), default=0.0) or 1.0
        merged.extend(replace(t, score=round(t.score / mx, 4)) for t in trends)
    merged.sort(key=lambda t: t.score, reverse=True)

    kept: list[Trend] = []
    for t in merged:
        if any(_similar(t.title, k.title) for k in kept):
            continue
        kept.append(t)
    return kept[:limit]


# ---------- fetch (rede) ----------


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    r = await client.get(url, params=params, headers=_HTTP_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


async def _fetch_reddit(client: httpx.AsyncClient, subs: list[str]) -> list[Trend]:
    out: list[Trend] = []
    for sub in subs:
        try:
            r = await client.get(
                f"https://www.reddit.com/r/{sub}/top/.rss",
                params={"t": "month"},
                headers=_HTTP_HEADERS,
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            out.extend(_parse_reddit_rss(r.text))
            # 1 sub ja traz ~25 itens; parar cedo evita o rate limit (429) do Reddit
            if len(out) >= 15:
                break
        except Exception as e:  # noqa: BLE001 — fonte cai sozinha, nao derruba o resto
            logger.warning("trends: reddit r/%s falhou: %s", sub, e)
    return out


async def _fetch_hn(client: httpx.AsyncClient) -> list[Trend]:
    try:
        data = await _get_json(client, "https://hn.algolia.com/api/v1/search", {"tags": "front_page"})
        return _parse_hn(data)
    except Exception as e:  # noqa: BLE001
        logger.warning("trends: hackernews falhou: %s", e)
        return []


async def _fetch_google_trends(client: httpx.AsyncClient) -> list[Trend]:
    try:
        r = await client.get(
            "https://trends.google.com/trending/rss",
            params={"geo": "BR"},
            headers=_HTTP_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return _parse_google_trends(r.text)
    except Exception as e:  # noqa: BLE001
        logger.warning("trends: google trends falhou: %s", e)
        return []


def _cache_get(key: str) -> list[dict] | None:
    try:
        raw = _redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001 — cache indisponivel nao e fatal
        return None


def _cache_set(key: str, value: list[dict]) -> None:
    try:
        _redis.set(key, json.dumps(value, ensure_ascii=False), ex=CACHE_TTL)
    except Exception:  # noqa: BLE001
        pass


async def fetch_trends(niche: str | None = None, limit: int = 12) -> list[dict]:
    """Temas em alta. niche None -> feed amplo (reddit+HN+Google Trends BR);
    niche definido -> reddit dos subs daquele nicho. Sempre retorna lista (parcial em falha)."""
    cache_key = f"trends:{niche or 'all'}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    subs = NICHE_SUBREDDITS.get(niche, DEFAULT_SUBREDDITS) if niche else DEFAULT_SUBREDDITS
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [_fetch_reddit(client, subs)]
        if niche is None:
            tasks += [_fetch_hn(client), _fetch_google_trends(client)]
        groups = await asyncio.gather(*tasks)

    out = [asdict(t) for t in _rank(list(groups), limit)]
    if out:  # nao cachear vazio: falha transiente nao deve congelar o painel por 4h
        _cache_set(cache_key, out)
    return out
