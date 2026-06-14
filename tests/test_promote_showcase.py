"""Testes do script de promocao de videos para o showcase (scripts/promote_to_showcase.py)."""

import json
from pathlib import Path

import pytest

from scripts.promote_to_showcase import promote_video, slugify


def test_slugify_removes_accents_punctuation_and_lowercases():
    assert slugify("5 Curiosidades sobre o Oceano!") == "5-curiosidades-sobre-o-oceano"
    assert slugify("Mensagem de Fé & Esperança") == "mensagem-de-fe-esperanca"
    assert slugify("   ") == "video"


def _seed(tmp_path: Path, job_id: str = "abc123") -> dict:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    storage_showcase = tmp_path / "storage_showcase"
    public_showcase = tmp_path / "public_showcase"
    public_showcase.mkdir()
    manifest_path = public_showcase / "showcase.json"
    manifest_path.write_text(
        json.dumps({"niches": [{"id": "curiosidades", "label": "Curiosidades", "icon": "🧠"}], "videos": []}),
        encoding="utf-8",
    )
    (output_dir / f"{job_id}.mp4").write_bytes(b"FAKE-MP4-DATA")
    return {
        "output_dir": output_dir,
        "showcase_storage_dir": storage_showcase,
        "public_showcase_dir": public_showcase,
        "manifest_path": manifest_path,
    }


def test_promote_copies_to_storage_and_prepends_manifest(tmp_path):
    paths = _seed(tmp_path)
    entry = promote_video("abc123", "curiosidades", "Fatos sobre o oceano", **paths)

    # copiou para storage/showcase (galeria, nao-hero) com o slug do titulo
    assert (paths["showcase_storage_dir"] / "fatos-sobre-o-oceano.mp4").read_bytes() == b"FAKE-MP4-DATA"
    assert entry["video"] == "/storage/showcase/fatos-sobre-o-oceano.mp4"
    assert "hero" not in entry

    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    assert manifest["videos"][0]["niche"] == "curiosidades"
    assert manifest["videos"][0]["video"] == "/storage/showcase/fatos-sobre-o-oceano.mp4"
    assert manifest["videos"][0]["title"] == "Fatos sobre o oceano"


def test_promote_hero_goes_to_public_showcase(tmp_path):
    paths = _seed(tmp_path)
    entry = promote_video("abc123", "curiosidades", "Top hero", hero=True, **paths)

    assert (paths["public_showcase_dir"] / "top-hero.mp4").exists()
    assert entry["video"] == "/showcase/top-hero.mp4"
    assert entry["hero"] is True


def test_promote_is_idempotent_on_same_title(tmp_path):
    paths = _seed(tmp_path)
    promote_video("abc123", "curiosidades", "Mesmo titulo", **paths)
    promote_video("abc123", "curiosidades", "Mesmo titulo", **paths)
    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    # nao duplica a entrada (mesmo id derivado do slug)
    assert len(manifest["videos"]) == 1


def test_promote_optional_fields(tmp_path):
    paths = _seed(tmp_path)
    entry = promote_video(
        "abc123",
        "curiosidades",
        "Com extras",
        phrase="frase de impacto",
        before_script="primeira linha",
        caption_style="impact",
        **paths,
    )
    assert entry["phrase"] == "frase de impacto"
    assert entry["beforeScript"] == "primeira linha"
    assert entry["captionStyle"] == "impact"


def test_promote_missing_source_raises(tmp_path):
    paths = _seed(tmp_path, job_id="abc123")
    with pytest.raises(FileNotFoundError):
        promote_video("inexistente", "curiosidades", "X", **paths)
