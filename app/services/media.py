import httpx

from app.config import settings

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_SEARCH = "https://api.pexels.com/v1/search"


async def search_videos(query: str, per_page: int = 5) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            PEXELS_VIDEO_SEARCH,
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            headers={"Authorization": settings.PEXELS_API_KEY},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for video in data.get("videos", []):
        best = _pick_best_video_file(video.get("video_files", []))
        if best:
            results.append({"url": best["link"], "width": best["width"], "height": best["height"]})
    return results


def _pick_best_video_file(files: list[dict]) -> dict | None:
    portrait = [f for f in files if f.get("height", 0) > f.get("width", 0)]
    if not portrait:
        portrait = files
    if not portrait:
        return None
    return max(portrait, key=lambda f: f.get("width", 0))


async def search_photos(query: str, per_page: int = 5) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            PEXELS_PHOTO_SEARCH,
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            headers={"Authorization": settings.PEXELS_API_KEY},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {"url": p["src"]["large2x"], "width": p["width"], "height": p["height"]}
        for p in data.get("photos", [])
    ]


async def download_media(url: str, dest_path: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(resp.content)
    return dest_path
