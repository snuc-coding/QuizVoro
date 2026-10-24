"""
schemas.py — Pydantic request and response models.

Why separate schemas from ORM models?
  - ORM models describe the database shape.
  - Pydantic schemas describe the API contract (what comes in, what goes out).
  - Keeping them separate lets us control exactly what data is exposed.

IMPORTANT — Answer security:
  AdminQuestionOut includes is_correct on each option.
  ParticipantQuestionOut deliberately OMITS is_correct.
  Developer 2 must use ParticipantQuestionOut (or an equivalent)
  when sending questions to participants during a live game.
"""

from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, EmailStr, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Base helpers
# ─────────────────────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    """All 'Out' schemas inherit from this to enable ORM mode."""
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN / AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    """Request body for POST /api/v1/admin/login"""
    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Administrator username",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Administrator password",
        examples=["supersecret"],
    )


class TokenResponse(BaseModel):
    """Response body for successful login."""
    access_token: str = Field(..., description="JWT Bearer token")
    token_type: str = Field(default="bearer", description="Always 'bearer'")
    expires_in: int = Field(..., description="Token lifetime in seconds")


class AdminOut(OrmBase):
    """Safe admin representation — never includes hashed_password."""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS
# ─────────────────────────────────────────────────────────────────────────────

class OptionIn(BaseModel):
    """One MCQ answer option sent when creating a question."""
    option_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The text of this answer choice",
    )
    is_correct: bool = Field(
        ...,
        description="True for the correct answer, False for distractors",
    )


class AdminOptionOut(OrmBase):
    """Option returned to admins — INCLUDES is_correct."""
    id: int
    option_text: str
    is_correct: bool       # ← admins can see this
    question_id: int


class ParticipantOptionOut(OrmBase):
    """
    Option returned to participants during a live quiz.

    is_correct is deliberately OMITTED to prevent cheating.
    Developer 2 must use this schema (or equivalent) in participant endpoints.
    """
    id: int
    option_text: str
    question_id: int
    # is_correct is intentionally absent ← SECURITY


# ─────────────────────────────────────────────────────────────────────────────
# QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_QUESTION_TYPES = Literal["MCQ"]
ALLOWED_MEDIA_TYPES = Literal["image", "audio", "video"]


class QuestionIn(BaseModel):
    """Request body for POST /api/v1/rounds/{roundId}/questions"""
    question_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question text shown to participants",
    )
    question_type: ALLOWED_QUESTION_TYPES = Field(
        default="MCQ",
        description="Question format. Currently only 'MCQ' is supported.",
    )
    time_limit: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds participants have to answer (5–300)",
    )
    points: int = Field(
        default=1000,
        ge=0,
        le=10000,
        description="Maximum points awarded for a correct answer (0–10000)",
    )
    question_order: int = Field(
        default=1,
        ge=1,
        description="Display order within the round (1-indexed, must be unique)",
    )
    options: list[OptionIn] = Field(
        default=[],
        description="Answer options. MCQ questions require 2–6 options with exactly one correct.",
    )

    @model_validator(mode="after")
    def validate_mcq_options(self) -> "QuestionIn":
        if self.question_type == "MCQ":
            if len(self.options) < 2:
                raise ValueError("MCQ questions must have at least 2 options.")
            if len(self.options) > 6:
                raise ValueError("MCQ questions may have at most 6 options.")
            correct_count = sum(1 for o in self.options if o.is_correct)
            if correct_count == 0:
                raise ValueError("MCQ questions must have exactly one correct option.")
            if correct_count > 1:
                raise ValueError(
                    f"MCQ questions must have exactly one correct option, "
                    f"but {correct_count} were marked correct."
                )
        return self


class AdminQuestionOut(OrmBase):
    """Question response for admins — INCLUDES correct-answer information."""
    id: int
    question_text: str
    question_type: str
    time_limit: int
    points: int
    question_order: int
    media_url: str | None
    media_type: str | None
    round_id: int
    created_at: datetime
    updated_at: datetime
    options: list[AdminOptionOut] = []


class ParticipantQuestionOut(OrmBase):
    """
    Question response for participants during a live game.

    SECURITY CONTRACT:
    - is_correct is NOT present on any nested option.
    - This schema must be used (or an equivalent) by Developer 2
      when pushing the current question to participants.
    - Never expose AdminQuestionOut through a participant-facing endpoint.
    """
    id: int
    question_text: str
    question_type: str
    time_limit: int
    points: int
    question_order: int
    media_url: str | None
    media_type: str | None
    round_id: int
    options: list[ParticipantOptionOut] = []


class QuestionUpdate(BaseModel):
    """Optional fields for PATCH /api/v1/questions/{questionId}"""
    question_text: str | None = Field(None, min_length=1, max_length=2000)
    time_limit: int | None = Field(None, ge=5, le=300)
    points: int | None = Field(None, ge=0, le=10000)
    question_order: int | None = Field(None, ge=1)


# ─────────────────────────────────────────────────────────────────────────────
# ROUNDS
# ─────────────────────────────────────────────────────────────────────────────

class RoundIn(BaseModel):
    """Request body for POST /api/v1/quizzes/{quizId}/rounds"""
    title: str = Field(..., min_length=1, max_length=255, description="Round title")
    description: str | None = Field(None, max_length=1000, description="Optional description")
    round_number: int = Field(..., ge=1, description="Round sequence number (must be unique within the quiz)")


class RoundOut(OrmBase):
    id: int
    title: str
    description: str | None
    round_number: int
    quiz_id: int
    created_at: datetime
    updated_at: datetime
    questions: list[AdminQuestionOut] = []


class RoundUpdate(BaseModel):
    """Optional fields for PATCH /api/v1/rounds/{roundId}"""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    round_number: int | None = Field(None, ge=1)


# ─────────────────────────────────────────────────────────────────────────────
# QUIZZES
# ─────────────────────────────────────────────────────────────────────────────

class QuizIn(BaseModel):
    """Request body for POST /api/v1/quizzes"""
    title: str = Field(..., min_length=1, max_length=255, description="Quiz title")
    description: str | None = Field(None, max_length=2000, description="Optional description")


class QuizOut(OrmBase):
    id: int
    title: str
    description: str | None
    is_published: bool
    admin_id: int
    created_at: datetime
    updated_at: datetime
    rounds: list[RoundOut] = []


class QuizSummaryOut(OrmBase):
    """Lightweight quiz listing — no nested rounds/questions."""
    id: int
    title: str
    description: str | None
    is_published: bool
    admin_id: int
    created_at: datetime
    updated_at: datetime


class QuizUpdate(BaseModel):
    """Optional fields for PATCH /api/v1/quizzes/{quizId}"""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_published: bool | None = None


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA
# ─────────────────────────────────────────────────────────────────────────────

class MediaUploadOut(BaseModel):
    """Response after a successful media file upload."""
    question_id: int
    media_url: str   # relative URL path, e.g. "/media/abc123.jpg"
    media_type: str  # "image" | "audio" | "video"


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC ERROR
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response body used across all endpoints."""
    detail: str
