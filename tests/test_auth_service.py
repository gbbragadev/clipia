from app.auth.service import hash_password, verify_password, create_access_token, decode_access_token


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
