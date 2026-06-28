from app.services import music


def test_resolve_music_path_returns_path_when_file_exists(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") == str(tmp_path / "inspirational.mp3")


def test_resolve_music_path_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") is None


def test_auto_music_url_uses_mood(tmp_path, monkeypatch):
    (tmp_path / "lofi-chill.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.auto_music_url("dialogue_duo") == "/music/lofi-chill.mp3"


def test_resolve_auto_music_respects_global_flag(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", False)
    assert music.resolve_auto_music("stock_narration") is None
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", True)
    assert music.resolve_auto_music("stock_narration") == str(tmp_path / "inspirational.mp3")
