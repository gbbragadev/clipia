import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, *, csrf_token: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "purpose": "access", "exp": expire}
    if csrf_token is not None:
        payload["csrf"] = csrf_token
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_reset_token(user_id: str, jti: uuid.UUID, issued_at: datetime | None = None) -> str:
    issued_at = issued_at or datetime.now(timezone.utc)
    expire = issued_at + timedelta(minutes=10)
    payload = {
        "sub": user_id,
        "purpose": "reset",
        "jti": str(jti),
        "iat": issued_at,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token_claims(token: str) -> dict | None:
    """Return validated access claims while accepting phase-one legacy JWTs.

    Tokens minted before the cookie rollout did not include ``purpose``. They
    remain valid during the Bearer compatibility release, while reset tokens
    are rejected explicitly and can never authenticate an API request.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") not in {None, "access"} or not payload.get("sub"):
            return None
        uuid.UUID(str(payload["sub"]))
        return payload
    except (JWTError, TypeError, ValueError):
        return None


def decode_access_token(token: str) -> str | None:
    """Returns user_id or None if invalid, expired, or not an access token."""
    payload = decode_access_token_claims(token)
    return payload.get("sub") if payload else None


def decode_reset_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") != "reset" or not payload.get("sub"):
            return None
        jti = uuid.UUID(str(payload.get("jti")))
        if jti.version != 4:
            return None
        return payload
    except (JWTError, TypeError, ValueError):
        return None
