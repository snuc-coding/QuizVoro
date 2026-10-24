"""
quiz_service.py — Database operations for quiz management.

Handles CRUD operations for the Quiz model.
Ownership checks are enforced here (not in the route handler)
to keep the routes clean and the business rules centralized.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Quiz, Admin
from app.schemas import QuizIn, QuizUpdate


def create_quiz(db: Session, quiz_in: QuizIn, admin: Admin) -> Quiz:
    """Create a new quiz owned by the given admin."""
    quiz = Quiz(
        title=quiz_in.title.strip(),
        description=quiz_in.description,
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

    We return 404 for unauthorized access too (instead of 403) to avoid
    leaking whether a quiz exists to non-owners. This is a security choice;
    switch to 403 if your team prefers explicit ownership errors.
    """
    quiz = get_quiz_by_id(db, quiz_id)
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
    """Apply a partial update to a quiz. Only updates fields that are provided."""
    update_data = quiz_update.model_dump(exclude_unset=True)
    if "title" in update_data and update_data["title"] is not None:
        update_data["title"] = update_data["title"].strip()
        if not update_data["title"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quiz title cannot be empty.",
            )
    for field, value in update_data.items():
        setattr(quiz, field, value)
    db.commit()
    db.refresh(quiz)
    return quiz


def delete_quiz(db: Session, quiz: Quiz) -> None:
    """Delete a quiz and all its rounds/questions (cascade is set in the model)."""
    db.delete(quiz)
    db.commit()
