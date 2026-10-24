"""
question_service.py — Database operations for question and option management.

Key rules enforced here:
  - Admin must own the quiz that contains the round.
  - MCQ questions: 2–6 options, exactly 1 correct (also validated by Pydantic).
  - question_order must be unique within a round.
  - Questions and options are saved in a single transaction.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import Question, Option, Admin
from app.schemas import QuestionIn, QuestionUpdate
from app.services.round_service import get_round_by_id, get_round_and_verify_ownership


def create_question(db: Session, round_id: int, question_in: QuestionIn, admin: Admin) -> Question:
    """
    Create a question (and its options) inside a round.

    Steps:
      1. Verify round exists.
      2. Verify admin owns the parent quiz.
      3. Check question_order uniqueness within the round.
      4. Save question and all options in one transaction.
         If anything fails, nothing is saved (atomicity).
    """
    round_ = get_round_and_verify_ownership(db, round_id, admin)

    # Check for duplicate question_order within this round.
    order_conflict = (
        db.query(Question)
        .filter(
            Question.round_id == round_.id,
            Question.question_order == question_in.question_order,
        )
        .first()
    )
    if order_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Question order {question_in.question_order} is already used in this round. "
                "Use a different order number."
            ),
        )

    question = Question(
        question_text=question_in.question_text.strip(),
        question_type=question_in.question_type,
        time_limit=question_in.time_limit,
        points=question_in.points,
        question_order=question_in.question_order,
        round_id=round_.id,
    )
    db.add(question)
    db.flush()  # Assign question.id without committing, so options can reference it.

    # Add all options in the same transaction.
    for opt_in in question_in.options:
        option = Option(
            option_text=opt_in.option_text.strip(),
            is_correct=opt_in.is_correct,
            question_id=question.id,
        )
        db.add(option)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question order {question_in.question_order} already exists in this round.",
        )

    db.refresh(question)
    return question


def get_question_by_id(db: Session, question_id: int) -> Question:
    """Return the question, raise 404 if not found."""
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} was not found.",
        )
    return question


def get_question_and_verify_ownership(db: Session, question_id: int, admin: Admin) -> Question:
    """Return the question and verify admin owns its parent quiz."""
    question = get_question_by_id(db, question_id)
    # Walk up: question → round → quiz → check admin
    round_ = get_round_by_id(db, question.round_id)
    from app.services.quiz_service import get_quiz_and_verify_ownership
    get_quiz_and_verify_ownership(db, round_.quiz_id, admin)
    return question


def list_questions_for_round(db: Session, round_id: int, admin: Admin) -> list[Question]:
    """List all questions in a round. Admin must own the parent quiz."""
    round_ = get_round_and_verify_ownership(db, round_id, admin)
    return (
        db.query(Question)
        .filter(Question.round_id == round_.id)
        .order_by(Question.question_order)
        .all()
    )


def update_question(
    db: Session, question: Question, question_update: QuestionUpdate, admin: Admin
) -> Question:
    """Partial update on a question. Checks question_order uniqueness if changing it."""
    update_data = question_update.model_dump(exclude_unset=True)

    if "question_order" in update_data:
        new_order = update_data["question_order"]
        conflict = (
            db.query(Question)
            .filter(
                Question.round_id == question.round_id,
                Question.question_order == new_order,
                Question.id != question.id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Question order {new_order} already exists in this round.",
            )

    for field, value in update_data.items():
        if value is not None:
            setattr(question, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question order conflict.",
        )

    db.refresh(question)
    return question


def delete_question(db: Session, question: Question) -> None:
    """Delete a question and its options (cascade)."""
    db.delete(question)
    db.commit()


def attach_media_to_question(
    db: Session, question: Question, media_url: str, media_type: str
) -> Question:
    """Update the media reference fields on a question after a successful upload."""
    question.media_url = media_url
    question.media_type = media_type
    db.commit()
    db.refresh(question)
    return question
