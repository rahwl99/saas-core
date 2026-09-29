from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from saas_core.config.settings import get_saas_settings

_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_saas_settings()
        connect_args = {}
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True
        )
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy database session.
    Automatically handles commit/rollback and closing.
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
