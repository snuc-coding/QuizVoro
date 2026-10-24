"""
routers/rounds.py — Round management endpoints.

Endpoints:
  POST   /api/v1/quizzes/{quizId}/rounds  ← Required (original endpoint)
  GET    /api/v1/quizzes/{quizId}/rounds  ← Additional
  GET    /api/v1/rounds/{roundId}         ← Additional
  PATCH  /api/v1/rounds/{roundId}         ← Additional
  DELETE /api/v1/rounds/{roundId}         ← Additional
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Admin
from app.schemas import RoundIn, RoundOut, RoundUpdate
from app.services import round_service

# Two routers because rounds are accessed via two different path prefixes:
#   /quizzes/{quizId}/rounds  (nested under quizzes)
#   /rounds/{roundId}         (direct access by ID)
quiz_router = APIRouter(
    prefix="/quizzes",
    tags=["Rounds"],
)

round_router = APIRouter(
    prefix="/rounds",
    tags=["Rounds"],
)


@quiz_router.post(
    "/{quizId}/rounds",
    response_model=RoundOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Round",
    description=(
        "Create a new round inside a quiz. "
        "round_number must be unique within the quiz."
    ),
    responses={
        201: {"description": "Round created."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Quiz not found."},
        409: {"description": "Duplicate round number within the quiz."},
    },
)
def create_round(
    quizId: int,
    round_in: RoundIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RoundOut:
    """POST /api/v1/quizzes/{quizId}/rounds"""
    return round_service.create_round(db, quizId, round_in, admin)


@quiz_router.get(
    "/{quizId}/rounds",
    response_model=list[RoundOut],
    summary="List Rounds",
    description="Return all rounds in a quiz, ordered by round_number.",
)
def list_rounds(
    quizId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[RoundOut]:
    """GET /api/v1/quizzes/{quizId}/rounds"""
    return round_service.list_rounds_for_quiz(db, quizId, admin)


@round_router.get(
    "/{roundId}",
    response_model=RoundOut,
    summary="Get Round",
    description="Return a single round with its questions.",
    responses={
        200: {"description": "Round returned."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Round not found."},
    },
)
def get_round(
    roundId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RoundOut:
    """GET /api/v1/rounds/{roundId}"""
    return round_service.get_round_and_verify_ownership(db, roundId, admin)


@round_router.patch(
    "/{roundId}",
    response_model=RoundOut,
    summary="Update Round",
    description="Partially update a round.",
    responses={
        200: {"description": "Round updated."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Round not found."},
        409: {"description": "Duplicate round number."},
    },
)
def update_round(
    roundId: int,
    round_update: RoundUpdate,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RoundOut:
    """PATCH /api/v1/rounds/{roundId}"""
    round_ = round_service.get_round_and_verify_ownership(db, roundId, admin)
    return round_service.update_round(db, round_, round_update, admin)


@round_router.delete(
    "/{roundId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Round",
    description="Delete a round and all its questions.",
    responses={
        204: {"description": "Round deleted."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Round not found."},
    },
)
def delete_round(
    roundId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """DELETE /api/v1/rounds/{roundId}"""
    round_ = round_service.get_round_and_verify_ownership(db, roundId, admin)
    round_service.delete_round(db, round_)
