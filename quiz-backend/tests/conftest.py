"""
conftest.py — Shared pytest fixtures.

This file is automatically loaded by pytest before any test runs.

Strategy:
  - Use SQLite in-memory database for tests (no PostgreSQL needed).
  - Override the get_db dependency so test routes use the in-memory DB.
  - Create a fresh database schema before each test module.
  - Provide a TestClient that bypasses real HTTP.

Why SQLite for tests?
  SQLite is bundled with Python — no install needed.
  The in-memory database is deleted when the test session ends.
  For production-parity, you can point TEST_DATABASE_URL at a real
  PostgreSQL test database and the fixtures work without changes.

NOTE: Some PostgreSQL-specific constraints (e.g., certain index types)
may not apply in SQLite. If you need exact PostgreSQL behaviour in tests,
set the DATABASE_URL in the test environment to a PostgreSQL URL.
"""

import os
import pytest

# Point to an in-memory SQLite database BEFORE importing anything from app,
# because config.py reads the env var at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_that_is_long_enough_32chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("MEDIA_DIR", "test_media")
os.environ.setdefault("MAX_UPLOAD_SIZE_MB", "10")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ENVIRONMENT", "test")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import Admin
from app.security import hash_password

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Replace the production DB session with the test DB session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    """
    Provide a fresh database for each test function.
    Tables are created before the test and dropped after.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """
    FastAPI TestClient with the test database injected.
    Each test function gets an isolated database.
    """
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_admin(db):
    """Create and return a test admin in the database."""
    admin = Admin(
        username="testadmin",
        email="testadmin@example.com",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client, test_admin):
    """
    Log in as the test admin and return Authorization headers.
    Use this in tests that require authentication.
    """
    response = client.post(
        "/api/v1/admin/login",
        json={"username": "testadmin", "password": "testpassword123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
