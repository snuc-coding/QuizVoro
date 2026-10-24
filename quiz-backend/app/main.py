"""
main.py — FastAPI application entry point.

This file:
  1. Creates the FastAPI app instance.
  2. Registers all routers under the /api/v1 prefix.
  3. Configures CORS.
  4. Provides a health-check endpoint.

To run:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, quizzes, rounds, questions

settings = get_settings()

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cognizant Quiz Club — Live Quiz API",
    description=(
        "Backend API for the Cognizant Quiz Club Kahoot-like live quiz application.\n\n"
        "**Developer 1** (Auth + Quiz Management) endpoints are implemented here.\n\n"
        "Developer 2 (Participants + Scoring) and Developer 3 (WebSockets + Game Control) "
        "will extend this API.\n\n"
        "## Authentication\n"
        "All quiz-management endpoints require a JWT Bearer token obtained from "
        "`POST /api/v1/admin/login`.\n"
        "Include it in the `Authorization` header: `Bearer <your_token>`."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Health Check")
def health_check() -> dict:
    """
    Simple liveness probe.
    Returns {"status": "ok"} when the application is running.
    """
    return {"status": "ok", "version": "1.0.0"}
