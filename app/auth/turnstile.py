"""Verificacao Cloudflare Turnstile (anti-bot no cadastro).

Graceful: sem TURNSTILE_SECRET_KEY configurado, verify_turnstile() retorna True
(desabilitado) — o cadastro funciona normalmente. Para ativar, plugue as keys do
painel Cloudflare (Turnstile): TURNSTILE_SECRET_KEY (backend) e
NEXT_PUBLIC_TURNSTILE_SITE_KEY (frontend, baked no build).

Complementa [[disposable]] e o rate-limit por IP real ([[ratelimit]]) — a barreira
anti-farming de creditos ja e o email_verified (debito exige verificacao).
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str | None, remoteip: str | None = None, bypass_header: str | None = None) -> bool:
    """Valida um token Turnstile.

    Retorna True se o captcha esta desabilitado (sem secret) OU se o token e valido.
    Fail-closed quando ativo: token ausente/invalido/erro de rede -> False (nao deixa
    passar sob ataque). ponytail: fail-closed acopla o cadastro a disponibilidade do CF;
    aceitavel porque so liga quando o Gui pluga o secret.

    Bypass de teste: se READINESS_BYPASS_SECRET estiver configurado E o header
    `X-Readiness-Bypass` recebido bater com ele, pula o Turnstile. Uso exclusivo do
    validate_readiness.py / testes E2E internos — nunca habilitar em prod exposta sem
    necessidade (mesmo sendo seguro: requer segredo compartilhado).
    """
    if settings.READINESS_BYPASS_SECRET and bypass_header and bypass_header == settings.READINESS_BYPASS_SECRET:
        return True  # bypass explicito e autenticado (gate de go-live / testes internos)
    if not settings.TURNSTILE_SECRET_KEY:
        return True  # desabilitado -> no-op gracioso
    if not token:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remoteip:
        data["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_VERIFY_URL, data=data)
        return bool(resp.json().get("success"))
    except Exception as e:  # noqa: BLE001 — falha de rede vira reprovacao (fail-closed)
        logger.warning("Turnstile verify falhou: %s", e)
        return False
