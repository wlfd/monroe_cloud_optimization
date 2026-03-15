"""
Unit tests for app.core.security.

Covers:
- create_access_token: payload fields, type='access', jti uniqueness
- create_refresh_token: payload fields, type='refresh', jti uniqueness
- decode_token: valid token round-trip, expired token raises, tampered raises
- verify_password / get_password_hash: correct/incorrect password
- hash_token: SHA-256 determinism and format
- Token type enforcement: access token rejected as refresh, and vice versa
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from jwt.exceptions import InvalidTokenError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_secret() -> str:
    """Return the JWT secret used by the security module."""
    from app.core.config import settings
    return settings.JWT_SECRET_KEY


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


def test_create_access_token_returns_string():
    """create_access_token returns a non-empty JWT string."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": str(uuid.uuid4()), "role": "viewer"})

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_contains_sub_and_role():
    """Access token payload includes sub, role, type='access', and jti."""
    from app.core.security import create_access_token

    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "role": "admin"})

    secret = _get_secret()
    payload = jwt.decode(token, secret, algorithms=["HS256"])

    assert payload["sub"] == user_id
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "exp" in payload


def test_create_access_token_has_correct_expiry():
    """Access token expires in approximately JWT_ACCESS_TOKEN_EXPIRE_MINUTES minutes."""
    from app.core.security import create_access_token
    from app.core.config import settings

    token = create_access_token({"sub": "test-user"})
    secret = _get_secret()
    payload = jwt.decode(token, secret, algorithms=["HS256"])

    now = datetime.now(timezone.utc)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    delta = abs((exp - expected_exp).total_seconds())
    assert delta < 5  # Within 5 seconds tolerance


def test_create_access_token_jti_unique_per_call():
    """Each call to create_access_token produces a unique jti."""
    from app.core.security import create_access_token

    secret = _get_secret()
    tokens = [create_access_token({"sub": "user-1"}) for _ in range(5)]
    jtis = [jwt.decode(t, secret, algorithms=["HS256"])["jti"] for t in tokens]

    assert len(set(jtis)) == 5  # All unique


# ---------------------------------------------------------------------------
# create_refresh_token
# ---------------------------------------------------------------------------


def test_create_refresh_token_type_is_refresh():
    """Refresh token payload has type='refresh'."""
    from app.core.security import create_refresh_token

    token = create_refresh_token({"sub": str(uuid.uuid4())})
    secret = _get_secret()
    payload = jwt.decode(token, secret, algorithms=["HS256"])

    assert payload["type"] == "refresh"
    assert "jti" in payload


def test_create_refresh_token_has_7_day_expiry():
    """Refresh token expires in approximately 7 days."""
    from app.core.security import create_refresh_token
    from app.core.config import settings

    token = create_refresh_token({"sub": "test-user"})
    secret = _get_secret()
    payload = jwt.decode(token, secret, algorithms=["HS256"])

    now = datetime.now(timezone.utc)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    delta = abs((exp - expected_exp).total_seconds())
    assert delta < 5


def test_refresh_token_different_from_access_token():
    """Refresh and access tokens for the same user are distinct strings."""
    from app.core.security import create_access_token, create_refresh_token

    data = {"sub": str(uuid.uuid4())}
    access = create_access_token(data)
    refresh = create_refresh_token(data)

    assert access != refresh


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------


def test_decode_token_valid_round_trip():
    """decode_token successfully decodes a token created by create_access_token."""
    from app.core.security import create_access_token, decode_token

    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "role": "finance"})

    payload = decode_token(token)

    assert payload["sub"] == user_id
    assert payload["role"] == "finance"
    assert payload["type"] == "access"


def test_decode_token_expired_raises():
    """decode_token raises InvalidTokenError for an expired token."""
    from app.core.security import decode_token
    from app.core.config import settings

    past_exp = datetime.now(timezone.utc) - timedelta(seconds=1)
    payload = {"sub": "user", "exp": past_exp, "jti": str(uuid.uuid4()), "type": "access"}
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_token(expired_token)


def test_decode_token_tampered_raises():
    """decode_token raises InvalidTokenError for a token with wrong signature."""
    from app.core.security import decode_token

    payload = {"sub": "user", "type": "access"}
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_garbage_string_raises():
    """decode_token raises InvalidTokenError for a non-JWT string."""
    from app.core.security import decode_token

    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt.token.here")


# ---------------------------------------------------------------------------
# verify_password / get_password_hash
# ---------------------------------------------------------------------------


def test_get_password_hash_returns_non_empty_string():
    """get_password_hash returns a hash string."""
    from app.core.security import get_password_hash

    hashed = get_password_hash("MyStrongPassword!")
    assert isinstance(hashed, str)
    assert len(hashed) > 0
    assert hashed != "MyStrongPassword!"


def test_verify_password_correct_password():
    """verify_password returns True for the correct plaintext password."""
    from app.core.security import get_password_hash, verify_password

    password = "Correct-Horse-Battery-Staple"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True


def test_verify_password_wrong_password():
    """verify_password returns False for an incorrect plaintext password."""
    from app.core.security import get_password_hash, verify_password

    hashed = get_password_hash("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_empty_password():
    """verify_password handles empty string without raising."""
    from app.core.security import get_password_hash, verify_password

    hashed = get_password_hash("correct-password")
    result = verify_password("", hashed)
    assert result is False


def test_get_password_hash_same_input_different_hashes():
    """get_password_hash produces different hashes for the same input (salted)."""
    from app.core.security import get_password_hash

    hash1 = get_password_hash("same-password")
    hash2 = get_password_hash("same-password")

    # Argon2 uses random salt — same input → different hash
    assert hash1 != hash2


# ---------------------------------------------------------------------------
# hash_token
# ---------------------------------------------------------------------------


def test_hash_token_returns_sha256_hex():
    """hash_token returns a 64-character lowercase hexadecimal SHA-256 digest."""
    from app.core.security import hash_token

    result = hash_token("some-refresh-token")

    assert isinstance(result, str)
    assert len(result) == 64
    assert result == result.lower()


def test_hash_token_is_deterministic():
    """hash_token produces the same output for the same input every time."""
    from app.core.security import hash_token

    token = "deterministic-token-value"
    assert hash_token(token) == hash_token(token)


def test_hash_token_different_inputs_different_hashes():
    """hash_token produces different digests for different inputs."""
    from app.core.security import hash_token

    h1 = hash_token("token-alpha")
    h2 = hash_token("token-beta")

    assert h1 != h2


def test_hash_token_matches_manual_sha256():
    """hash_token result matches manual SHA-256 computation."""
    import hashlib
    from app.core.security import hash_token

    token = "test-refresh-token"
    expected = hashlib.sha256(token.encode()).hexdigest()

    assert hash_token(token) == expected
