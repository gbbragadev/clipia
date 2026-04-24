from unittest.mock import MagicMock, patch

from app.services.image_provider import (
    ImageProviderError,
    ModerationBlockedError,
    OpenAIImageProvider,
)


def test_error_classes_exist_and_are_exceptions():
    assert issubclass(ModerationBlockedError, Exception)
    assert issubclass(ImageProviderError, Exception)


def test_provider_can_be_instantiated_with_defaults(tmp_path):
    provider = OpenAIImageProvider(
        api_key="sk-test",
        cache_dir=tmp_path / "cache",
    )
    assert provider.model == "gpt-image-2"
    assert provider.quality == "medium"
    assert provider.size == "1024x1536"
    assert provider.moderation == "low"
    assert provider.max_retries == 3


def test_generate_writes_png_to_output_path(tmp_path, tiny_png_b64):
    output = tmp_path / "scene_1.png"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        mock_openai.return_value.images.generate.return_value = mock_response
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "cache")
        result = provider.generate("retrato sepia de 1912", output)

    assert result == output
    assert output.exists()
    assert output.read_bytes().startswith(b"\x89PNG")


def test_generate_calls_api_with_correct_params(tmp_path, tiny_png_b64):
    output = tmp_path / "scene_1.png"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.return_value = mock_response
        provider = OpenAIImageProvider(
            api_key="sk-test",
            quality="medium",
            size="1024x1536",
            cache_dir=tmp_path / "cache",
        )
        provider.generate("prompt", output)

    gen_mock.assert_called_once()
    kwargs = gen_mock.call_args.kwargs
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["prompt"] == "prompt"
    assert kwargs["size"] == "1024x1536"
    assert kwargs["quality"] == "medium"
    assert kwargs["moderation"] == "low"
    assert kwargs["n"] == 1
