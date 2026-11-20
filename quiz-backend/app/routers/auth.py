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


import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, status

# In-memory tracking of failed login attempts: ip -> list of failure timestamps
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_WINDOW_SECONDS = 60


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    # Filter attempts within the window
    attempts = [t for t in _failed_attempts[client_ip] if now - t < _LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[client_ip] = attempts
    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(_LOCKOUT_WINDOW_SECONDS)},
        )


def _record_failed_attempt(client_ip: str) -> None:
    _failed_attempts[client_ip].append(time.time())


def _reset_attempts(client_ip: str) -> None:
    _failed_attempts.pop(client_ip, None)


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
        429: {"description": "Too many failed login attempts."},
    },
)
def admin_login(
    login_request: AdminLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    POST /api/v1/admin/login

    Validates username + password, returns a signed JWT access token.
    Protected against brute-force attacks via per-IP rate limiting.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    _check_rate_limit(client_ip)

    admin = authenticate_admin(db, login_request)
    if admin is None:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login: reset failed attempts
    _reset_attempts(client_ip)

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
