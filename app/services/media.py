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
                    results.append({"url": best["link"], "width": best["width"], "height": best["height"]})
            if results:
                return results
        except Exception as e:
            logger.warning(f"Pexels video search attempt {attempt + 1} failed for '{query}': {e}")

    return []


def _pick_best_video_file(files: list[dict]) -> dict | None:
    """Pick best portrait video file with minimum resolution."""
    portrait = [
        f for f in files
        if f.get("height", 0) > f.get("width", 0) and f.get("width", 0) >= 540
    ]
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
