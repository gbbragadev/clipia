"""Testes offline do catalogo drive_library (mocka rclone; sem rede/GPU)."""

from pathlib import Path

import app.services.drive_library as dl


class _FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_index_folder_filters_mp4_and_counts_recursively(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "_DB_PATH", tmp_path / "idx.db")
    # rclone recursivo retorna caminhos com subpastas; so .mp4 entram
    monkeypatch.setattr(
        dl,
        "_rclone",
        lambda *a: _FakeProc(stdout="clip1.mp4\nclip2.mp4\nlixo.txt\nsub/clip3.mp4\n"),
    )

    n = dl.index_folder("FID", "satisfying")
    assert n == 3  # recursivo pega sub/clip3.mp4; lixo.txt descartado
    assert dl.count_for_tag("satisfying") == 3
    assert dl.count_for_tag("cinematic") == 0


def test_pick_drive_clip_downloads_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "_DB_PATH", tmp_path / "idx.db")
    monkeypatch.setattr(dl, "_CACHE_DIR", tmp_path / "cache")

    # indexa 1 clip
    monkeypatch.setattr(
        dl,
        "_rclone",
        lambda *a: _FakeProc(stdout="VIDEO (1).mp4\n"),
    )
    assert dl.index_folder("FID", "satisfying") == 1

    # copy: cria o arquivo no destino
    def fake_copy(*args):
        dest = Path(args[-1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "VIDEO (1).mp4").write_bytes(b"x")
        return _FakeProc()

    monkeypatch.setattr(dl, "_rclone", fake_copy)

    p = dl.pick_drive_clip("satisfying")
    assert p is not None and p.exists()
    assert p.name == "VIDEO (1).mp4"

    # 2a chamada usa o cache (cached_path gravado) — nao baixa de novo
    def boom(*a):
        raise AssertionError("nao deveria baixar de novo")

    monkeypatch.setattr(dl, "_rclone", boom)
    p2 = dl.pick_drive_clip("satisfying")
    assert p2 == p


def test_pick_drive_clip_empty_tag_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "_DB_PATH", tmp_path / "idx.db")
    assert dl.pick_drive_clip("inexistente") is None
