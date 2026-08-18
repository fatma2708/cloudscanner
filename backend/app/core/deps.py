"""Shared FastAPI dependencies: current user, pagination, public/private demo access."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the authenticated user from a Bearer token."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(_extract_token(authorization))
        user_id = int(payload.get("sub", ""))
    except Exception:
        raise credentials_exc from None
    user = db.get(User, user_id)
    if user is None:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Resolve the authenticated user if present, otherwise return ``None``.

    Used by public endpoints that still personalize data when possible.
    """
    if not authorization:
        return None
    try:
        payload = decode_access_token(_extract_token(authorization))
        return db.get(User, int(payload.get("sub", "")))
    except Exception:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
