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
from typing import Any, Callable, Generator, TypeVar

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# Every database call runs in a worker thread (see run_db), and each thread
# holds at most one connection. With at least as many connections as worker
# threads, a thread never waits for a connection, so the two pools cannot
# starve each other. Keep POOL_SIZE + MAX_OVERFLOW below Postgres
# max_connections (default 100), leaving room for migrations and psql.
THREADPOOL_SIZE = int(os.getenv("THREADPOOL_SIZE", "60"))
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "40"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "10"))

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,  # fail fast instead of hanging 30s
    pool_recycle=1800,
    # Logging every statement is far too slow for a live game; opt in with SQL_ECHO.
    echo=settings.SQL_ECHO,
)

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


T = TypeVar("T")


async def run_db(fn: Callable[..., T], *args: Any, db: Session | None = None) -> T:
    """
    Run fn(db, *args) in a worker thread, never on the event loop.

    A blocking query on the loop freezes every socket on the server while it
    waits, so async code must reach the database only through this.

    With db=None the call gets its own short-lived session. With a request's
    session (from get_db), its transaction is ended in the same thread, so the
    connection goes back to the pool before the request waits on anything else.
    Either way fn must return plain values or Pydantic models, not ORM objects:
    they are expired by then and would lazy-load on the loop.
    """
    def _inner() -> T:
        if db is None:
            with SessionLocal() as own_db:
                return fn(own_db, *args)
        try:
            return fn(db, *args)
        finally:
            db.rollback()  # after a commit this just ends the read transaction
    return await run_in_threadpool(_inner)


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
