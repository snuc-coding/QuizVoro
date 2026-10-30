# """
# database.py — SQLAlchemy engine, session factory, and Base class.

# All models import Base from here.
# All route handlers receive a database session via the get_db dependency.

# Connection: PostgreSQL via psycopg (psycopg3).
# ORM: SQLAlchemy 2.x declarative style.
# """

# from sqlalchemy import create_engine
# from sqlalchemy.orm import declarative_base, sessionmaker, Session
# from typing import Generator

# from app.config import get_settings

# settings = get_settings()

# # ── Engine ────────────────────────────────────────────────────────────────────
# # pool_pre_ping=True: SQLAlchemy will test the connection before using it,
# # recovering gracefully from stale connections after the DB restarts.
# engine = create_engine(
#     settings.DATABASE_URL,
#     pool_pre_ping=True,
#     # For development, echo=True logs every SQL statement.
#     # Set to False in production.
#     echo=(settings.ENVIRONMENT == "development"),
# )

# # ── Session factory ───────────────────────────────────────────────────────────
# # autocommit=False: we control transactions explicitly.
# # autoflush=False:  changes are flushed only when we call session.flush()
# #                   or session.commit(), giving us more control.
# SessionLocal = sessionmaker(
#     bind=engine,
#     autocommit=False,
#     autoflush=False,
# )

# # ── Declarative base ──────────────────────────────────────────────────────────
# # All SQLAlchemy models inherit from this Base.
# Base = declarative_base()


# # ── Dependency ────────────────────────────────────────────────────────────────
# def get_db() -> Generator[Session, None, None]:
#     """
#     FastAPI dependency that provides a database session per request.

#     Usage in a route:
#         def my_route(db: Session = Depends(get_db)):
#             ...

#     The session is automatically closed after the request finishes,
#     even if an exception is raised.
#     """
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
"""
database.py — SQLAlchemy engine, session factory, and Base class.

All models import Base from here.
HTTP route handlers receive a database session via the get_db dependency.
WebSocket handlers must NOT use get_db (it holds a connection for the whole
socket lifetime); use the db_session() context manager around each DB access.

Connection: PostgreSQL via psycopg (psycopg3).
ORM: SQLAlchemy 2.x declarative style.
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# Keep pool_size + max_overflow below Postgres max_connections (default 100).
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))
POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "10"))

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,  # fail fast instead of hanging 30s
    pool_recycle=1800,
    echo=(settings.ENVIRONMENT == "development"),
)


@event.listens_for(engine, "checkout")
def _log_checkout(dbapi_conn, rec, proxy):
    print("POOL:", engine.pool.status())

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ──────────────────────────────────────────────────────────
Base = declarative_base()


# ── Dependencies ──────────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per HTTP request, closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Short-lived session for WebSocket handlers.

    Usage:
        with db_session() as db:
            participant = db.get(Participant, pid)
            pid = participant.id   # copy out plain values
        # connection is released here, before the long-lived receive loop

    Copy any values you need out of ORM objects before the block ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
