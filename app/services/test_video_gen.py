"""Check offline do provider de video IA — body do request + classificacao de status.
A geracao real custa $; o smoke ao vivo fica fora do teste automatizado."""

from app.services.video_gen_provider import build_submit_body, classify_status


def test_build_submit_body():
    b = build_submit_body(
        "um gato astronauta", 5, model="bytedance/seedance-2.0-fast", resolution="720p", aspect_ratio="9:16"
    )
    assert b["model"] == "bytedance/seedance-2.0-fast"
    assert b["prompt"] == "um gato astronauta"
    assert b["duration"] == 5
    assert b["aspect_ratio"] == "9:16"
    assert b["generate_audio"] is False  # ClipIA usa TTS proprio


def test_classify_status():
    assert classify_status("completed") == "done"
    assert classify_status("SUCCEEDED") == "done"
    assert classify_status("failed") == "failed"
    assert classify_status("expired") == "failed"
    assert classify_status("cancelled") == "failed"
    assert classify_status("processing") == "pending"
    assert classify_status("queued") == "pending"
    assert classify_status("") == "pending"


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
