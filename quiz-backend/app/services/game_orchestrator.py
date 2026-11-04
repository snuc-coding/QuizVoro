"""
game_orchestrator.py — Game lifecycle state orchestration and authorized host controls.

Developer 3: Real-time game orchestrator.
Manages state machine transitions:
  lobby -> active (question open) <-> paused -> reveal (scored) -> next_question / finished.

Reuses:
  - participant_service: get_game_for_admin, active_players, get_participant_by_token
  - answer_service: score_question, ordered_options, participant_question, _quiz_question_ids
  - leaderboard_service: get_leaderboard, my_stats

Threading rule: the async methods here never touch the database themselves.
Each host action does all of its database work in one run_db call (a worker
thread) that returns plain payloads, then broadcasts them on the event loop.
A blocking query on the loop stalls every socket on the server.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
import jwt
from sqlalchemy.orm import Session

from app import scoring
from app.config import get_settings
from app.database import SessionLocal, run_db
from app.game_schemas import GameOut, ScoreQuestionOut
from app.models import Admin, Answer, Game, GameParticipant, Question, Round, ScoredQuestion
from app.security import decode_access_token
from app.services import answer_service, leaderboard_service, participant_service
from app.services.connection_manager import manager
from app.websocket_schemas import (
    AnswerCountPayload,
    AnswerRevealPayload,
    EventType,
    PauseResumePayload,
    PlayerJoinedPayload,
    PlayerLeftPayload,
    PlayerPersonalResultPayload,
    QuestionStartPayload,
    WebSocketMessage,
)

settings = get_settings()
logger = logging.getLogger("quizvoro.game_timer")

# In-memory locks per game to prevent race conditions across concurrent operations
_game_locks: dict[int, asyncio.Lock] = {}
# In-memory paused_at tracker: game_id -> datetime (UTC)
_paused_times: dict[int, datetime] = {}
_deadline_tasks: dict[int, asyncio.Task] = {}

# "How many have answered" updates: game_id -> question_id still to announce,
# and the one task per game that sends them. A burst of answers becomes one
# update every ANSWER_COUNT_DELAY_S instead of one per answer.
_count_pending: dict[int, int] = {}
_count_tasks: dict[int, asyncio.Task] = {}
ANSWER_COUNT_DELAY_S = 0.3


def _get_game_lock(game_id: int) -> asyncio.Lock:
    if game_id not in _game_locks:
        _game_locks[game_id] = asyncio.Lock()
    return _game_locks[game_id]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_game_for_admin(db: Session, game_id: int, admin: Admin) -> Game:
    """Lock and refresh game state before a host transition changes it."""
    participant_service.get_game_for_admin(db, game_id, admin)
    return (
        db.query(Game)
        .filter(Game.id == game_id)
        .populate_existing()
        .with_for_update()
        .one()
    )


def _active_admin(db: Session, admin_id: int) -> Admin:
    admin = db.get(Admin, admin_id)
    if not admin or not admin.is_active:
        raise ValueError("Admin account disabled or not found")
    return admin


@dataclass(frozen=True)
class _Timer:
    """The open question whose deadline the auto-reveal waits for."""
    question_id: int
    opened_at: datetime
    deadline: datetime


def _timer_for(game: Game, question: Question | None) -> _Timer | None:
    if question is None or game.status != "active" or game.current_question_started_at is None:
        return None
    opened_at = scoring.as_utc(game.current_question_started_at)
    return _Timer(question.id, opened_at, opened_at + timedelta(seconds=question.time_limit))


@dataclass
class _Transition:
    """What a host action's database step hands back to the event loop."""
    game: GameOut
    message: dict[str, Any] | None = None
    timer: _Timer | None = None


@dataclass
class _Reveal:
    result: ScoreQuestionOut
    reveal_message: dict[str, Any]
    personal_messages: dict[int, dict[str, Any]] = field(default_factory=dict)
    board_message: dict[str, Any] | None = None


def _question_started_message(question: Question, number: int, total: int, now: datetime) -> dict[str, Any]:
    """QUESTION_STARTED, with the sanitized question (NEVER includes is_correct)."""
    q_payload = QuestionStartPayload(
        question=answer_service.participant_question(question),
        question_number=number,
        total_questions=total,
        opened_at=now,
        deadline=now + timedelta(seconds=question.time_limit),
        server_time=now,
        time_limit=question.time_limit,
    )
    return WebSocketMessage(
        event=EventType.QUESTION_STARTED.value,
        data=q_payload.model_dump(mode="json"),
    ).to_json_dict()


