from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import APIStatusError, BadRequestError

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


def test_generate_uses_cache_on_second_identical_call(tmp_path, tiny_png_b64):
    output1 = tmp_path / "scene_1.png"
    output2 = tmp_path / "scene_1_copy.png"
    cache = tmp_path / "cache"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.return_value = mock_response
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=cache)
        provider.generate("mesma prompt", output1)
        provider.generate("mesma prompt", output2)

    assert gen_mock.call_count == 1
    assert output1.exists()
    assert output2.exists()
    assert output1.read_bytes() == output2.read_bytes()


def test_cache_key_differs_by_quality(tmp_path):
    provider_low = OpenAIImageProvider(api_key="sk-test", quality="low", cache_dir=tmp_path / "c")
    provider_high = OpenAIImageProvider(api_key="sk-test", quality="high", cache_dir=tmp_path / "c")
    assert provider_low._cache_key("mesma") != provider_high._cache_key("mesma")


def test_cache_key_differs_by_size(tmp_path):
    p1 = OpenAIImageProvider(api_key="sk-test", size="1024x1536", cache_dir=tmp_path / "c")
    p2 = OpenAIImageProvider(api_key="sk-test", size="1024x1024", cache_dir=tmp_path / "c")
    assert p1._cache_key("mesma") != p2._cache_key("mesma")


def _api_status_error(status_code: int, message: str = "transient") -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return APIStatusError(message=message, response=response, body=None)


def _bad_request_moderation() -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"message": "moderation_blocked: content violates policy"}},
    )
    return BadRequestError(
        message="moderation_blocked: content violates policy",
        response=response,
        body=None,
    )


def test_generate_retries_on_rate_limit_429(tmp_path, tiny_png_b64, monkeypatch):
    monkeypatch.setattr("app.services.image_provider.time.sleep", lambda *_: None)
    ok = MagicMock()
    ok.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = [_api_status_error(429), _api_status_error(429), ok]
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "c")
        provider.generate("prompt", tmp_path / "out.png")

    assert gen_mock.call_count == 3


def test_generate_raises_moderation_blocked(tmp_path):
    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = _bad_request_moderation()
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "c")
        with pytest.raises(ModerationBlockedError):
            provider.generate("violência explícita", tmp_path / "out.png")
    assert gen_mock.call_count == 1  # no retry on moderation


def test_generate_raises_provider_error_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.image_provider.time.sleep", lambda *_: None)
    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = _api_status_error(500)
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "c", max_retries=3)
        with pytest.raises(ImageProviderError):
            provider.generate("prompt", tmp_path / "out.png")
    assert gen_mock.call_count == 3
