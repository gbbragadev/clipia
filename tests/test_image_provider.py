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
