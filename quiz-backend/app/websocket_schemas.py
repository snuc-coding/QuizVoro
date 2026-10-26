"""
websocket_schemas.py — Pydantic models for WebSocket event messages and payloads.

Developer 3: Real-time communication protocol.
Ensures strict separation between admin, participant, and stage payloads.
CRITICAL: Correct answer is NEVER exposed in question broadcasting payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.game_schemas import LastResult, LeaderboardOut, OptionCount
from app.schemas import ParticipantQuestionOut


# ── Event Types ───────────────────────────────────────────────────────────────

class EventType(str, Enum):
    # Connection / System
    PING = "PING"
    PONG = "PONG"
    ERROR = "ERROR"

    # Lobby / Participants
    PLAYER_JOINED = "PLAYER_JOINED"
    PLAYER_LEFT = "PLAYER_LEFT"
    PLAYER_KICKED = "PLAYER_KICKED"

    # Game Lifecycle
    GET_READY = "GET_READY"
    QUESTION_STARTED = "QUESTION_STARTED"
    ANSWER_COUNT_UPDATED = "ANSWER_COUNT_UPDATED"
    GAME_PAUSED = "GAME_PAUSED"
    GAME_RESUMED = "GAME_RESUMED"
    ANSWER_REVEALED = "ANSWER_REVEALED"
    LEADERBOARD_UPDATED = "LEADERBOARD_UPDATED"
    GAME_FINISHED = "GAME_FINISHED"


# ── Generic Message Envelope ──────────────────────────────────────────────────

class WebSocketMessage(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary with ISO format timestamp."""
        payload = self.model_dump(mode="json")
        return payload


# ── Host Command Payloads ─────────────────────────────────────────────────────

class HostAction(str, Enum):
    START = "START"
    NEXT_QUESTION = "NEXT_QUESTION"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    REVEAL = "REVEAL"
    END = "END"
    KICK = "KICK"


class HostCommandIn(BaseModel):
    action: HostAction
    participant_id: int | None = Field(None, description="Target participant ID for KICK action.")


# ── Broadcast Payloads ────────────────────────────────────────────────────────

class PlayerJoinedPayload(BaseModel):
    participant_id: int
    nickname: str
    total_players: int


class PlayerLeftPayload(BaseModel):
    participant_id: int
    nickname: str | None = None
    total_players: int


class PlayerKickedPayload(BaseModel):
    participant_id: int
    reason: str = "Removed by host"


class GetReadyPayload(BaseModel):
    question_number: int
    total_questions: int
    seconds_remaining: int = 3


class QuestionStartPayload(BaseModel):
    """Broadcast to participants, stage, and host when a question goes live.
    Deliberately contains ParticipantQuestionOut which excludes `is_correct`.
    """
    question: ParticipantQuestionOut
    question_number: int
    total_questions: int
    opened_at: datetime
    deadline: datetime
    server_time: datetime
    time_limit: int


class AnswerCountPayload(BaseModel):
    question_id: int
    answered_count: int
    total_active_players: int


class PauseResumePayload(BaseModel):
    status: str  # "paused" | "active"
    remaining_seconds: float | None = None
    deadline: datetime | None = None
    server_time: datetime


class AnswerRevealPayload(BaseModel):
    game_id: int
    question_id: int
    correct_option_id: int
    distribution: list[OptionCount]
    answered: int
    correct: int
    already_scored: bool = False


class PlayerPersonalResultPayload(BaseModel):
    participant_id: int
    nickname: str
    score: int
    rank: int | None
    rank_delta: int
    streak: int
    last_result: LastResult | None


class StageTokenOut(BaseModel):
    game_id: int
    stage_token: str
    expires_in_hours: int = 24
