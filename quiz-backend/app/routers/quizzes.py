"""
routers/quizzes.py — Quiz management endpoints.

Endpoints (all require admin authentication):
  POST   /api/v1/quizzes            ← Required (original endpoint)
  GET    /api/v1/quizzes            ← Additional: list my quizzes
  GET    /api/v1/quizzes/{quizId}   ← Additional: get quiz detail
  PATCH  /api/v1/quizzes/{quizId}   ← Additional: update quiz
  DELETE /api/v1/quizzes/{quizId}   ← Additional: delete quiz
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Admin
from app.schemas import QuizIn, QuizOut, QuizSummaryOut, QuizUpdate
from app.services import quiz_service

router = APIRouter(
    prefix="/quizzes",
    tags=["Quizzes"],
)


@router.post(
    "",
    response_model=QuizOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Quiz",
    description=(
        "Create a new quiz. The quiz is automatically associated with "
        "the authenticated administrator."
    ),
    responses={
        201: {"description": "Quiz created successfully."},
        401: {"description": "Not authenticated."},
        422: {"description": "Validation error (e.g., empty title)."},
    },
)
def create_quiz(
    quiz_in: QuizIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuizOut:
    """POST /api/v1/quizzes"""
    return quiz_service.create_quiz(db, quiz_in, admin)


@router.get(
    "",
    response_model=list[QuizSummaryOut],
    summary="List My Quizzes",
    description="Return all quizzes owned by the authenticated administrator.",
)
def list_quizzes(
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[QuizSummaryOut]:
    """GET /api/v1/quizzes"""
    return quiz_service.list_quizzes_for_admin(db, admin)


@router.get(
    "/{quizId}",
    response_model=QuizOut,
    summary="Get Quiz",
    description="Return a quiz with all its rounds and questions.",
    responses={
        200: {"description": "Quiz returned."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Quiz not found."},
    },
)
def get_quiz(
    quizId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuizOut:
    """GET /api/v1/quizzes/{quizId}"""
    return quiz_service.get_quiz_detail_and_verify_ownership(db, quizId, admin)


@router.patch(
    "/{quizId}",
    response_model=QuizOut,
    summary="Update Quiz",
    description="Partially update a quiz. Only fields provided in the request body are changed.",
    responses={
        200: {"description": "Quiz updated."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Quiz not found."},
    },
)
def update_quiz(
    quizId: int,
    quiz_update: QuizUpdate,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QuizOut:
    """PATCH /api/v1/quizzes/{quizId}"""
    quiz = quiz_service.get_quiz_and_verify_ownership(db, quizId, admin)
    return quiz_service.update_quiz(db, quiz, quiz_update)


@router.delete(
    "/{quizId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Quiz",
    description=(
        "Delete a quiz and all its rounds and questions. "
        "This action is irreversible."
    ),
    responses={
        204: {"description": "Quiz deleted."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Quiz not found."},
    },
)
def delete_quiz(
    quizId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """DELETE /api/v1/quizzes/{quizId}"""
    quiz = quiz_service.get_quiz_and_verify_ownership(db, quizId, admin)
    quiz_service.delete_quiz(db, quiz)
