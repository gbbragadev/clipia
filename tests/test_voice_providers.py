from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.custom_audio_provider import (
    MAX_DURATION_SECONDS,
    MAX_FILE_SIZE_BYTES,
    CustomAudioProvider,
    normalize_audio,
    validate_audio_file,
)
from app.services.edge_provider import EDGE_VOICES, EdgeTTSProvider
from app.services.elevenlabs_provider import _VOICES_CACHE_KEY, ElevenLabsProvider, _get_client
from app.services.voice_provider import get_voice_provider


class FakeRedisClient:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []
        self.set_calls: list[tuple[str, str, int | None]] = []

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        self.set_calls.append((key, value, ex))

    def delete(self, key: str):
        self.deleted.append(key)
        self.values.pop(key, None)


@pytest.mark.asyncio
async def test_edge_list_voices():
    provider = EdgeTTSProvider()
    voices = await provider.list_voices()

    assert voices == EDGE_VOICES
    assert [voice.name for voice in voices] == ["Antonio", "Francisca", "Thalita"]


def test_edge_estimate_cost():
    assert EdgeTTSProvider().estimate_cost("texto") == 1


@pytest.mark.asyncio
async def test_edge_synthesize(tmp_path):
    output_path = tmp_path / "edge.wav"
    provider = EdgeTTSProvider()

    with patch("app.services.edge_provider.edge_tts.Communicate") as mock_comm:
        instance = MagicMock()
        instance.save = AsyncMock(side_effect=lambda path: Path(path).write_bytes(b"edge"))
        mock_comm.return_value = instance

        result = await provider.synthesize(
            text="Narracao de teste",
            output_path=str(output_path),
            voice_id="pt-BR-AntonioNeural",
            rate=-5,
            pitch=2,
        )

    assert result == output_path
    mock_comm.assert_called_once_with(
        "Narracao de teste",
        "pt-BR-AntonioNeural",
        rate="-5%",
        pitch="+2Hz",
    )
    instance.save.assert_awaited_once_with(str(output_path))


@pytest.mark.asyncio
async def test_edge_synthesize_with_duration_target(tmp_path):
    output_path = tmp_path / "edge-fit.wav"
    provider = EdgeTTSProvider()

    with (
        patch("app.services.edge_provider.edge_tts.Communicate") as mock_comm,
        patch("app.services.edge_provider._fit_to_duration") as mock_fit,
    ):
        instance = MagicMock()
        instance.save = AsyncMock(side_effect=lambda path: Path(path).write_bytes(b"edge"))
        mock_comm.return_value = instance

        await provider.synthesize(
            text="Narracao de teste",
            output_path=str(output_path),
            duration_target=12,
        )

    mock_fit.assert_called_once_with(str(output_path), 12)


def test_edge_provider_name():
    assert EdgeTTSProvider().provider_name == "edge"


@pytest.mark.asyncio
async def test_elevenlabs_list_voices_cached():
    provider = ElevenLabsProvider()
    redis_client = FakeRedisClient()
    redis_client.values[_VOICES_CACHE_KEY] = (
        '[{"id":"voice_1","name":"Cached Voice","provider":"elevenlabs","language":"multilingual","gender":"female","preview_url":null,"is_clone":false}]'
    )

    with (
        patch("app.services.elevenlabs_provider.get_redis", return_value=redis_client),
        patch("app.services.elevenlabs_provider._get_client") as mock_client,
    ):
        voices = await provider.list_voices()

    assert len(voices) == 1
    assert voices[0].id == "voice_1"
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_elevenlabs_list_voices_uncached():
    provider = ElevenLabsProvider()
    redis_client = FakeRedisClient()
    response = SimpleNamespace(
        voices=[
            SimpleNamespace(
                voice_id="voice_2",
                name="Premium Voice",
                labels={"gender": "male"},
                preview_url="https://preview",
                category="cloned",
            )
        ]
    )
    client = MagicMock()
    client.voices.get_all.return_value = response

    with (
        patch("app.services.elevenlabs_provider.get_redis", return_value=redis_client),
        patch("app.services.elevenlabs_provider._get_client", return_value=client),
    ):
        voices = await provider.list_voices()

    assert len(voices) == 1
    assert voices[0].id == "voice_2"
    assert voices[0].is_clone is True
    assert redis_client.set_calls[0][0] == _VOICES_CACHE_KEY


def test_elevenlabs_estimate_cost():
    assert ElevenLabsProvider().estimate_cost("texto") == 2


