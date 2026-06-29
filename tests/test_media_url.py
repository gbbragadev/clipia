from urllib.parse import parse_qs, urlparse

import pytest

from app.utils.media_url import sign_media_url, verify_media_sig


def test_sign_verify_roundtrip():
    signed = sign_media_url("/storage/jobs/j1/media/scene_0.mp4")
    assert "exp=" in signed and "sig=" in signed
    parsed = urlparse(signed)
    q = parse_qs(parsed.query)
    assert verify_media_sig(parsed.path, q["exp"][0], q["sig"][0]) is True


def test_sign_preserves_absolute_url():
    signed = sign_media_url("https://clipia.com.br/storage/jobs/j1/narration.wav")
    assert signed.startswith("https://clipia.com.br/storage/jobs/j1/narration.wav?")
    parsed = urlparse(signed)
    q = parse_qs(parsed.query)
    # o path assinado e relativo (sem host), igual ao que o middleware ve
    assert verify_media_sig("/storage/jobs/j1/narration.wav", q["exp"][0], q["sig"][0]) is True


def test_non_private_url_not_signed():
    assert sign_media_url("/storage/showcase/x.mp4") == "/storage/showcase/x.mp4"


def test_tampered_path_fails():
    signed = sign_media_url("/storage/jobs/j1/narration.wav")
    q = parse_qs(urlparse(signed).query)
    assert verify_media_sig("/storage/jobs/OUTRO/narration.wav", q["exp"][0], q["sig"][0]) is False


def test_missing_params_fail():
    assert verify_media_sig("/storage/jobs/j1/narration.wav", None, None) is False
    assert verify_media_sig("/storage/jobs/j1/narration.wav", "abc", "def") is False


def test_expired_signature_fails():
    # exp no passado, assinado corretamente -> rejeitado por expiracao
    from app.utils.media_url import _sign

    path = "/storage/jobs/j1/narration.wav"
    past = 1
    assert verify_media_sig(path, str(past), _sign(path, past)) is False


@pytest.mark.asyncio
async def test_private_media_requires_signature(client):
    r = await client.get("/storage/jobs/abc/narration.wav")
    assert r.status_code == 403, "Midia privada sem assinatura deve ser barrada."


@pytest.mark.asyncio
async def test_private_media_with_valid_signature_passes_guard(client):
    signed = sign_media_url("/storage/jobs/abc/narration.wav")
    r = await client.get(signed)
    assert r.status_code != 403, "Assinatura valida deve passar o guard (404 por arquivo ausente, nao 403)."


@pytest.mark.asyncio
async def test_public_showcase_needs_no_signature(client):
    r = await client.get("/storage/showcase/qualquer.mp4")
    assert r.status_code != 403, "Galeria publica nao deve exigir assinatura."
