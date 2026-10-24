"""
routers/auth.py — Authentication endpoints.

Endpoints:
  POST /api/v1/admin/login   ← Required (original planning doc endpoint)
  GET  /api/v1/admin/me      ← Additional: returns the current admin's profile
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.models import Admin
from app.schemas import AdminLoginRequest, AdminOut, TokenResponse
from app.security import create_access_token
from app.services.auth_service import authenticate_admin

router = APIRouter(
    prefix="/admin",
    tags=["Authentication"],
)

settings = get_settings()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Admin Login",
    description=(
        "Authenticate an administrator with username and password. "
        "Returns a JWT Bearer token to use in subsequent requests. "
        "Include the token in the Authorization header: `Bearer <token>`."
    ),
    responses={
        200: {"description": "Login successful. JWT token returned."},
        401: {"description": "Invalid username or password."},
        422: {"description": "Request body validation failed."},
    },
)
def admin_login(
    login_request: AdminLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    POST /api/v1/admin/login

    Validates username + password, returns a signed JWT access token.

    Security notes:
    - The error message is intentionally vague ("Invalid credentials") to avoid
      leaking whether the username or password was wrong.
    - Passwords are verified with Argon2 (timing-safe).
    """
    admin = authenticate_admin(db, login_request)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(
        subject=admin.id,
        expires_delta=timedelta(minutes=expire_minutes),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,  # seconds
    )


@router.get(
    "/me",
    response_model=AdminOut,
    summary="Get Current Admin",
    description="Return the profile of the currently authenticated administrator.",
    responses={
        200: {"description": "Admin profile returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_me(admin: Admin = Depends(require_admin)) -> AdminOut:
    """
    GET /api/v1/admin/me

    Returns the authenticated admin's profile.
    Useful for verifying that a token is valid.
    """
    return admin