@pytest.mark.asyncio
async def test_elevenlabs_synthesize(tmp_path):
    provider = ElevenLabsProvider()
    output_path = tmp_path / "premium.wav"
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter([b"pcm-audio"])

    def fake_run(_args, **_kwargs):
        output_path.write_bytes(b"wav-audio")
        return MagicMock(returncode=0)

    with (
        patch("app.services.elevenlabs_provider._get_client", return_value=client),
        patch("subprocess.run", side_effect=fake_run),
    ):
        result = await provider.synthesize(
            text="Texto premium",
            output_path=str(output_path),
            voice_id="el_voice_1",
            model_id="eleven_multilingual_v2",
        )

    assert result == output_path
    client.text_to_speech.convert.assert_called_once_with(
        voice_id="el_voice_1",
        text="Texto premium",
        model_id="eleven_multilingual_v2",
        output_format="pcm_24000",
        language_code="pt",
    )


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_creates_wav(tmp_path):
    provider = ElevenLabsProvider()
    output_path = tmp_path / "premium.wav"
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter([b"pcm-audio"])

    def fake_run(args, **_kwargs):
        assert args[:8] == [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            "24000",
            "-ac",
            "1",
        ]
        output_path.write_bytes(b"wav-audio")
        return MagicMock(returncode=0)

    with (
        patch("app.services.elevenlabs_provider._get_client", return_value=client),
        patch("subprocess.run", side_effect=fake_run) as mock_run,
    ):
        await provider.synthesize(
            text="Texto premium",
            output_path=str(output_path),
            voice_id="el_voice_2",
        )

    assert mock_run.call_count == 1
    assert output_path.exists()


@pytest.mark.asyncio
async def test_elevenlabs_clone_voice():
    provider = ElevenLabsProvider()
    redis_client = FakeRedisClient()
    client = MagicMock()
    client.voices.ivc.create.return_value = SimpleNamespace(voice_id="clone_123")

    with (
        patch("app.services.elevenlabs_provider._get_client", return_value=client),
        patch("app.services.elevenlabs_provider.get_redis", return_value=redis_client),
    ):
        voice_id = await provider.clone_voice("Minha voz", [b"sample"], "descricao")

    assert voice_id == "clone_123"
    assert redis_client.deleted == [_VOICES_CACHE_KEY]


@pytest.mark.asyncio
async def test_elevenlabs_delete_voice():
    provider = ElevenLabsProvider()
    redis_client = FakeRedisClient()
    client = MagicMock()

    with (
        patch("app.services.elevenlabs_provider._get_client", return_value=client),
        patch("app.services.elevenlabs_provider.get_redis", return_value=redis_client),
    ):
        await provider.delete_voice("clone_123")

    client.voices.delete.assert_called_once_with(voice_id="clone_123")
    assert redis_client.deleted == [_VOICES_CACHE_KEY]


def test_elevenlabs_no_api_key_raises(monkeypatch):
    monkeypatch.setattr("app.services.elevenlabs_provider.settings.ELEVENLABS_API_KEY", "")

    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY not configured"):
        _get_client()


def test_custom_estimate_cost():
    assert CustomAudioProvider().estimate_cost("texto") == 1


@pytest.mark.asyncio
async def test_custom_list_voices():
    voices = await CustomAudioProvider().list_voices()

    assert len(voices) == 1
    assert voices[0].id == "custom_upload"


def test_validate_audio_too_short(tmp_path):
    audio_path = tmp_path / "short.wav"
    audio_path.write_bytes(b"tiny")

    with patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout='{"format":{"duration":"4.9","format_name":"wav"}}'),
    ):
        with pytest.raises(ValueError, match="muito curto"):
            validate_audio_file(str(audio_path))


def test_validate_audio_too_long(tmp_path):
    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"long")

    with patch(
        "subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout=f'{{"format":{{"duration":"{MAX_DURATION_SECONDS + 0.1}","format_name":"wav"}}}}',
        ),
    ):
        with pytest.raises(ValueError, match="muito longo"):
            validate_audio_file(str(audio_path))


def test_validate_audio_too_large(tmp_path):
    audio_path = tmp_path / "large.wav"
    audio_path.write_bytes(b"x")

    with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=MAX_FILE_SIZE_BYTES + 1)):
        with pytest.raises(ValueError, match="Arquivo muito grande"):
            validate_audio_file(str(audio_path))


def test_normalize_audio(tmp_path):
    input_path = tmp_path / "input.mp3"
    output_path = tmp_path / "output.wav"
    input_path.write_bytes(b"audio")

    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        normalize_audio(str(input_path), str(output_path))

    args = mock_run.call_args.args[0]
    assert args[:2] == ["ffmpeg", "-y"]
    assert "-ar" in args and args[args.index("-ar") + 1] == "24000"
    assert "-ac" in args and args[args.index("-ac") + 1] == "1"
    assert "-c:a" in args and args[args.index("-c:a") + 1] == "pcm_s16le"


def test_get_voice_provider_edge():
    assert isinstance(get_voice_provider("edge"), EdgeTTSProvider)


def test_get_voice_provider_elevenlabs():
    assert isinstance(get_voice_provider("elevenlabs"), ElevenLabsProvider)


def test_get_voice_provider_custom():
    assert isinstance(get_voice_provider("custom"), CustomAudioProvider)


def test_get_voice_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown voice provider"):
        get_voice_provider("unknown")
