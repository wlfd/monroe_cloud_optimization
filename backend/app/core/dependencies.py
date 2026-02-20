from typing import AsyncGenerator
from fastapi import Depends, Cookie
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.core.exceptions import CredentialsException
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates JWT Bearer token on protected routes.
    FastAPI auto-includes this in OpenAPI security schema (API-02).
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise CredentialsException()
        user_id: str = payload.get("sub")
        if user_id is None:
            raise CredentialsException()
    except InvalidTokenError:
        raise CredentialsException()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise CredentialsException()
    return user
