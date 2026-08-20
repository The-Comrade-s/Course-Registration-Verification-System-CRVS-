"""
Centralized database connection and session management.

This is the single place where the SQLAlchemy engine and session factory
are created. No other module should construct its own engine or open raw
connections. Because access goes through SQLAlchemy's engine URL, moving
from SQLite to PostgreSQL later only requires changing CRVS_DATABASE_URL;
no application code needs to change.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from utils.logging_config import get_logger

logger = get_logger("database.connection")

_connect_args = {}
if settings.database.database_url.startswith("sqlite"):
    # Required for SQLite when used from multiple threads, which Streamlit does.
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database.database_url,
    echo=settings.database.echo_sql,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """
    Create all tables registered on the shared declarative Base.

    Safe to call multiple times; existing tables are left untouched.
    """
    from database.models import Base  # imported here to avoid circular imports

    logger.info("Initializing database schema.")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ready.")


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing it."""
    return SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope for a series of database operations.

    Commits on success, rolls back and re-raises on error, and always
    closes the session. Use this for any multi-step write operation so
    that partial data is never left behind.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Database transaction rolled back due to an error.")
        raise
    finally:
        session.close()
