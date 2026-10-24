"""
question_service.py — Database operations for question and option management.

Key rules enforced here:
  - Admin must own the quiz that contains the round.
  - Published quiz modification protection.
  - MCQ questions: 2–6 options, exactly 1 correct (also validated by Pydantic).
  - question_order must be unique within a round.
  - Questions and options are saved in a single transaction.
  - Physical media files are cleaned up on deletion or replacement.
"""

from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.config import get_settings
from app.models import Question, Option, Admin, Quiz, Round
from app.schemas import QuestionIn, QuestionUpdate
from app.services.round_service import get_round_by_id, get_round_and_verify_ownership
from app.services.quiz_service import get_quiz_and_verify_ownership

settings = get_settings()


def _delete_physical_media(media_url: str | None) -> None:
    """Helper to remove physical media file from disk without throwing errors if missing."""
    if not media_url:
        return
    try:
        filename = Path(media_url).name
        file_path = Path(settings.MEDIA_DIR).resolve() / filename
        file_path.unlink(missing_ok=True)
    except Exception:
        pass


def create_question(db: Session, round_id: int, question_in: QuestionIn, admin: Admin) -> Question:
    """
    Create a question (and its options) inside a round.
    Steps:
      1. Verify round exists and admin owns the parent quiz.
      2. Verify parent quiz is not published.
      3. Check question_order uniqueness within the round.
      4. Save question and all options in one transaction.
    """
    round_ = get_round_and_verify_ownership(db, round_id, admin)
    quiz = get_quiz_and_verify_ownership(db, round_.quiz_id, admin)

    if quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add questions to a published quiz. Please unpublish it first.",
        )

    text_clean = question_in.question_text.strip()
    if not text_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question text cannot be empty.",
        )

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
        question_text=text_clean,
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
        opt_text = opt_in.option_text.strip()
        if not opt_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Option text cannot be empty.",
            )
        option = Option(
            option_text=opt_text,
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
    round_ = get_round_by_id(db, question.round_id)
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
    """
    Partial update on a question.
    Validates non-null values for fields to prevent 500 errors.
    Checks question_order uniqueness if changing it.
    """
    round_ = get_round_by_id(db, question.round_id)
    quiz = get_quiz_and_verify_ownership(db, round_.quiz_id, admin)

    if quiz.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit questions of a published quiz. Please unpublish it first.",
        )

    update_data = question_update.model_dump(exclude_unset=True)

    if "question_text" in update_data:
        val = update_data["question_text"]
        if val is None or not val.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question text cannot be null or empty.",
            )
        update_data["question_text"] = val.strip()

    if "time_limit" in update_data and update_data["time_limit"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Time limit cannot be null.",
        )

    if "points" in update_data and update_data["points"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Points cannot be null.",
        )

    if "question_order" in update_data:
        new_order = update_data["question_order"]
        if new_order is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question order cannot be null.",
            )
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
    """Delete a question, its options (cascade), and any attached physical media."""
    round_ = db.get(Round, question.round_id)
    if round_:
        quiz = db.get(Quiz, round_.quiz_id)
        if quiz and quiz.is_published:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete questions of a published quiz. Please unpublish it first.",
            )

    old_media = question.media_url
    db.delete(question)
    db.commit()

    # Clean up physical file after successful DB deletion
    _delete_physical_media(old_media)


def attach_media_to_question(
    db: Session, question: Question, media_url: str, media_type: str
) -> Question:
    """
    Update the media reference fields on a question after a successful upload.
    If the question already had a media file, deletes the previous file to prevent orphans.
    """
    old_media = question.media_url if question.media_url != media_url else None

    question.media_url = media_url
    question.media_type = media_type
    db.commit()
    db.refresh(question)

    if old_media:
        _delete_physical_media(old_media)

    return question
