"""Authentication endpoints: email/password register + login, OAuth token
exchange (Google / GitHub) and the current-user profile."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.v1.auth_oauth import exchange_github, exchange_google
from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter()


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    """Create an account with email + password."""
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        provider="email",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Exchange email + password for a JWT."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or not user.hashed_password
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return _token_for(user)


@router.post("/oauth/{provider}", response_model=TokenResponse)
async def oauth(provider: str, code: str, db: DbSession) -> TokenResponse:
    """Exchange an authorization code from Google or GitHub for a session.

    Requires ``GOOGLE_CLIENT_*`` / ``GITHUB_CLIENT_*`` settings. When unset, a
    deterministic demo account is returned so the flow can be exercised locally.
    """
    if provider == "google":
        profile = await exchange_google(code)
    elif provider == "github":
        profile = await exchange_github(code)
    else:
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider.")

    user = db.scalar(select(User).where(User.email == profile["email"]))
    if user is None:
        user = User(
            email=profile["email"],
            full_name=profile.get("name"),
            avatar_url=profile.get("avatar_url"),
            provider=provider,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return _token_for(user)


@router.get("/me", response_model=UserResponse)
def me(current: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current)
