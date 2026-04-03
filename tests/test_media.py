import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.media import download_media, search_videos


@pytest.mark.asyncio
async def test_search_videos_returns_urls():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "videos": [{
            "video_files": [
                {"width": 1080, "height": 1920, "link": "https://example.com/v.mp4", "quality": "hd"},
                {"width": 640, "height": 360, "link": "https://example.com/v_sd.mp4", "quality": "sd"},
            ]
        }]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.media.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            get=AsyncMock(return_value=mock_response)
        ))
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await search_videos("ocean waves")

    assert len(results) >= 1
    assert "url" in results[0]


@pytest.mark.asyncio
async def test_download_media_saves_file(tmp_path):
    dest = str(tmp_path / "video.mp4")
    mock_response = MagicMock()
    mock_response.content = b"fake video data"
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.media.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            get=AsyncMock(return_value=mock_response)
        ))
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await download_media("https://example.com/v.mp4", dest)

    assert result == dest
