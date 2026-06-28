import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_SEARCH = "https://api.pexels.com/v1/search"


async def search_videos(query: str, per_page: int = 10) -> list[dict]:
    """Search Pexels for portrait videos, with retry on failure."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    PEXELS_VIDEO_SEARCH,
                    params={"query": query, "per_page": per_page, "orientation": "portrait"},
                    headers={"Authorization": settings.PEXELS_API_KEY},
                    timeout=20.0,
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for video in data.get("videos", []):
                best = _pick_best_video_file(video.get("video_files", []))
                if best:
                    results.append(
                        {
                            "url": best["link"],
                            "width": best["width"],
                            "height": best["height"],
                            "thumb": video.get("image", ""),
                            "duration": video.get("duration", 0),
                        }
                    )
            if results:
                return results
        except Exception as e:
            logger.warning(f"Pexels video search attempt {attempt + 1} failed for '{query}': {e}")

    return []


def _pick_best_video_file(files: list[dict]) -> dict | None:
    """Pick best portrait video file with minimum resolution."""
    portrait = [f for f in files if f.get("height", 0) > f.get("width", 0) and f.get("width", 0) >= 540]
    if not portrait:
        return None  # Never fall back to landscape — produces bad results
    return max(portrait, key=lambda f: f.get("width", 0))


async def search_media_for_scene(keywords: list[str]) -> list[dict]:
    """Try multiple keyword combinations to find portrait media for a scene."""
    # Try full query first, then progressively simpler queries
    queries = [
        " ".join(keywords[:4]),
        " ".join(keywords[:2]),
        keywords[0] if keywords else "nature",
    ]

    for query in queries:
        results = await search_videos(query)
        if results:
            logger.info(f"Found {len(results)} results for '{query}'")
            return results

    logger.warning(f"No portrait video found for any keyword combination: {keywords}")
    return []


def _clip_scores(text: str, candidates: list[dict]) -> dict[str, float]:
    """Similaridade visual (thumb x texto da cena), 0..1 por url. {} se heuristica/indisponivel."""
    if settings.MEDIA_RERANK != "clip":
        return {}
    try:
        from app.services.clip_rerank import score_candidates

        return score_candidates(text, candidates)
    except Exception as e:  # noqa: BLE001 — CLIP e opt-in; cai na heuristica
        logger.warning("CLIP rerank indisponivel, usando heuristica: %s", e)
        return {}


def order_candidates(candidates: list[dict], scene: dict, used_clips: set[str]) -> list[dict]:
    """Ordena candidatos do melhor ao pior: penaliza clipe ja usado, pontua resolucao e
    proximidade da duracao; com MEDIA_RERANK='clip' soma relevancia semantica (dominante)."""
    if not candidates:
        return []
    target = scene.get("duration_hint", 7) or 7
    text = scene.get("visual_hint") or " ".join(scene.get("keywords_en", []) or []) or scene.get("text", "")
    sims = _clip_scores(text, candidates)

    def score(c: dict) -> float:
        s = 0.0
        if c.get("url") in used_clips:
            s -= 1.0  # repeticao so se nao houver alternativa
        s += min(c.get("width", 0), 1080) / 1080 * 0.3  # resolucao (cap em 1080)
        dur = c.get("duration", 0) or 0
        if dur:
            s -= min(abs(dur - target) / target, 1.0) * 0.3  # proximidade da duracao alvo
        s += sims.get(c.get("url", ""), 0.0)  # relevancia visual (1.0 quando CLIP ativo)
        return s

    return sorted(candidates, key=score, reverse=True)


def pick_best_candidate(candidates: list[dict], scene: dict, used_clips: set[str]) -> dict | None:
    ordered = order_candidates(candidates, scene, used_clips)
    return ordered[0] if ordered else None


async def download_media(url: str, dest_path: str) -> str:
    """Download media file with retry."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30.0, follow_redirects=True)
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
            return dest_path
        except Exception as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
    raise RuntimeError(f"Failed to download {url} after 3 attempts")
