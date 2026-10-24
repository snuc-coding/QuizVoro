"""
security.py — Password hashing and JWT token utilities.

Responsibilities:
  - Hash passwords with Argon2 (industry best practice for password hashing).
  - Verify passwords against their stored hash.
  - Generate signed JWT access tokens.
  - Decode and validate JWT access tokens.

This module has NO database access — it only handles cryptography.
Database lookups happen in auth_service.py or the auth dependency.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
# We use Argon2 (winner of the 2015 Password Hashing Competition).
# 'deprecated="auto"' means passlib will automatically re-hash passwords
# that were hashed with an older/weaker scheme on next login.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password with Argon2.

    Returns the full hash string (includes algorithm, parameters, and salt).
    This is safe to store in the database.

    Example:
        hashed = hash_password("my_secret")
        # hashed → "$argon2id$v=19$m=65536,t=3,p=4$..."
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plaintext password against its Argon2 hash.

    Returns True if the password matches, False otherwise.
    This function is timing-safe — it takes the same amount of time
    regardless of whether the password is correct, preventing timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      The unique identifier for the token holder (admin ID).
        extra_claims: Additional key-value pairs to embed in the token payload.
        expires_delta: How long until the token expires. Defaults to the value
                       in settings (ACCESS_TOKEN_EXPIRE_MINUTES).

    Returns:
        A signed JWT string.

    Token claims:
        sub  — Subject (admin ID as a string).
        exp  — Expiry timestamp (UTC).
        iat  — Issued-at timestamp (UTC).
        role — "admin" (so Dev 3 / Dev 2 can check role without a DB query).
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "role": "admin",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Raises:
        jose.JWTError: If the token is invalid, expired, or tampered with.

    Returns:
        The decoded token payload as a dictionary.

    The caller (dependencies.py) is responsible for converting JWTError
    into an appropriate HTTP 401 response.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
