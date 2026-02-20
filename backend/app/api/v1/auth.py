from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_token,
    hash_token,
)
from app.core.config import settings
from app.models.user import User, UserSession
from app.schemas.user import TokenResponse, UserProfile
from jwt.exceptions import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    AUTH-01: Email + password login returning JWT access token.
    AUTH-02: Sets HttpOnly refresh token cookie (7-day, SameSite=Lax).
    API-02: Access token is a JWT Bearer token.
    """
    # Look up user by email (OAuth2PasswordRequestForm uses 'username' field for email)
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Issue tokens
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Store hashed refresh token in user_sessions (AUTH-02)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Set refresh token in HttpOnly cookie — never touches JavaScript (XSS protection)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=(settings.APP_ENV == "production"),  # HTTPS only in prod
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",  # Scoped to auth endpoints only
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    """
    AUTH-02: Rotate access token using the HttpOnly refresh token cookie.
    Issues a new access token; refresh token cookie is re-set with same expiry.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    if not refresh_token:
        raise credentials_error

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_error
        user_id: str = payload.get("sub")
    except InvalidTokenError:
        raise credentials_error

    # Verify session exists and is not revoked
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked == False,  # noqa: E712
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise credentials_error

    # Load user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_error

    # Issue new access token
    new_access_token = create_access_token({"sub": str(user.id), "role": user.role})

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
):
    """
    AUTH-03: Revoke current session. Sets revoked=true in user_sessions immediately.
    Clears the refresh token cookie.
    """
    if refresh_token:
        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.revoked == False,  # noqa: E712
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.revoked = True
            session.revoked_at = datetime.now(timezone.utc)
            await db.commit()

    # Clear the cookie
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    API-02: Returns current user profile. Requires valid JWT Bearer token.
    """
    return current_user
