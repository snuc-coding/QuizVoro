"""
main.py — FastAPI application entry point.

This file:
  1. Creates the FastAPI app instance for QuizVoro.
  2. Registers all routers under the /api/v1 prefix.
  3. Mounts static media files at /media.
  4. Configures CORS.
  5. Provides a health-check endpoint.

To run:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import DB_WORKER_TOKENS
from app.routers import auth, quizzes, rounds, questions, games, game_controls, websocket

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep synchronous database workers in step with the SQLAlchemy pool."""
    thread_limiter = anyio.to_thread.current_default_thread_limiter()
    previous_tokens = thread_limiter.total_tokens
    thread_limiter.total_tokens = DB_WORKER_TOKENS
    try:
        yield
    finally:
        thread_limiter.total_tokens = previous_tokens

# Ensure media directory exists before mounting
media_path = Path(settings.MEDIA_DIR).resolve()
media_path.mkdir(parents=True, exist_ok=True)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="QuizVoro — Live Quiz API",
    description=(
        "Backend API for QuizVoro — the live multiplayer quiz platform.\n\n"
        "**Developer 1** (Auth + Quiz Management) endpoints are implemented here.\n\n"
        "Developer 2 (Participants + Scoring) and Developer 3 (WebSockets + Game Control) "
        "will extend this API.\n\n"
        "## Authentication\n"
        "All quiz-management endpoints require a JWT Bearer token obtained from "
        "`POST /api/v1/admin/login`.\n"
        "Include it in the `Authorization` header: `Bearer <your_token>`."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.middleware("http")
async def record_request_arrival(request, call_next):
    """Capture answer arrival before dependency/database queues can delay it."""
    request.state.received_at = datetime.now(timezone.utc)
    return await call_next(request)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Static Media ────────────────────────────────────────────────────────
# Enables public access to uploaded question images/audio/video at /media/<filename>
# for participants (Dev 2) and live stage displays (Dev 3).
app.mount("/media", StaticFiles(directory=str(media_path)), name="media")

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

# Authentication: /api/v1/admin/...
app.include_router(auth.router, prefix=API_PREFIX)

# Quizzes: /api/v1/quizzes/...
app.include_router(quizzes.router, prefix=API_PREFIX)

# Rounds — two prefixes:
#   /api/v1/quizzes/{quizId}/rounds/...
#   /api/v1/rounds/{roundId}/...
app.include_router(rounds.quiz_router, prefix=API_PREFIX)
app.include_router(rounds.round_router, prefix=API_PREFIX)

# Questions — two prefixes:
#   /api/v1/rounds/{roundId}/questions/...
#   /api/v1/questions/{questionId}/...
app.include_router(questions.round_router, prefix=API_PREFIX)
app.include_router(questions.question_router, prefix=API_PREFIX)
app.include_router(questions.media_router, prefix=API_PREFIX)

# Live games (Developer 2): /api/v1/games/...
app.include_router(games.router, prefix=API_PREFIX)

# Host game controls (Developer 3): /api/v1/games/...
app.include_router(game_controls.router, prefix=API_PREFIX)

# Real-time WebSockets (Developer 3): /api/v1/ws/games/...
app.include_router(websocket.router, prefix=API_PREFIX)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Health Check")
def health_check() -> dict:
    """
    Simple liveness probe.
    Returns {"status": "ok"} when the application is running.
    """
    return {"status": "ok", "app": "QuizVoro", "version": "1.0.0"}
