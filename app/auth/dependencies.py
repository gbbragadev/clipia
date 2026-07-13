from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token_claims
from app.auth.session import AUTH_COOKIE_NAME, validate_cookie_csrf
from app.db.engine import get_db
from app.db.models import User

optional_security = HTTPBearer(auto_error=False)


def _resolve_access_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[dict, str] | None:
    authorization = request.headers.get("Authorization")
    if authorization is not None:
        # Never fall back to a valid cookie when an explicit Authorization
        # header is malformed or invalid. Bearer remains phase-one precedence.
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado")
        claims = decode_access_token_claims(credentials.credentials)
        transport = "bearer"
    else:
        cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
        if cookie_token is None:
            return None
        claims = decode_access_token_claims(cookie_token)
        transport = "cookie"

    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado")
    if transport == "cookie":
        validate_cookie_csrf(request, claims)
    request.state.auth_transport = transport
    return claims, transport


async def _load_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.plan == "deleted":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario nao encontrado")
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> User:
    resolved = _resolve_access_claims(request, credentials)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autenticado")
    claims, transport = resolved
    from app.observability import record_auth_transport

    record_auth_transport(transport)
    return await _load_user(db, str(claims["sub"]))


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.plan != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return user


async def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return no user for absent auth, but fail closed for presented bad auth."""
    resolved = _resolve_access_claims(request, credentials)
    if resolved is None:
        return None
    claims, transport = resolved
    from app.observability import record_auth_transport

    record_auth_transport(transport)
    return await _load_user(db, str(claims["sub"]))
