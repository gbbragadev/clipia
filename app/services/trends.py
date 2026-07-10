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
# Subs pt-BR PRIMEIRO (o fetch para em ~15 itens, entao a ordem prioriza portugues);
# os mainstream EN completam pelo volume e sao traduzidos na exibicao (title_pt).
NICHE_SUBREDDITS: dict[str, list[str]] = {
    "curiosidades": ["PergunteReddit", "todayilearned", "interestingasfuck", "Damnthatsinteresting"],
    "religioso": ["Catolicismo", "Christianity", "religion", "TrueChristian"],
    "motivacional": ["GetMotivated", "selfimprovement", "decidingtobebetter"],
    "financas": ["investimentos", "personalfinance", "Frugal", "financialindependence"],
    "historias": ["EuSouOBabaca", "desabafos", "stories", "tifu", "nosleep"],
    "humor": ["DiretoDoZapZap", "funny", "ContagiousLaughter", "Whatcouldgowrong"],
    "drama": ["history", "HistoryMemes", "todayilearned"],
}
DEFAULT_SUBREDDITS = ["todayilearned", "interestingasfuck", "Damnthatsinteresting"]

# Sabor de cada nicho p/ gerar temas prontos por IA (get_example_topics).
NICHE_FLAVOR: dict[str, str] = {
    "curiosidades": "fatos surpreendentes de ciencia, historia, natureza e corpo humano",
    "religioso": "reflexoes e historias biblicas/de fe, tom respeitoso e acolhedor",
    "motivacional": "superacao, disciplina, habitos e mentalidade, tom energetico",
    "financas": "dinheiro no dia a dia, investimentos simples, erros comuns, tom pratico",
    "historias": "historias reais dramaticas ou surpreendentes narradas em primeira pessoa",
    "humor": "situacoes engracadas do cotidiano brasileiro, listas comicas",
    "drama": "dramas historicos reais, segredos, tracoes e reviravoltas do passado",
}

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
    # Traducao pt-BR do titulo (fontes EN); exibicao usa title_pt || title.
    # O grounding do roteiro segue usando o title/context ORIGINAIS.
    title_pt: str = ""


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


_TRANSLATE_SOURCES = {"reddit", "hackernews"}  # google_trends geo=BR ja vem em pt


def _translate_titles(trends: list[Trend]) -> None:
    """Preenche title_pt dos itens de fontes EN numa UNICA chamada LLM (batch).

    Roda 1x por refresh do cache (4h) — custo desprezivel. Fail-open: qualquer
    erro deixa title_pt vazio e o painel exibe o titulo original.
    O prompt manda repetir titulos que ja estejam em portugues (subs BR).
    """
    targets = [t for t in trends if t.source in _TRANSLATE_SOURCES and not t.title_pt]
    if not targets:
        return
    from app.services.llm import complete_text  # lazy: evita custo/ciclo no import

    titles_json = json.dumps([t.title for t in targets], ensure_ascii=False)
    prompt = (
        "Traduza os títulos abaixo para português do Brasil, tom jornalístico natural, "
        "mantendo nomes próprios. Se um título já estiver em português, repita-o como está. "
        'Responda APENAS JSON no formato {"traducoes": ["...", ...]} na MESMA ordem e quantidade.\n'
        f"Títulos: {titles_json}"
    )
    try:
        raw = complete_text(prompt, max_tokens=4000)
        translations = json.loads(raw).get("traducoes", [])
        if len(translations) != len(targets):
            logger.warning(
                "trends: traducao voltou %d itens p/ %d titulos — ignorando", len(translations), len(targets)
            )
            return
        for t, translated in zip(targets, translations):
            if isinstance(translated, str) and translated.strip():
                t.title_pt = translated.strip()
    except Exception as e:  # noqa: BLE001 — traducao e cosmetica, nunca derruba o painel
        logger.warning("trends: traducao de titulos falhou (segue em EN): %s", e)


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

    ranked = _rank(list(groups), limit)
    # complete_text e sync (bloquearia o event loop do FastAPI) -> thread
    await asyncio.to_thread(_translate_titles, ranked)

    out = [asdict(t) for t in ranked]
    if out:  # nao cachear vazio: falha transiente nao deve congelar o painel por 4h
        _cache_set(cache_key, out)
    return out


# ---------- temas prontos rotativos (gerados por IA, renovam por hora) ----------

EXAMPLE_TOPICS_TTL = 60 * 60  # 1h — "temas prontos" renovam a cada hora


def _generate_example_topics(niche: str) -> list[str]:
    """8 temas prontos pt-BR no sabor do nicho, via LLM (sync — chamar em thread)."""
    flavor = NICHE_FLAVOR.get(niche)
    if not flavor:
        return []
    from app.services.llm import complete_text  # lazy

    prompt = (
        f"Gere 8 temas para vídeos curtos (Shorts/Reels/TikTok) em português do Brasil "
        f"sobre o nicho: {flavor}. Cada tema deve ser um título pronto, específico e clicável "
        f"(30-70 caracteres), variado entre si, sem numeração. "
        'Responda APENAS JSON: {"topics": ["...", ...]}'
    )
    raw = complete_text(prompt, max_tokens=2000)
    topics = json.loads(raw).get("topics", [])
    return [t.strip() for t in topics if isinstance(t, str) and 10 <= len(t.strip()) <= 90][:8]


async def get_example_topics(niche: str) -> list[str]:
    """Temas prontos do nicho com cache de 1h. Lista vazia em falha/nicho
    desconhecido — o frontend cai no fallback estático (niches.ts)."""
    cache_key = f"example_topics:{niche}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        topics = await asyncio.to_thread(_generate_example_topics, niche)
    except Exception as e:  # noqa: BLE001 — painel nunca quebra por falha de LLM
        logger.warning("example topics: geracao falhou p/ %s: %s", niche, e)
        return []
    if topics:
        try:
            _redis.set(cache_key, json.dumps(topics, ensure_ascii=False), ex=EXAMPLE_TOPICS_TTL)
        except Exception:  # noqa: BLE001
            pass
    return topics
