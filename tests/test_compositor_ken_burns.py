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
