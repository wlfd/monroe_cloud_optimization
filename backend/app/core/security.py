import hashlib
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from app.core.config import settings

password_hash_ctx = PasswordHash.recommended()


def create_access_token(data: dict) -> str:
    """Issue short-lived access token (1 hour). Stored in React memory only."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {**data, "exp": expire, "jti": str(uuid.uuid4()), "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """Issue long-lived refresh token (7 days). Stored in HttpOnly cookie only — never in JS."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {**data, "exp": expire, "jti": str(uuid.uuid4()), "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises InvalidTokenError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash_ctx.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return password_hash_ctx.hash(password)


def hash_token(token: str) -> str:
    """SHA-256 hash of a refresh token for storage in user_sessions.token_hash."""
    return hashlib.sha256(token.encode()).hexdigest()
