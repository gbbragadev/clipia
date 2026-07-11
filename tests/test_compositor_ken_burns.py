import json
import shutil
import subprocess
import time
from unittest.mock import patch

import pytest

_HAS_FFMPEG = bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))


def _mocked_run():
    """Patch subprocess.run no compositor com returncode=0 (o helper _run valida)."""
    patcher = patch("app.services.compositor.subprocess.run")
    run = patcher.start()
    run.return_value.returncode = 0
    return patcher, run


def test_static_image_uses_loop_and_zoompan(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = str(tmp_path / "clip.mp4")

    patcher, run = _mocked_run()
    try:
        _prepare_static_image(str(img), 5.0, out, scene_index=0)
    finally:
        patcher.stop()

    cmd = run.call_args.args[0]
    assert "-loop" in cmd
    loop_idx = cmd.index("-loop")
    assert cmd[loop_idx + 1] == "1"
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf
    assert "scale=1080:1920" in vf
    assert "crop=1080:1920" in vf


def test_static_image_limits_output_frames_not_input(tmp_path):
    """Regressão do bug de 3h39: -t de INPUT fazia zoompan emitir d frames por frame
    de entrada (duration*fps ao quadrado); a saída deve ser limitada por -frames:v."""
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    patcher, run = _mocked_run()
    try:
        _prepare_static_image(str(img), 12.0, str(tmp_path / "o.mp4"), scene_index=0)
    finally:
        patcher.stop()

    cmd = run.call_args.args[0]
    assert "-t" not in cmd  # nada de limitar o INPUT: era a causa dos 90k frames/cena
    assert "-frames:v" in cmd
    assert cmd[cmd.index("-frames:v") + 1] == "300"  # 12s * 25fps
    assert "veryfast" in cmd  # clip intermediario: encode rapido, qualidade no final


def test_static_image_zooms_in_on_even_index(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    patcher, run = _mocked_run()
    try:
        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=0)
        cmd = run.call_args.args[0]
        vf_even = cmd[cmd.index("-vf") + 1]

        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=1)
        cmd = run.call_args.args[0]
        vf_odd = cmd[cmd.index("-vf") + 1]
    finally:
        patcher.stop()

    assert "min(zoom" in vf_even  # zoom in: z starts small, grows
    assert "max(1.15" in vf_odd  # zoom out: z starts 1.15, shrinks


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe indisponiveis no PATH")
def test_static_image_real_encode_is_bounded(tmp_path):
    """Prova com FFmpeg real: clip de 3s tem exatamente 75 frames e encoda em
    segundos (o comando bugado gerava 5625 frames = ~4min de video por cena)."""
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "scene.png"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=steelblue:s=540x960", "-frames:v", "1", str(img)],
        capture_output=True,
        check=True,
        timeout=30,
    )
    out = tmp_path / "clip.mp4"

    t0 = time.monotonic()
    _prepare_static_image(str(img), 3.0, str(out), scene_index=0)
    elapsed = time.monotonic() - t0

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(out)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(probe.stdout)
    duration = float(data["format"]["duration"])
    nb_frames = int(data["streams"][0]["nb_frames"])

    assert abs(duration - 3.0) < 0.3, f"clip deveria ter ~3s, tem {duration:.2f}s"
    assert nb_frames == 75, f"3s a 25fps deveria ter 75 frames, tem {nb_frames}"
    assert elapsed < 30, f"encode de 3s deveria levar segundos, levou {elapsed:.0f}s"


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
