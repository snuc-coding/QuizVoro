"""
round_service.py — Database operations for round management.

Responsibilities:
  - Create, read, update, delete rounds within a quiz.
  - Enforce the unique round_number constraint at the service level.
  - Protect published quizzes from round modifications.
  - Validate non-nullable fields on updates (preventing 500s).
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import Round, Admin, Quiz
from app.schemas import RoundIn, RoundUpdate
from app.services.quiz_service import get_quiz_and_verify_ownership


def create_round(db: Session, quiz_id: int, round_in: RoundIn, admin: Admin) -> Round:
    """
    Create a round inside a quiz.
    Steps:
      1. Verify the quiz exists and the admin owns it.
      2. Verify quiz is not published.
      3. Check that round_number is not already used in this quiz.
      4. Save and return the new round.
    """
    quiz = get_quiz_and_verify_ownership(db, quiz_id, admin)

    if quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add rounds to a published quiz. Please unpublish it first.",
        )

    title_clean = round_in.title.strip()
    if not title_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Round title cannot be empty.",
        )

    # Service-level duplicate check (friendlier error than a raw DB IntegrityError).
    existing = (
        db.query(Round)
        .filter(Round.quiz_id == quiz.id, Round.round_number == round_in.round_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Round number {round_in.round_number} already exists in this quiz. "
                "Use a different round number."
            ),
        )

    round_ = Round(
        title=title_clean,
        description=round_in.description.strip() if round_in.description else None,
        round_number=round_in.round_number,
        quiz_id=quiz.id,
    )
    db.add(round_)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Round number {round_in.round_number} already exists in this quiz.",
        )

    db.refresh(round_)
    return round_


def get_round_by_id(db: Session, round_id: int) -> Round:
    """Return the round, raise 404 if not found."""
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Round with ID {round_id} was not found.",
        )
    return round_


def get_round_and_verify_ownership(db: Session, round_id: int, admin: Admin) -> Round:
    """Return the round and verify admin owns the parent quiz."""
    round_ = get_round_by_id(db, round_id)
    get_quiz_and_verify_ownership(db, round_.quiz_id, admin)
    return round_


def list_rounds_for_quiz(db: Session, quiz_id: int, admin: Admin) -> list[Round]:
    """List all rounds in a quiz (admin must own the quiz)."""
    quiz = get_quiz_and_verify_ownership(db, quiz_id, admin)
    return (
        db.query(Round)
        .filter(Round.quiz_id == quiz.id)
        .order_by(Round.round_number)
        .all()
    )


def update_round(db: Session, round_: Round, round_update: RoundUpdate, admin: Admin) -> Round:
    """
    Partial update on a round.
    Validates non-null values for title and round_number to prevent 500 errors.
    Checks round_number uniqueness if changing it.
    """
    quiz = get_quiz_and_verify_ownership(db, round_.quiz_id, admin)
    if quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit rounds of a published quiz. Please unpublish it first.",
        )

    update_data = round_update.model_dump(exclude_unset=True)

    if "title" in update_data:
        val = update_data["title"]
        if val is None or not val.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Round title cannot be null or empty.",
            )
        update_data["title"] = val.strip()

    if "round_number" in update_data:
        new_num = update_data["round_number"]
        if new_num is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Round number cannot be null.",
            )
        conflict = (
            db.query(Round)
            .filter(
                Round.quiz_id == round_.quiz_id,
                Round.round_number == new_num,
                Round.id != round_.id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Round number {new_num} already exists in this quiz.",
            )

    for field, value in update_data.items():
        setattr(round_, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Round number conflict.",
        )

    db.refresh(round_)
    return round_


def delete_round(db: Session, round_: Round) -> None:
    """Delete a round and its questions (cascade)."""
    quiz = db.get(Quiz, round_.quiz_id)
    if quiz and quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete rounds of a published quiz. Please unpublish it first.",
        )
    db.delete(round_)
    db.commit()
