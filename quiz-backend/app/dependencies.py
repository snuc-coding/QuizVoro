"""
dependencies.py — Reusable FastAPI dependency functions.

These are injected into route handlers with Depends().

Main dependencies:
  get_current_admin — Validates the Bearer token and returns the Admin model.
  require_admin     — Alias for get_current_admin (explicit naming for routes).

Usage example:
    @router.get("/protected")
    def protected_route(admin: Admin = Depends(require_admin)):
        return {"message": f"Hello, {admin.username}"}
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin
from app.security import decode_access_token

# HTTPBearer extracts the token from the "Authorization: Bearer <token>" header.
# auto_error=True means FastAPI will return 403 automatically if the header is missing.
bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """
    FastAPI dependency: authenticate the request and return the Admin.

    Steps:
      1. Extract the Bearer token from the Authorization header.
      2. Decode and verify the JWT signature and expiry.
      3. Extract the admin ID from the 'sub' claim.
      4. Fetch the admin from PostgreSQL.
      5. Verify the admin account is still active.
      6. Return the Admin ORM object.

    Raises HTTP 401 if:
      - The token is missing, malformed, expired, or has an invalid signature.
      - The admin no longer exists in the database.
      - The admin account is inactive.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        admin_id_str: str | None = payload.get("sub")
        if admin_id_str is None:
            raise _CREDENTIALS_EXCEPTION
        admin_id = int(admin_id_str)
    except (jwt.PyJWTError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    admin = db.get(Admin, admin_id)

    if admin is None:
        raise _CREDENTIALS_EXCEPTION

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled.",
        )

    return admin


# Alias — makes the intent explicit in route handlers.
require_admin = get_current_admin
