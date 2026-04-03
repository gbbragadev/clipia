from unittest.mock import MagicMock, patch

from app.services.compositor import compose_short


def test_compose_short_calls_moviepy():
    scenes = [{"text": "Cena um", "keywords_en": ["ocean"], "duration_hint": 5}]
    media_paths = ["/tmp/scene0.mp4"]

    mock_video = MagicMock()
    mock_video.w = 1080
    mock_video.h = 1920
    mock_video.duration = 10
    mock_video.resized.return_value = mock_video
    mock_video.cropped.return_value = mock_video
    mock_video.with_duration.return_value = mock_video

    mock_audio = MagicMock()
    mock_audio.duration = 5.0

    mock_composite = MagicMock()

    with (
        patch("app.services.compositor.VideoFileClip", return_value=mock_video),
        patch("app.services.compositor.AudioFileClip", return_value=mock_audio),
        patch("app.services.compositor.concatenate_videoclips", return_value=mock_video),
        patch("app.services.compositor.CompositeVideoClip", return_value=mock_composite),
        patch("app.services.compositor.build_subtitle_clips", return_value=[]),
    ):
        mock_video.with_audio.return_value = mock_composite
        mock_composite.with_audio.return_value = mock_composite
        mock_composite.with_duration.return_value = mock_composite

        compose_short(
            scenes=scenes,
            media_paths=media_paths,
            audio_path="/tmp/narration.wav",
            words=[],
            output_path="/tmp/final.mp4",
        )

    mock_composite.write_videofile.assert_called_once()
