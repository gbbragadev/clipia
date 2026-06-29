"""Assinatura HMAC de URLs de midia privada (/storage/jobs/*).

O editor consome <video src>/<audio src> direto, sem header Authorization, entao a
midia intermediaria do usuario e protegida por assinatura na query (?exp&sig) em vez
de auth por token. O backend monta as URLs ja assinadas (composition, regenerate-tts,
render via [[remotion]]); o middleware em app.main as valida e devolve 403 sem assinatura.

A galeria publica (/storage/showcase) e o download do MP4 final (/jobs/{id}/download,
autenticado) NAO passam por aqui.

ponytail: TTL longo (7 dias) porque o editor/render seguram a URL durante a sessao; o
ganho sobre o UUID nao-enumeravel e barrar acesso de quem nunca recebeu a URL do backend.
Para revogacao imediata seria preciso TTL curto + re-assinatura no client (nao vale a pena hoje).
"""

import hashlib
import hmac
import time

from app.config import settings

_TTL_SECONDS = 7 * 24 * 3600  # 7 dias
PRIVATE_PREFIX = "/storage/jobs/"


def _sign(path: str, exp: int) -> str:
    msg = f"{path}:{exp}".encode()
    return hmac.new(settings.JWT_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]


def sign_media_url(url: str) -> str:
    """Anexa ?exp&sig a uma URL/path de /storage/jobs/*. Outras URLs voltam intactas."""
    idx = url.find(PRIVATE_PREFIX)
    if idx == -1:
        return url  # nao e midia privada -> nao assina
    path_only = url[idx:]
    exp = int(time.time()) + _TTL_SECONDS
    sig = _sign(path_only, exp)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}exp={exp}&sig={sig}"


def verify_media_sig(path: str, exp: str | None, sig: str | None) -> bool:
    """Valida a assinatura de um path /storage/jobs/*. False se ausente/expirada/adulterada."""
    if not exp or not sig:
        return False
    try:
        exp_i = int(exp)
    except ValueError:
        return False
    if exp_i < int(time.time()):
        return False
    return hmac.compare_digest(_sign(path, exp_i), sig)