def _game_finished_message(db: Session, game: Game, limit: int) -> dict[str, Any]:
    board = leaderboard_service.get_leaderboard(db, game, limit=limit)
    return WebSocketMessage(
        event=EventType.GAME_FINISHED.value,
        data={"game_id": game.id, "status": "finished", "leaderboard": board.model_dump(mode="json")},
    ).to_json_dict()


# ── Stage Display Cryptographic Token Helpers ─────────────────────────────────

def create_stage_token(game_id: int) -> str:
    """Generate a cryptographically signed token for the stage display."""
    expire = _now() + timedelta(hours=24)
    payload = {
        "sub": f"stage:{game_id}",
        "game_id": game_id,
        "role": "stage",
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_stage_token(token: str, game_id: int) -> bool:
    """Validate that the token was signed by our secret, has role 'stage', and matches game_id."""
    if not token:
        return False
    try:
        payload = decode_access_token(token)
        return payload.get("role") == "stage" and payload.get("game_id") == game_id
    except Exception:
        return False


# ── Game Orchestrator Logic ───────────────────────────────────────────────────

class GameOrchestrator:
    """State transition orchestrator for live quiz sessions."""

    @staticmethod
    def get_quiz_question_ids(db: Session, quiz_id: int) -> list[int]:
        """All questions in the quiz, in order: round_number, then question_order."""
        return [
            qid
            for (qid,) in db.query(Question.id)
            .join(Round, Round.id == Question.round_id)
            .filter(Round.quiz_id == quiz_id)
            .order_by(Round.round_number, Question.question_order)
        ]

    @classmethod
    def game_state_snapshot(cls, db: Session, game_id: int) -> dict[str, Any]:
        """Build a reconnect snapshot shared by the host and sanitized stage. Sync: call via run_db."""
        game = participant_service.get_game_by_id(db, game_id)
        now = _now()
        question = db.get(Question, game.current_question_id) if game.current_question_id else None
        question_ids = cls.get_quiz_question_ids(db, game.quiz_id)
        players = participant_service.active_players(db, game.id)
        player_rows = [
            {
                "participant_id": player.id,
                "nickname": player.display_name or player.participant.nickname,
                "display_name": player.display_name or player.participant.nickname,
                "is_anonymous": player.is_anonymous,
            }
            for player in players
        ]

        current_question = None
        question_number = None
        deadline = None
        remaining_seconds = None
        answered_count = 0
        revealed_data = None
        snapshot_status = game.status

        if question is not None:
            current_question = answer_service.participant_question(question).model_dump(mode="json")
            question_number = question_ids.index(question.id) + 1 if question.id in question_ids else None
            answered_count = db.query(Answer.id).filter(
                Answer.game_id == game.id,
                Answer.question_id == question.id,
            ).count()

            scored = db.query(ScoredQuestion.id).filter(
                ScoredQuestion.game_id == game.id,
                ScoredQuestion.question_id == question.id,
            ).first() is not None
            if scored:
                # Read-only: a reconnecting stage or refreshed host must never
                # take the game's FOR UPDATE lock just to show a result.
                revealed_data = answer_service._result(
                    db, game.id, question, already_scored=True
                ).model_dump(mode="json")
                if game.status != "finished":
                    snapshot_status = "reveal"

            if game.current_question_started_at is not None:
                opened_at = scoring.as_utc(game.current_question_started_at)
                deadline = opened_at + timedelta(seconds=question.time_limit)
                if game.status == "paused":
                    paused_at = scoring.as_utc(game.updated_at) if game.updated_at else now
                    remaining_seconds = max(0.0, question.time_limit - (paused_at - opened_at).total_seconds())
                elif game.status == "active":
                    remaining_seconds = max(0.0, (deadline - now).total_seconds())

        leaderboard = None
        if snapshot_status in ("reveal", "finished"):
            leaderboard = leaderboard_service.get_leaderboard(db, game, limit=5).model_dump(mode="json")

        return {
            "game_id": game.id,
            "pin": game.pin,
            "game_status": snapshot_status,
            "players": player_rows,
            "total_active_players": len(player_rows),
            "current_question": current_question,
            "question_number": question_number or 1,
            "total_questions": len(question_ids),
            "deadline": deadline.isoformat() if deadline else None,
            "server_time": now.isoformat(),
            "remaining_seconds": remaining_seconds,
            "answered_count": answered_count,
            "revealed_data": revealed_data,
            "leaderboard": leaderboard,
        }

    @classmethod
    async def run_host_action(cls, game_id: int, admin_id: int, action, *args):
        """
        Run a host action with its own session, for callers without a request
        session (the host WebSocket and the deadline timer).
        """
        db = SessionLocal()  # no connection until first use, which happens in a worker thread
        try:
            admin = await run_db(_active_admin, admin_id, db=db)
            return await action(db, game_id, admin, *args)
        finally:
            await run_in_threadpool(db.close)

    # ── Deadline timer ────────────────────────────────────────────────────────

    @classmethod
    def _cancel_deadline(cls, game_id: int) -> None:
        task = _deadline_tasks.pop(game_id, None)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()

    @classmethod
    def _schedule_deadline(cls, game_id: int, timer: _Timer | None) -> None:
        cls._cancel_deadline(game_id)
        if timer is None:
            return
        _deadline_tasks[game_id] = asyncio.create_task(cls._reveal_at_deadline(game_id, timer))

    @staticmethod
    def _open_question_timer(db: Session, game_id: int) -> _Timer | None:
        game = participant_service.get_game_by_id(db, game_id)
        if not game.current_question_id:
            return None
        return _timer_for(game, db.get(Question, game.current_question_id))

    @classmethod
    async def ensure_deadline_timer(cls, game_id: int) -> None:
        """Re-arm an active question timer after a server process restart."""
        timer = await run_db(cls._open_question_timer, game_id)
        if timer is None:
            cls._cancel_deadline(game_id)
            return
        task = _deadline_tasks.get(game_id)
        if task and not task.done():
            return
        cls._schedule_deadline(game_id, timer)

    @staticmethod
    def _host_admin_id(db: Session, game_id: int) -> int | None:
        game = db.get(Game, game_id)
        return game.quiz.admin_id if game is not None else None

    @classmethod
    async def _reveal_at_deadline(cls, game_id: int, timer: _Timer) -> None:
        try:
            grace_seconds = scoring.ANSWER_GRACE_MS / 1000
            await asyncio.sleep(max(0.0, (timer.deadline - _now()).total_seconds()) + grace_seconds)
            admin_id = await run_db(cls._host_admin_id, game_id)
            if admin_id is None:
                return
            # reveal_answer re-checks, under the game lock, that this exact
            # question is still open, so a host action racing the timer wins.
            await cls.run_host_action(game_id, admin_id, cls.reveal_answer, timer)
        except asyncio.CancelledError:
            raise
        except ValueError:
            logger.warning("Could not auto-reveal game %s: host admin is unavailable", game_id)
        except Exception:
            logger.exception("Automatic answer reveal failed for game %s, question %s", game_id, timer.question_id)
        finally:
            if _deadline_tasks.get(game_id) is asyncio.current_task():
                _deadline_tasks.pop(game_id, None)

    # ── Lobby and answer-count broadcasts ─────────────────────────────────────

    @staticmethod
    async def broadcast_player_joined(
        game_id: int,
        participant_id: int,
        nickname: str,
        total: int,
        is_anonymous: bool = False,
    ):
        msg = WebSocketMessage(
            event=EventType.PLAYER_JOINED.value,
            data=PlayerJoinedPayload(
                participant_id=participant_id,
                nickname=nickname,
                display_name=nickname,
                is_anonymous=is_anonymous,
                total_players=total,
            ).model_dump(mode="json"),
        )
        await manager.broadcast_to_role(game_id, "host", msg)
        await manager.broadcast_to_role(game_id, "stage", msg)

    @staticmethod
    async def broadcast_player_left(
        game_id: int,
        participant_id: int,
        total: int,
        nickname: str | None = None,
        is_anonymous: bool = False,
    ):
        msg = WebSocketMessage(
            event=EventType.PLAYER_LEFT.value,
            data=PlayerLeftPayload(
                participant_id=participant_id,
                nickname=nickname,
                display_name=nickname,
                is_anonymous=is_anonymous,
                total_players=total,
            ).model_dump(mode="json"),
        )
        await manager.broadcast_to_role(game_id, "host", msg)
        await manager.broadcast_to_role(game_id, "stage", msg)

    @classmethod
    def request_answer_count(cls, game_id: int, question_id: int) -> None:
        """
        Tell host and stage the new answer count soon. Call on the event loop
        after every accepted answer (HTTP or WebSocket). Answers that arrive
        while an update is being sent trigger one more, so the last answer of
        a question is always counted.
        """
        _count_pending[game_id] = question_id
        task = _count_tasks.get(game_id)
        if task is not None and not task.done():
            return
        _count_tasks[game_id] = asyncio.create_task(cls._send_answer_count_soon(game_id))

    @classmethod
    async def _send_answer_count_soon(cls, game_id: int) -> None:
        try:
            while game_id in _count_pending:
                await asyncio.sleep(ANSWER_COUNT_DELAY_S)
                await cls.broadcast_answer_count(game_id, _count_pending.pop(game_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Answer count update failed for game %s", game_id)

    @staticmethod
    def _answer_counts(db: Session, game_id: int, question_id: int) -> tuple[int, int]:
        answered = (
            db.query(Answer.id)
            .filter(Answer.game_id == game_id, Answer.question_id == question_id)
            .count()
        )
        return answered, participant_service.active_player_count(db, game_id)

    @classmethod
    async def broadcast_answer_count(cls, game_id: int, question_id: int):
        answered_count, active_count = await run_db(cls._answer_counts, game_id, question_id)
        msg = WebSocketMessage(
            event=EventType.ANSWER_COUNT_UPDATED.value,
            data=AnswerCountPayload(
                question_id=question_id,
                answered_count=answered_count,
                total_active_players=active_count,
            ).model_dump(mode="json"),
        )
        await manager.broadcast_to_role(game_id, "host", msg)
        await manager.broadcast_to_role(game_id, "stage", msg)

    # ── Host actions ──────────────────────────────────────────────────────────
    # Each async method takes the per-game lock, runs its _..._db step in a
    # worker thread, then broadcasts what that step returned.

    @classmethod
    def _start_game_db(cls, db: Session, game_id: int, admin: Admin) -> _Transition:
        game = _lock_game_for_admin(db, game_id, admin)
        if game.status != "lobby":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot start game in '{game.status}' status. Must be in 'lobby'.",
            )

        question_ids = cls.get_quiz_question_ids(db, game.quiz_id)
        if not question_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Add at least one question before starting a game.",
            )

        question = db.get(Question, question_ids[0])
        now = _now()
        game.status = "active"
        game.current_question_id = question.id
        game.current_question_started_at = now
        db.commit()
        db.refresh(game)
        return _Transition(
            game=GameOut.model_validate(game),
            message=_question_started_message(question, 1, len(question_ids), now),
            timer=_timer_for(game, question),
        )

    @classmethod
    async def start_game(cls, db: Session, game_id: int, admin: Admin) -> GameOut:
        """Start the live quiz: transition from lobby to active with Question 1."""
        async with _get_game_lock(game_id):
            out = await run_db(cls._start_game_db, game_id, admin, db=db)
            await manager.broadcast_to_game(game_id, out.message)
            cls._schedule_deadline(game_id, out.timer)
            return out.game

    @classmethod
    def _next_question_db(cls, db: Session, game_id: int, admin: Admin) -> _Transition:
        game = _lock_game_for_admin(db, game_id, admin)
        if game.status not in ("active", "paused"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot advance question when game status is '{game.status}'.",
            )

        question_ids = cls.get_quiz_question_ids(db, game.quiz_id)
        if not game.current_question_id or game.current_question_id not in question_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Current question is not set or invalid.",
            )

        if not db.query(ScoredQuestion.id).filter(
            ScoredQuestion.game_id == game.id,
            ScoredQuestion.question_id == game.current_question_id,
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reveal and score the current question before advancing.",
            )

        current_idx = question_ids.index(game.current_question_id)
        if current_idx + 1 >= len(question_ids):
            # No more questions -> End game
            game.status = "finished"
            db.commit()
            db.refresh(game)
            return _Transition(game=GameOut.model_validate(game), message=_game_finished_message(db, game, limit=10))

        question = db.get(Question, question_ids[current_idx + 1])
        now = _now()
        game.status = "active"
        game.current_question_id = question.id
        game.current_question_started_at = now
        _paused_times.pop(game_id, None)
        db.commit()
        db.refresh(game)
        return _Transition(
            game=GameOut.model_validate(game),
            message=_question_started_message(question, current_idx + 2, len(question_ids), now),
            timer=_timer_for(game, question),
        )

    @classmethod
    async def next_question(cls, db: Session, game_id: int, admin: Admin) -> GameOut:
        """Advance to the next question in sequence, or finish the game if at the end."""
        async with _get_game_lock(game_id):
            out = await run_db(cls._next_question_db, game_id, admin, db=db)
            cls._cancel_deadline(game_id)
            await manager.broadcast_to_game(game_id, out.message)
            cls._schedule_deadline(game_id, out.timer)
            return out.game

    @staticmethod
    def _pause_game_db(db: Session, game_id: int, admin: Admin) -> _Transition:
        game = _lock_game_for_admin(db, game_id, admin)
        if game.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot pause game with status '{game.status}'. Must be 'active'.",
            )

        question = db.get(Question, game.current_question_id) if game.current_question_id else None
        now = _now()
        _paused_times[game_id] = now
        game.status = "paused"
        db.commit()
        db.refresh(game)

        remaining_sec = None
        if question and game.current_question_started_at:
            started_at = scoring.as_utc(game.current_question_started_at)
            elapsed = (now - started_at).total_seconds()
            remaining_sec = max(0.0, float(question.time_limit) - elapsed)

        payload = PauseResumePayload(
            status="paused",
            remaining_seconds=remaining_sec,
            deadline=None,
            server_time=now,
        )
        msg = WebSocketMessage(event=EventType.GAME_PAUSED.value, data=payload.model_dump(mode="json"))
        return _Transition(game=GameOut.model_validate(game), message=msg.to_json_dict())

    @classmethod
    async def pause_game(cls, db: Session, game_id: int, admin: Admin) -> GameOut:
        """Pause the game: halts question countdown and records pause timestamp."""
        async with _get_game_lock(game_id):
            out = await run_db(cls._pause_game_db, game_id, admin, db=db)
            cls._cancel_deadline(game_id)
            await manager.broadcast_to_game(game_id, out.message)
            return out.game

    @staticmethod
    def _resume_game_db(db: Session, game_id: int, admin: Admin) -> _Transition:
        game = _lock_game_for_admin(db, game_id, admin)
        if game.status != "paused":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resume game with status '{game.status}'. Must be 'paused'.",
            )

        now = _now()
        raw_paused_at = _paused_times.pop(game_id, None) or game.updated_at or now
        paused_at = scoring.as_utc(raw_paused_at)

        # Preserve remaining question time by shifting started_at forward
        paused_duration = now - paused_at
        if game.current_question_started_at:
            started_at = scoring.as_utc(game.current_question_started_at)
            game.current_question_started_at = started_at + paused_duration

        game.status = "active"
        db.commit()
        db.refresh(game)

        question = db.get(Question, game.current_question_id) if game.current_question_id else None
        timer = _timer_for(game, question)
        payload = PauseResumePayload(
            status="active",
            remaining_seconds=max(0.0, (timer.deadline - now).total_seconds()) if timer else None,
            deadline=timer.deadline if timer else None,
            server_time=now,
        )
        msg = WebSocketMessage(event=EventType.GAME_RESUMED.value, data=payload.model_dump(mode="json"))
        return _Transition(game=GameOut.model_validate(game), message=msg.to_json_dict(), timer=timer)

    @classmethod
    async def resume_game(cls, db: Session, game_id: int, admin: Admin) -> GameOut:
        """Resume a paused game: shifts question start forward by paused duration."""
        async with _get_game_lock(game_id):
            out = await run_db(cls._resume_game_db, game_id, admin, db=db)
            await manager.broadcast_to_game(game_id, out.message)
            cls._schedule_deadline(game_id, out.timer)
            return out.game

    @staticmethod
    def _reveal_answer_db(db: Session, game_id: int, admin: Admin, only_if: _Timer | None) -> _Reveal | None:
        game = _lock_game_for_admin(db, game_id, admin)
        if only_if is not None and _timer_for(
            game, db.get(Question, game.current_question_id) if game.current_question_id else None
        ) != only_if:
            return None  # the timer's question was already revealed, paused or moved on
        if not game.current_question_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No question is currently open to reveal.",
            )

        # Reuses Developer 2's answer_service.score_question (safe to call twice)
        question_id = game.current_question_id
        result = answer_service.score_question(db, game, question_id)
        board = leaderboard_service.get_leaderboard(db, game, limit=5)

        reveal_payload = AnswerRevealPayload(
            game_id=game_id,
            question_id=question_id,
            correct_option_id=result.correct_option_id,
            distribution=result.distribution,
            answered=result.answered,
            correct=result.correct,
            already_scored=result.already_scored,
        ).model_dump(mode="json")

        # Each player's own result, built here so no per-player work runs on the loop.
        players = participant_service.active_players(db, game_id)
        all_stats = leaderboard_service.stats_for_all(db, game, players)  # one pass, not one per player
        personal: dict[int, dict[str, Any]] = {}
        for player in players:
            stats = all_stats[player.id]
            player_name = player.display_name or player.participant.nickname
            personal_payload = PlayerPersonalResultPayload(
                participant_id=player.id,
                nickname=player_name,
                display_name=player_name,
                is_anonymous=player.is_anonymous,
                score=stats.score,
                rank=stats.rank,
                rank_delta=stats.rank_delta,
                streak=stats.streak,
                last_result=stats.last_result,
            )
            personal[player.id] = WebSocketMessage(
                event=EventType.ANSWER_REVEALED.value,
                data={**reveal_payload, "my_stats": personal_payload.model_dump(mode="json")},
            ).to_json_dict()

        return _Reveal(
            result=result,
            reveal_message=WebSocketMessage(event=EventType.ANSWER_REVEALED.value, data=reveal_payload).to_json_dict(),
            personal_messages=personal,
            board_message=WebSocketMessage(
                event=EventType.LEADERBOARD_UPDATED.value,
                data=board.model_dump(mode="json"),
            ).to_json_dict(),
        )

    @classmethod
    async def reveal_answer(
        cls, db: Session, game_id: int, admin: Admin, only_if: _Timer | None = None
    ) -> ScoreQuestionOut | None:
        """
        Score the question at reveal and broadcast results and updated leaderboard.

        only_if is for the deadline timer: reveal only if that exact question
        opening is still running, otherwise do nothing and return None.
        """
        async with _get_game_lock(game_id):
            out = await run_db(cls._reveal_answer_db, game_id, admin, only_if, db=db)
            if out is None:
                return None
            cls._cancel_deadline(game_id)

            # 1. Correct option & distribution to Stage and Host
            await manager.broadcast_to_role(game_id, "host", out.reveal_message)
            await manager.broadcast_to_role(game_id, "stage", out.reveal_message)
            # 2. Personalized results to every participant at once
            await manager.send_to_participants(game_id, out.personal_messages)
            # 3. Updated leaderboard to all
            await manager.broadcast_to_game(game_id, out.board_message)
            return out.result

    @staticmethod
    def _end_game_db(db: Session, game_id: int, admin: Admin) -> _Transition:
        game = _lock_game_for_admin(db, game_id, admin)
        game.status = "finished"
        db.commit()
        db.refresh(game)
        return _Transition(game=GameOut.model_validate(game), message=_game_finished_message(db, game, limit=5))

    @classmethod
    async def end_game(cls, db: Session, game_id: int, admin: Admin) -> GameOut:
        """End the game session manually."""
        async with _get_game_lock(game_id):
            out = await run_db(cls._end_game_db, game_id, admin, db=db)
            cls._cancel_deadline(game_id)
            await manager.broadcast_to_game(game_id, out.message)
            return out.game

    @staticmethod
    def _kick_participant_db(
        db: Session, game_id: int, admin: Admin, participant_id: int
    ) -> tuple[int, str, int]:
        game = _lock_game_for_admin(db, game_id, admin)
        membership = (
            db.query(GameParticipant)
            .filter(GameParticipant.game_id == game.id, GameParticipant.id == participant_id)
            .first()
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Participant with ID {participant_id} not found in this game.",
            )

        membership.is_active = False
        db.commit()
        return membership.id, membership.participant.nickname, participant_service.active_player_count(db, game_id)

    @classmethod
    async def kick_participant(
        cls, db: Session, game_id: int, admin: Admin, participant_id: int
    ) -> None:
        """Kick an active player: deactivates in DB and disconnects their sockets."""
        async with _get_game_lock(game_id):
            membership_id, nickname, total_active = await run_db(
                cls._kick_participant_db, game_id, admin, participant_id, db=db
            )
            # Disconnect WebSockets for this participant
            await manager.kick_participant(game_id, membership_id, reason="Removed by host")
            # Broadcast updated player count
            await cls.broadcast_player_left(game_id, membership_id, total_active, nickname)


orchestrator = GameOrchestrator()
