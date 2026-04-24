from unittest.mock import patch


def test_static_image_uses_loop_and_zoompan(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = str(tmp_path / "clip.mp4")

    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, out, scene_index=0)

    cmd = run.call_args.args[0]
    assert "-loop" in cmd
    loop_idx = cmd.index("-loop")
    assert cmd[loop_idx + 1] == "1"
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf
    assert "scale=1080:1920" in vf
    assert "crop=1080:1920" in vf


def test_static_image_zooms_in_on_even_index(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=0)
    cmd = run.call_args.args[0]
    vf_even = cmd[cmd.index("-vf") + 1]

    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=1)
    cmd = run.call_args.args[0]
    vf_odd = cmd[cmd.index("-vf") + 1]

    assert "min(zoom" in vf_even  # zoom in: z starts small, grows
    assert "max(1.15" in vf_odd  # zoom out: z starts 1.15, shrinks


def test_prepare_scene_routes_png_to_static_image(tmp_path):
    from app.services import compositor

    img = tmp_path / "scene.png"
    img.write_bytes(b"\x89PNG")
    out = str(tmp_path / "out.mp4")

    with (
        patch("app.services.compositor._prepare_static_image") as static,
        patch("app.services.compositor._prepare_video_scene") as video,
    ):
        compositor._prepare_scene(str(img), 5.0, out, scene_index=2)

    static.assert_called_once()
    video.assert_not_called()
    # scene_index was passed through (either positionally or as kwarg)
    assert static.call_args.kwargs.get("scene_index") == 2 or (
        len(static.call_args.args) >= 4 and static.call_args.args[3] == 2
    )


def test_prepare_scene_routes_mp4_to_video_scene(tmp_path):
    from app.services import compositor

    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00")
    out = str(tmp_path / "out.mp4")

    with (
        patch("app.services.compositor._prepare_static_image") as static,
        patch("app.services.compositor._prepare_video_scene") as video,
    ):
        compositor._prepare_scene(str(mp4), 5.0, out, scene_index=0)

    video.assert_called_once()
    static.assert_not_called()
