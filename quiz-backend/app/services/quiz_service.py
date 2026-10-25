"""
quiz_service.py — Database operations for quiz management.

Handles CRUD operations for the Quiz model.
Ownership checks are enforced here (not in the route handler)
to keep the routes clean and the business rules centralized.
"""

from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import Quiz, Admin, Round, Question
from app.schemas import QuizIn, QuizUpdate


def create_quiz(db: Session, quiz_in: QuizIn, admin: Admin) -> Quiz:
    """Create a new quiz owned by the given admin."""
    title_clean = quiz_in.title.strip()
    if not title_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quiz title cannot be empty.",
        )

    quiz = Quiz(
        title=title_clean,
        description=quiz_in.description.strip() if quiz_in.description else None,
        admin_id=admin.id,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


def get_quiz_by_id(db: Session, quiz_id: int) -> Quiz:
    """
    Return the quiz with this ID.
    Raises HTTP 404 if not found.
    """
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} was not found.",
        )
    return quiz


def get_quiz_and_verify_ownership(db: Session, quiz_id: int, admin: Admin) -> Quiz:
    """
    Return the quiz and verify the authenticated admin owns it.
    Raises HTTP 404 if not found, HTTP 403 if not the owner.
    """
    quiz = get_quiz_by_id(db, quiz_id)
    if quiz.admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this quiz.",
        )
    return quiz


def get_quiz_detail_and_verify_ownership(db: Session, quiz_id: int, admin: Admin) -> Quiz:
    """
    Return the quiz with all nested rounds, questions, and options loaded efficiently
    using selectinload to eliminate N+1 query patterns.
    """
    quiz = (
        db.query(Quiz)
        .options(
            selectinload(Quiz.rounds)
            .selectinload(Round.questions)
            .selectinload(Question.options)
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} was not found.",
        )
    if quiz.admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this quiz.",
        )
    return quiz


def list_quizzes_for_admin(db: Session, admin: Admin) -> list[Quiz]:
    """Return all quizzes belonging to this admin."""
    return db.query(Quiz).filter(Quiz.admin_id == admin.id).order_by(Quiz.created_at.desc()).all()


def update_quiz(db: Session, quiz: Quiz, quiz_update: QuizUpdate) -> Quiz:
    """
    Apply a partial update to a quiz. Only updates fields that are provided.
    Rejects explicit null values for non-nullable columns (e.g. title, is_published).
    """
    update_data = quiz_update.model_dump(exclude_unset=True)

    # Validate non-nullable fields when provided
    if "title" in update_data:
        val = update_data["title"]
        if val is None or not val.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quiz title cannot be null or empty.",
            )
        update_data["title"] = val.strip()

    if "is_published" in update_data and update_data["is_published"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_published cannot be null.",
        )

    # If quiz is published and content (title/description) is being changed without unpublishing
    content_modified = ("title" in update_data or "description" in update_data)
    if quiz.is_published and content_modified and update_data.get("is_published") is not False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit content of a published quiz. Please unpublish it first.",
        )

    for field, value in update_data.items():
        setattr(quiz, field, value)

    db.commit()
    db.refresh(quiz)
    return quiz


def delete_quiz(db: Session, quiz: Quiz) -> None:
    """
    Delete a quiz and all its rounds/questions (cascade is set in the model).
    If live games reference this quiz, the foreign key RESTRICT constraint
    prevents deletion and raises HTTP 409.
    """
    try:
        db.delete(quiz)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete quiz because live games are associated with it.",
        )
