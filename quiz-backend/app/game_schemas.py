"""
game_schemas.py — Request/response models for live games (Developer 2).

Kept apart from schemas.py (Developer 1) so the two files never conflict.

SECURITY: nothing a participant can call returns which option is correct before
the question has been scored. Correctness appears only in ScoreQuestionOut
(admin, after scoring) and in MyStatsOut.last_result (after scoring).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import OrmBase, ParticipantQuestionOut


# ── Create a game (admin) ────────────────────────────────────────────────────

class GameCreate(BaseModel):
    quiz_id: int = Field(..., gt=0, examples=[1])


class GameOut(OrmBase):
    id: int
    quiz_id: int
    pin: str
    status: str
    current_question_id: int | None
    created_at: datetime


# ── Join / rejoin (participant) ──────────────────────────────────────────────

class JoinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=10, examples=["48291375"])
    nickname: str | None = Field(None, max_length=64, examples=["Rathi"])
    is_anonymous: bool | None = Field(None, description="Whether to participate anonymously.")


class RejoinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=10, examples=["48291375"])
    token: str = Field(..., min_length=10, max_length=64)


class JoinOut(BaseModel):
    """Returned on join and rejoin. The phone stores `token` (localStorage) for rejoining."""
    game_id: int
    participant_id: int = Field(..., description="The player's id in this game (game_participants.id).")
    nickname: str
    display_name: str | None = None
    is_anonymous: bool = False
    token: str = Field(..., description="Send as the X-Participant-Token header on player endpoints.")
    game_status: str


# ── Current question (participant) ───────────────────────────────────────────

class CurrentQuestionOut(BaseModel):
    """The open question, WITHOUT correct answers, plus timing for the countdown."""
    question: ParticipantQuestionOut
    question_number: int = Field(
        ..., description="1-based position across the whole quiz (by round_number, then question_order).", examples=[1]
    )
    total_questions: int = Field(..., description="All questions in the quiz.", examples=[2])
    opened_at: datetime
    deadline: datetime
    server_time: datetime
    already_answered: bool
    is_revealed: bool = False
    revealed_data: dict | None = None


# ── Answers (participant) ────────────────────────────────────────────────────

OPTION_LETTERS = "ABCD"


class AnswerIn(BaseModel):
    """
    Send exactly one of option_id or selected_option.

    selected_option is a letter "A"-"D" (any case) or an index 0-3 into the
    question's options ordered by id, as the current question lists them.
    After validation it always holds the index (0-3).
    """
    question_id: int = Field(..., gt=0)
    option_id: int | None = Field(None, gt=0)
    selected_option: str | int | None = Field(
        None, description='"A"-"D" (any case) or 0-3, by option id order.', examples=["A"]
    )

    @field_validator("selected_option", mode="before")
    @classmethod
    def letter_or_index(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and len(value.strip()) == 1 and value.strip().upper() in OPTION_LETTERS:
            return OPTION_LETTERS.index(value.strip().upper())
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(OPTION_LETTERS):
            return value
        raise ValueError('selected_option must be a letter "A"-"D" or an index 0-3.')

    @model_validator(mode="after")
    def exactly_one_choice(self) -> "AnswerIn":
        if (self.option_id is None) == (self.selected_option is None):
            raise ValueError("Send exactly one of option_id or selected_option.")
        return self


class AnswerAck(BaseModel):
    """'Locked in' — deliberately says nothing about whether the answer is right."""
    success: bool = True
    message: str = "Answer locked in!"
    accepted: bool = True
    question_id: int
    option_id: int
    response_time_ms: int


# ── Scoring (admin / Dev 3 at reveal) ────────────────────────────────────────

class OptionCount(BaseModel):
    option_id: int
    count: int


class ScoreQuestionOut(BaseModel):
    game_id: int
    question_id: int
    correct_option_id: int
    distribution: list[OptionCount]
    answered: int
    correct: int
    already_scored: bool = Field(False, description="True if this question had been scored before; nothing changed.")


# ── Leaderboard (anyone: stage, host, players) ───────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    participant_id: int
    nickname: str
    display_name: str | None = None
    is_anonymous: bool = False
    is_certificate_eligible: bool = Field(False, description="True for top 3 participants.")
    score: int
    rank_delta: int = Field(..., description="Places climbed since the previous scoring (positive = up).")
    streak: int
    correct_count: int


class ClimberOut(BaseModel):
    participant_id: int
    nickname: str
    rank_delta: int


class CloseBattleOut(BaseModel):
    rank: int
    participant_ids: list[int]
    gap: int


class LeaderboardOut(BaseModel):
    game_id: int
    round_id: int | None = Field(None, description="Set when this is a per-round leaderboard.")
    total_participants: int
    scored_questions: int
    top: list[LeaderboardEntry]
    climbers: list[ClimberOut]
    close_battles: list[CloseBattleOut]


# ── My stats (participant) ───────────────────────────────────────────────────

class LastResult(BaseModel):
    question_id: int
    answered: bool
    is_correct: bool
    points: int


class MyStatsOut(BaseModel):
    participant_id: int
    nickname: str
    score: int
    rank: int | None
    rank_delta: int
    streak: int
    best_streak: int
    correct_count: int
    last_result: LastResult | None
