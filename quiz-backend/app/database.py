"""
database.py — SQLAlchemy engine, session factory, and Base class.

All models import Base from here.
All route handlers receive a database session via the get_db dependency.

Connection: PostgreSQL via psycopg (psycopg3).
ORM: SQLAlchemy 2.x declarative style.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True: SQLAlchemy will test the connection before using it,
# recovering gracefully from stale connections after the DB restarts.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # For development, echo=True logs every SQL statement.
    # Set to False in production.
    echo=(settings.ENVIRONMENT == "development"),
)

# ── Session factory ───────────────────────────────────────────────────────────
# autocommit=False: we control transactions explicitly.
# autoflush=False:  changes are flushed only when we call session.flush()
#                   or session.commit(), giving us more control.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ──────────────────────────────────────────────────────────
# All SQLAlchemy models inherit from this Base.
Base = declarative_base()


# ── Dependency ────────────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        def my_route(db: Session = Depends(get_db)):
            ...

    The session is automatically closed after the request finishes,
    even if an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
