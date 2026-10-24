"""
models.py — SQLAlchemy ORM models.

Developer 1 owns: Admin, Quiz, Round, Question, Option.
Shared stubs:      Game, Participant, GameParticipant, Answer, Score
                   (column structure to be finalised with Dev 2 & Dev 3).

Table naming: snake_case plural (PostgreSQL convention).
ID type:      Integer primary key (simple, works well at student-project scale).
              Change to UUID if the team prefers it — update this file and run
              a new Alembic migration.

Relationships defined here so that all three developers share the same ORM.
"""

import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Helper: auto-populated timestamps
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# ADMINS
# Dev 1 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class Admin(Base):
    """
    Represents a quiz administrator.

    Admins can log in, create quizzes, add rounds and questions.
    Passwords are stored as Argon2 hashes — NEVER plaintext.
    """
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Argon2 hash — long enough for the full hash string (~100 chars).
    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # One admin → many quizzes
    quizzes = relationship("Quiz", back_populates="admin", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# QUIZZES
# Dev 1 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class Quiz(Base):
    """
    A quiz is the top-level container (e.g. "Week 3 Tech Quiz").

    A quiz belongs to one admin and contains one or more rounds.
    The 'is_published' flag can be used by Dev 3 to gate live-game creation.
    """
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False, nullable=False)

    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    admin = relationship("Admin", back_populates="quizzes")
    rounds = relationship("Round", back_populates="quiz", cascade="all, delete-orphan", order_by="Round.round_number")

    # Games that use this quiz template (Dev 3 will populate this side)
    games = relationship("Game", back_populates="quiz")


