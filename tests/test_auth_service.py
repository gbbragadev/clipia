import base64
import json
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth.service import create_access_token, decode_access_token, hash_password, verify_password
from app.config import settings


def test_password_hash_and_verify():
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert verify_password("mysecretpassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_jwt_create_and_decode():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    decoded = decode_access_token(token)
    assert decoded == user_id


def test_jwt_invalid_token():
    assert decode_access_token("invalid.token.here") is None


def test_jwt_wrong_secret_returns_none():
    token = jwt.encode(
        {"sub": "550e8400-e29b-41d4-a716-446655440000", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_jwt_without_subject_returns_none():
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_jwt_with_non_uuid_subject_returns_none():
    token = jwt.encode(
        {
            "sub": "not-a-user-id",
            "purpose": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_jwt_alg_none_is_rejected():
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "abc"}).encode()).rstrip(b"=").decode()
    token = f"{header}.{payload}."
    assert decode_access_token(token) is None
