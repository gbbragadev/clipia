import json

import pytest
from pydantic import ValidationError

from app.models import EditRequest, GenerateRequest
from app.services import music, remotion


@pytest.mark.parametrize(
    "malicious_id",
    [
        "../secrets",
        "file:///etc/passwd",
        r"\\server\share\song.mp3",
        "http://127.0.0.1:8005/private",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/internal",
    ],
)
def test_music_asset_resolver_rejects_paths_urls_and_private_origins(tmp_path, monkeypatch, malicious_id):
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)

    with pytest.raises(ValueError, match="asset"):
        music.resolve_music_asset_path(malicious_id)


def test_music_asset_resolver_returns_only_contained_server_owned_file(tmp_path, monkeypatch):
    owned = tmp_path / "lofi-chill.mp3"
    owned.write_bytes(b"owned")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)

    assert music.resolve_music_asset_path("lofi-chill") == owned.resolve()


@pytest.mark.parametrize(
    "composition",
    [
        {"musicUrl": "http://127.0.0.1:8005/private"},
        {"musicAssetId": "../secrets"},
        {"voiceConfig": {"voiceId": "x", "voiceProvider": "edge", "rate": 0, "pitch": 0, "source_path": "C:/x"}},
        {"voiceConfig": {"voiceId": "x", "voiceProvider": "edge", "rate": 0, "pitch": 0, "voicePath": "file:///x"}},
        {"voiceConfig": {"voiceId": "file:///etc/passwd", "voiceProvider": "edge", "rate": 0, "pitch": 0}},
    ],
)
def test_editor_state_rejects_urls_paths_and_unknown_asset_ids(composition):
    with pytest.raises(ValidationError):
        EditRequest.model_validate({"editor_state": {"composition": composition}})


def test_generate_contract_rejects_legacy_custom_source_path():
    with pytest.raises(ValidationError):
        GenerateRequest.model_validate(
            {
                "topic": "Um tema valido para gerar video",
                "voice_provider": "custom",
                "voice_config": {"source_path": r"\\server\share\audio.wav"},
            }
        )


def test_generate_contract_rejects_source_path_even_for_supported_provider():
    with pytest.raises(ValidationError):
        GenerateRequest.model_validate(
            {
                "topic": "Um tema valido para gerar video",
                "voice_provider": "edge",
                "voice_config": {"source_path": "C:/Windows/system.ini"},
            }
        )


def test_generate_contract_requires_opaque_voice_id():
    with pytest.raises(ValidationError):
        GenerateRequest.model_validate(
            {
                "topic": "Um tema valido para gerar video",
                "voice_provider": "edge",
                "voice_config": {"voice_id": r"\\server\share\audio.wav"},
            }
        )


def test_remotion_drops_malicious_legacy_music_url(tmp_path, monkeypatch):
    job_dir = tmp_path / "jobs" / "job1"
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"title": "t", "scenes": []}))
    (job_dir / "words.json").write_text("[]")
    (job_dir / "editor_state.json").write_text(
        json.dumps({"composition": {"musicUrl": "http://169.254.169.254/latest/meta-data"}})
    )
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)

    props = remotion.build_composition_props("job1", default_music_asset_id="lofi-chill")

    assert props["musicAssetId"] == "lofi-chill"
    assert "musicUrl" not in props


def test_remotion_converts_only_allowlisted_legacy_music_url(tmp_path, monkeypatch):
    job_dir = tmp_path / "jobs" / "job1"
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"title": "t", "scenes": []}))
    (job_dir / "words.json").write_text("[]")
    (job_dir / "editor_state.json").write_text(json.dumps({"composition": {"musicUrl": "/music/happy-pop.mp3"}}))
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)

    props = remotion.build_composition_props("job1", default_music_asset_id="lofi-chill")

    assert props["musicAssetId"] == "happy-pop"
    assert "musicUrl" not in props