# ─────────────────────────────────────────────────────────────────────────────
# ROUNDS
# Dev 1 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class Round(Base):
    """
    A round groups questions within a quiz.

    round_number must be unique within a quiz (enforced by a DB constraint).
    E.g. Quiz "Tech Night" → Round 1 "General Knowledge", Round 2 "Python".
    """
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    round_number = Column(Integer, nullable=False)

    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="rounds")
    questions = relationship(
        "Question",
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="Question.question_order",
    )

    # DB-level guarantee: no duplicate round_number within the same quiz.
    __table_args__ = (
        UniqueConstraint("quiz_id", "round_number", name="uq_rounds_quiz_round_number"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# QUESTIONS
# Dev 1 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class Question(Base):
    """
    A single question inside a round.

    question_type: currently "MCQ". Extend to "TRUE_FALSE", "SHORT_ANSWER", etc.
    media_url:     relative path to the uploaded file in the media/ directory
                   (NOT an absolute filesystem path, NOT a binary blob).
    media_type:    "image", "audio", "video", or None.
    """
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False, default="MCQ")
    time_limit = Column(Integer, nullable=False, default=30)   # seconds
    points = Column(Integer, nullable=False, default=1000)
    question_order = Column(Integer, nullable=False, default=1)

    # Multimedia references — stored as relative URL paths.
    media_url = Column(String(500), nullable=True)
    media_type = Column(String(10), nullable=True)   # "image" | "audio" | "video"

    round_id = Column(Integer, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    round = relationship("Round", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")

    # Answers reference this question (Dev 2 creates the answers table).
    answers = relationship("Answer", back_populates="question")

    # Prevent two questions with the same order number in the same round.
    __table_args__ = (
        UniqueConstraint(
            "round_id", "question_order",
            name="uq_questions_round_question_order",
        ),
        Index("ix_questions_round_id", "round_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONS
# Dev 1 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class Option(Base):
    """
    One MCQ answer choice for a question.

    is_correct is stored in the database and returned to ADMINS only.
    Participant-facing endpoints (Dev 2) must exclude is_correct.

    SECURITY NOTE: Never expose is_correct through a participant API endpoint
    before the authorized answer reveal.
    """
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    option_text = Column(String(500), nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)

    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    question = relationship("Question", back_populates="options")

    # Answers reference which option was chosen (Dev 2).
    answers = relationship("Answer", back_populates="chosen_option")

    __table_args__ = (
        Index("ix_options_question_id", "question_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SHARED TABLES — stubs for Dev 2 and Dev 3 compatibility.
# These are defined here so that foreign-key relationships work across the
# whole team's codebase from a single shared models.py.
#
# Dev 2 and Dev 3: add columns, relationships, and business logic to these
# stubs. Do NOT create separate model files that redefine these tables.
# ─────────────────────────────────────────────────────────────────────────────

class Game(Base):
    """
    Represents a live game session.

    A game is a running instance of a quiz.
    Dev 3 owns the game lifecycle (creating, starting, pausing, ending).
    Dev 2 owns participant joining and answer submission.
    Dev 1 provides the quiz data this game is based on.

    Columns to be extended by Dev 3 as needed.
    """
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)

    # The quiz template this game is running.
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False)

    # 6-digit PIN for participants to join (Dev 2 + Dev 3).
    pin = Column(String(10), unique=True, nullable=True, index=True)

    # Game lifecycle state (Dev 3 manages transitions).
    # Possible values: "lobby" | "active" | "paused" | "finished"
    status = Column(String(20), nullable=False, default="lobby")

    # Which question is currently being displayed (Dev 3 manages this).
    current_question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # When answers opened for the current question (Dev 3 sets this; Dev 2's
    # answer timing and scoring read it). On resume after a pause, Dev 3 shifts it
    # forward by the paused duration so paused time never counts against players.
    current_question_started_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="games")
    game_participants = relationship("GameParticipant", back_populates="game", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="game")


class Participant(Base):
    """
    A person who joins a live game as a player.

    Dev 2 owns participant joining and management.
    """
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(50), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    game_participants = relationship("GameParticipant", back_populates="participant")


class GameParticipant(Base):
    """
    Junction table linking a Participant to a specific Game.
    Tracks per-game score.

    Dev 2 owns scoring. Dev 3 may use this for leaderboard broadcasts.
    """
    __tablename__ = "game_participants"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    total_score = Column(Integer, default=0, nullable=False)

    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ── Dev 2: joining and rejoining ─────────────────────────────────────────
    # Secret the player's phone keeps (localStorage) to rejoin after a dropped
    # connection. Sent back as the X-Participant-Token header.
    token = Column(String(64), unique=True, nullable=True, index=True)
    # Nickname folded to lower case, so "Rathi" and "RATHI" can't both join a game.
    nickname_key = Column(String(50), nullable=True)
    # False once the host removes the player (Dev 3 sets this).
    is_active = Column(Boolean, default=True, server_default="1", nullable=False)

    # ── Dev 2: scoring state, updated once per question when it is scored ────
    correct_count = Column(Integer, default=0, server_default="0", nullable=False)
    # Sum of response times on CORRECT answers only (tie-break 3).
    correct_time_ms = Column(Integer, default=0, server_default="0", nullable=False)
    current_streak = Column(Integer, default=0, server_default="0", nullable=False)
    best_streak = Column(Integer, default=0, server_default="0", nullable=False)
    rank = Column(Integer, nullable=True)            # None until the first question is scored
    previous_rank = Column(Integer, nullable=True)   # rank before the latest scoring

    game = relationship("Game", back_populates="game_participants")
    participant = relationship("Participant", back_populates="game_participants")
    answers = relationship("Answer", back_populates="game_participant")

    # A participant can only join a given game once.
    __table_args__ = (
        UniqueConstraint("game_id", "participant_id", name="uq_game_participants_game_participant"),
        UniqueConstraint("game_id", "nickname_key", name="uq_game_participants_game_nickname"),
    )


class Answer(Base):
    """
    A participant's answer to a question in a live game.

    Dev 2 owns answer submission and validation.
    is_correct and points_awarded are computed by Dev 2's scoring logic.
    """
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    game_participant_id = Column(Integer, ForeignKey("game_participants.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    chosen_option_id = Column(Integer, ForeignKey("options.id", ondelete="SET NULL"), nullable=True)

    is_correct = Column(Boolean, nullable=True)           # set after evaluation
    points_awarded = Column(Integer, nullable=True)       # set after scoring
    response_time_ms = Column(Integer, nullable=True)     # milliseconds to answer

    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    game = relationship("Game", back_populates="answers")
    game_participant = relationship("GameParticipant", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    chosen_option = relationship("Option", back_populates="answers")

    # One answer per participant per question per game.
    __table_args__ = (
        UniqueConstraint(
            "game_id", "game_participant_id", "question_id",
            name="uq_answers_one_per_participant_per_question",
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCORED QUESTIONS
# Dev 2 owns this table.
# ─────────────────────────────────────────────────────────────────────────────

class ScoredQuestion(Base):
    """
    Records that a question has been scored in a game.

    Scoring adds points to every player's total, so it must happen exactly once.
    The unique (game_id, question_id) pair is the final guard: if two "reveal"
    requests race, only one can insert this row; the other sees the conflict and
    returns the existing result instead of scoring twice.
    """
    __tablename__ = "scored_questions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    scored_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "question_id", name="uq_scored_questions_game_question"),
    )
