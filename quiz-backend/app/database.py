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
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# Keep pool capacity aligned with the AnyIO worker-thread limit and leave room
# for migrations/administrative connections under PostgreSQL's usual 100 limit.
POOL_SIZE = settings.DB_POOL_SIZE
MAX_OVERFLOW = settings.DB_MAX_OVERFLOW
DB_WORKER_TOKENS = settings.DB_WORKER_TOKENS or (POOL_SIZE + MAX_OVERFLOW)
POOL_TIMEOUT = settings.DB_POOL_TIMEOUT
if DB_WORKER_TOKENS > POOL_SIZE + MAX_OVERFLOW:
    raise ValueError("DB_WORKER_TOKENS must not exceed DB_POOL_SIZE + DB_MAX_OVERFLOW")

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,  # fail fast instead of hanging 30s
    pool_recycle=1800,
    echo=settings.SQL_ECHO,
)
# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
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
