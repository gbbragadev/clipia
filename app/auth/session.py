import secrets

from fastapi import HTTPException, Request, Response, status

from app.config import settings

AUTH_COOKIE_NAME = "clipia_session"
CSRF_COOKIE_NAME = "clipia_csrf"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(response: Response, *, access_token: str, csrf_token: str) -> None:
    secure = settings.ENVIRONMENT == "production"
    max_age = settings.JWT_EXPIRE_MINUTES * 60
    common = {
        "max_age": max_age,
        "path": "/",
        "secure": secure,
        "samesite": "lax",
    }
    # Host-only cookies intentionally omit Domain. The Next reverse proxy keeps
    # /api same-origin, so sibling subdomains cannot broaden the session scope.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.set_cookie(AUTH_COOKIE_NAME, access_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, **common)


def clear_auth_cookies(response: Response) -> None:
    secure = settings.ENVIRONMENT == "production"
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def validate_cookie_csrf(request: Request, claims: dict) -> None:
    if request.method.upper() in _SAFE_METHODS:
        return

    csrf_claim = claims.get("csrf")
    submitted = request.headers.get("X-CSRF-Token")
    if not csrf_claim or not submitted or not secrets.compare_digest(str(csrf_claim), submitted):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_validation_failed")

    origin = request.headers.get("Origin")
    if not origin:
        return
    allowed = {value.strip().rstrip("/") for value in settings.CORS_ORIGINS.split(",") if value.strip()}
    if "*" not in allowed and origin.rstrip("/") not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_origin_invalid")
