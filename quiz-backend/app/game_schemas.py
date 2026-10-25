"""
game_schemas.py — Request/response models for live games (Developer 2).

Kept apart from schemas.py (Developer 1) so the two files never conflict.

SECURITY: nothing a participant can call returns which option is correct before
the question has been scored. Correctness appears only in ScoreQuestionOut
(admin, after scoring) and in MyStatsOut.last_result (after scoring).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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
    nickname: str = Field(..., max_length=64, examples=["Rathi"])


class RejoinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=10, examples=["48291375"])
    token: str = Field(..., min_length=10, max_length=64)


class JoinOut(BaseModel):
    """Returned on join and rejoin. The phone stores `token` (localStorage) for rejoining."""
    game_id: int
    participant_id: int = Field(..., description="The player's id in this game (game_participants.id).")
    nickname: str
    token: str = Field(..., description="Send as the X-Participant-Token header on player endpoints.")
    game_status: str


# ── Current question (participant) ───────────────────────────────────────────

class CurrentQuestionOut(BaseModel):
    """The open question, WITHOUT correct answers, plus timing for the countdown."""
    question: ParticipantQuestionOut
    opened_at: datetime
    deadline: datetime
    server_time: datetime
    already_answered: bool


# ── Answers (participant) ────────────────────────────────────────────────────

class AnswerIn(BaseModel):
    question_id: int = Field(..., gt=0)
    option_id: int = Field(..., gt=0)


class AnswerAck(BaseModel):
    """'Locked in' — deliberately says nothing about whether the answer is right."""
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
