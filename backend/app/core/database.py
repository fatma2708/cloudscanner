"""SQLAlchemy engine, session factory and declarative base.

The engine is created lazily so tests can swap the database URL before the
first import of any model.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_engine = None
_session_factory: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine() -> object:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def get_engine():
    """Return a lazily-initialized global engine."""
    global _engine, _session_factory
    if _engine is None:
        _engine = _make_engine()
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the global session factory, initializing the engine if needed."""
    get_engine()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    """Create tables for the current metadata. Used by tests and demo seeding."""
    from app.models import analysis, project, recommendation, user  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
