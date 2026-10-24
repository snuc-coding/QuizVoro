"""
auth_service.py — Database operations for admin authentication.

Handles:
  - Looking up admins by username or email.
  - Verifying passwords.
  - Creating new admin accounts (used by the seed script, not a public endpoint).

No HTTP logic here — only database + crypto operations.
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Admin
from app.schemas import AdminLoginRequest
from app.security import verify_password, hash_password


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    """Return the Admin with this username, or None if not found."""
    return db.query(Admin).filter(Admin.username == username).first()


def get_admin_by_email(db: Session, email: str) -> Admin | None:
    """Return the Admin with this email, or None if not found."""
    return db.query(Admin).filter(Admin.email == email).first()


def get_admin_by_username_or_email(db: Session, identifier: str) -> Admin | None:
    """
    Look up an admin by username OR email.
    Useful if you want to allow login with either.
    """
    return (
        db.query(Admin)
        .filter(or_(Admin.username == identifier, Admin.email == identifier))
        .first()
    )


def authenticate_admin(db: Session, login_request: AdminLoginRequest) -> Admin | None:
    """
    Validate login credentials.

    Returns the Admin object on success, None on failure.

    IMPORTANT: Return None (not raise) so that the route handler can
    produce the correct HTTP 401 response without leaking which part
    of the credentials was wrong (security best practice).
    """
    admin = get_admin_by_username(db, login_request.username)
    if admin is None:
        # Run the hash function anyway to prevent timing attacks that could
        # reveal whether a username exists.
        hash_password("dummy_constant_to_waste_time")
        return None

    if not verify_password(login_request.password, admin.hashed_password):
        return None

    if not admin.is_active:
        return None

    return admin


def create_admin(db: Session, username: str, email: str, plain_password: str) -> Admin:
    """
    Create a new admin account.

    Used by the create_admin.py seed script — NOT exposed as an API endpoint.
    Passwords are hashed with Argon2 before storage.

    Raises:
        ValueError: If the username or email is already taken.
    """
    if get_admin_by_username(db, username):
        raise ValueError(f"Username '{username}' is already taken.")
    if get_admin_by_email(db, email):
        raise ValueError(f"Email '{email}' is already registered.")

    admin = Admin(
        username=username,
        email=email,
        hashed_password=hash_password(plain_password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
