"""
game_orchestrator.py — Game lifecycle state orchestration and authorized host controls.

Developer 3: Real-time game orchestrator.
Manages state machine transitions:
  lobby -> active (question open) <-> paused -> reveal (scored) -> next_question / finished.

Reuses:
  - participant_service: get_game_for_admin, active_players, get_participant_by_token
  - answer_service: score_question, ordered_options, participant_question, _quiz_question_ids
  - leaderboard_service: get_leaderboard, my_stats
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
import jwt
from sqlalchemy.orm import Session, selectinload

from app import scoring
from app.config import get_settings
from app.database import SessionLocal
from app.game_schemas import LeaderboardOut, ScoreQuestionOut
from app.models import Admin, Answer, Game, GameParticipant, Question, Round, ScoredQuestion
from app.schemas import ParticipantQuestionOut
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

# Pending "how many have answered" updates for answers sent over HTTP (one per game at a time).
_count_tasks: dict[int, asyncio.Task] = {}
ANSWER_COUNT_DELAY_S = 0.3


def _get_game_lock(game_id: int) -> asyncio.Lock:
    if game_id not in _game_locks:
        _game_locks[game_id] = asyncio.Lock()
    return _game_locks[game_id]


@asynccontextmanager
async def _host_action(db: Session | None, game_id: int):
    """
    One host action at a time per game. Synchronous transaction work is run by
    _run_db in a worker thread and rolled back before the lock is released.
    """
    async with _get_game_lock(game_id):
        yield


def _run_db(db: Session | None, fn, *args):
    """Run one complete synchronous DB unit; timer tasks own a short session."""
    def execute(session: Session):
        try:
            result = fn(session, *args)
            # End any read transaction opened while building the return payload
            # before the event loop starts broadcasting it to many sockets.
            session.commit()
            return result
        except BaseException:
            session.rollback()
            raise

    if db is not None:
        return execute(db)
    with SessionLocal() as session:
        return execute(session)


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
        """Build a reconnect snapshot shared by the host and sanitized stage."""
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
    def _cancel_deadline(cls, game_id: int) -> None:
        task = _deadline_tasks.pop(game_id, None)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()

    @classmethod
    def _schedule_deadline(cls, game_id: int, question_id: int, opened_at: datetime, time_limit: int) -> None:
        cls._cancel_deadline(game_id)
        deadline = opened_at + timedelta(seconds=time_limit)
        task = asyncio.create_task(cls._reveal_at_deadline(game_id, question_id, opened_at, deadline))
        _deadline_tasks[game_id] = task

    @classmethod
    async def ensure_deadline_timer(cls, game_id: int) -> None:
        """Re-arm an active question timer after a server process restart."""
        def timer_state(db: Session):
            game = participant_service.get_game_by_id(db, game_id)
            if game.status != "active" or not game.current_question_id or game.current_question_started_at is None:
                return None
            question = db.get(Question, game.current_question_id)
            if question is None:
                return None
            return game.id, question.id, scoring.as_utc(game.current_question_started_at), question.time_limit

        state = await run_in_threadpool(_run_db, None, timer_state)
        task = _deadline_tasks.get(game_id)
        if state is None:
            cls._cancel_deadline(game_id)
            return
        if task and not task.done():
            return
        cls._schedule_deadline(*state)

    @classmethod
    async def _reveal_at_deadline(
        cls, game_id: int, question_id: int, opened_at: datetime, deadline: datetime
    ) -> None:
        try:
            grace_seconds = scoring.ANSWER_GRACE_MS / 1000
            await asyncio.sleep(max(0.0, (deadline - _now()).total_seconds()) + grace_seconds)
            def current_admin_id(db: Session):
                game = db.get(Game, game_id)
                if (
                    game is None
                    or game.status != "active"
                    or game.current_question_id != question_id
                    or game.current_question_started_at is None
                    or scoring.as_utc(game.current_question_started_at) != opened_at
                ):
                    return None

                admin = db.get(Admin, game.quiz.admin_id)
                if admin is None or not admin.is_active:
                    logger.warning("Could not auto-reveal game %s: host admin is unavailable", game_id)
                    return None
                return admin.id

            admin_id = await run_in_threadpool(_run_db, None, current_admin_id)
            if admin_id is not None:
                admin_ref = type("AdminRef", (), {"id": admin_id, "is_active": True})()
                await cls.reveal_answer(None, game_id, admin_ref)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic answer reveal failed for game %s, question %s", game_id, question_id)
        finally:
            if _deadline_tasks.get(game_id) is asyncio.current_task():
                _deadline_tasks.pop(game_id, None)

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
        Tell host and stage the new answer count soon, for answers sent over HTTP
        (the phones' POST /answers). A burst of answers becomes one update every
        ANSWER_COUNT_DELAY_S instead of one per answer. Call on the event loop.
        """
        task = _count_tasks.get(game_id)
        if task is not None and not task.done():
            return
        _count_tasks[game_id] = asyncio.create_task(cls._send_answer_count_soon(game_id, question_id))

    @classmethod
    async def _send_answer_count_soon(cls, game_id: int, question_id: int) -> None:
        try:
            await asyncio.sleep(ANSWER_COUNT_DELAY_S)
            await cls.broadcast_answer_count(game_id, question_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Answer count update failed for game %s", game_id)

    @classmethod
    async def broadcast_answer_count(cls, game_id: int, question_id: int):
        from app.models import Answer

        def counts(db: Session):
            active_count = (
                db.query(GameParticipant.id)
                .filter(GameParticipant.game_id == game_id, GameParticipant.is_active.is_(True))
                .count()
            )
            answered_count = db.query(Answer.id).filter(
                Answer.game_id == game_id, Answer.question_id == question_id
            ).count()
            return active_count, answered_count

        active_count, answered_count = await run_in_threadpool(_run_db, None, counts)
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

    @classmethod
    async def start_game(cls, db: Session | None, game_id: int, admin: Admin) -> Game:
        """Start the live quiz: transition from lobby to active with Question 1."""
        async with _host_action(db, game_id):
            def work(session: Session):
                action_admin = session.get(Admin, admin.id)
                game = _lock_game_for_admin(session, game_id, action_admin)
                if game.status != "lobby":
                    raise HTTPException(status_code=409, detail=f"Cannot start game in '{game.status}' status. Must be in 'lobby'.")
                question_ids = cls.get_quiz_question_ids(session, game.quiz_id)
                if not question_ids:
                    raise HTTPException(status_code=409, detail="Add at least one question before starting a game.")
                question_id = question_ids[0]
                question = session.get(Question, question_id)
                opened_at = _now()
                game.status = "active"
                game.current_question_id = question_id
                game.current_question_started_at = opened_at
                session.commit()
                session.refresh(game)
                deadline = opened_at + timedelta(seconds=question.time_limit)
                payload = QuestionStartPayload(
                    question=answer_service.participant_question(question),
                    question_number=1,
                    total_questions=len(question_ids),
                    opened_at=opened_at,
                    deadline=deadline,
                    server_time=opened_at,
                    time_limit=question.time_limit,
                )
                msg = WebSocketMessage(event=EventType.QUESTION_STARTED.value, data=payload.model_dump(mode="json"))
                return game, msg, (question_id, opened_at, question.time_limit)

            game, msg, timer = await run_in_threadpool(_run_db, db, work)
            await manager.broadcast_to_game(game_id, msg)
            cls._schedule_deadline(game_id, *timer)
            return game

    @classmethod
    async def next_question(cls, db: Session | None, game_id: int, admin: Admin) -> Game:
        """Advance to the next question in sequence, or finish the game if at the end."""
        async with _host_action(db, game_id):
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                if game.status not in ("active", "paused"):
                    raise HTTPException(status_code=409, detail=f"Cannot advance question when game status is '{game.status}'.")
                question_ids = cls.get_quiz_question_ids(session, game.quiz_id)
                if not game.current_question_id or game.current_question_id not in question_ids:
                    raise HTTPException(status_code=409, detail="Current question is not set or invalid.")
                if not session.query(ScoredQuestion.id).filter(
                    ScoredQuestion.game_id == game.id,
                    ScoredQuestion.question_id == game.current_question_id,
                ).first():
                    raise HTTPException(status_code=409, detail="Reveal and score the current question before advancing.")
                current_idx = question_ids.index(game.current_question_id)
                if current_idx + 1 >= len(question_ids):
                    game.status = "finished"
                    session.commit()
                    session.refresh(game)
                    board = leaderboard_service.get_leaderboard(session, game, limit=10)
                    msg = WebSocketMessage(
                        event=EventType.GAME_FINISHED.value,
                        data={"game_id": game.id, "status": "finished", "leaderboard": board.model_dump(mode="json")},
                    )
                    return game, msg, None
                question_id = question_ids[current_idx + 1]
                question = session.get(Question, question_id)
                opened_at = _now()
                game.status = "active"
                game.current_question_id = question_id
                game.current_question_started_at = opened_at
                session.commit()
                session.refresh(game)
                payload = QuestionStartPayload(
                    question=answer_service.participant_question(question),
                    question_number=current_idx + 2,
                    total_questions=len(question_ids),
                    opened_at=opened_at,
                    deadline=opened_at + timedelta(seconds=question.time_limit),
                    server_time=opened_at,
                    time_limit=question.time_limit,
                )
                msg = WebSocketMessage(event=EventType.QUESTION_STARTED.value, data=payload.model_dump(mode="json"))
                return game, msg, (question_id, opened_at, question.time_limit)

            game, msg, timer = await run_in_threadpool(_run_db, db, work)
            cls._cancel_deadline(game_id)
            _paused_times.pop(game_id, None)
            await manager.broadcast_to_game(game_id, msg)
            if timer is not None:
                cls._schedule_deadline(game_id, *timer)
            return game

    @classmethod
    async def pause_game(cls, db: Session | None, game_id: int, admin: Admin) -> Game:
        """Pause the game: halts question countdown and records pause timestamp."""
        async with _host_action(db, game_id):
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                if game.status != "active":
                    raise HTTPException(status_code=409, detail=f"Cannot pause game with status '{game.status}'. Must be 'active'.")
                question = session.get(Question, game.current_question_id) if game.current_question_id else None
                now = _now()
                remaining = None
                if question and game.current_question_started_at:
                    started_at = scoring.as_utc(game.current_question_started_at)
                    remaining = max(0.0, float(question.time_limit) - (now - started_at).total_seconds())
                game.status = "paused"
                session.commit()
                session.refresh(game)
                payload = PauseResumePayload(status="paused", remaining_seconds=remaining, deadline=None, server_time=now)
                msg = WebSocketMessage(event=EventType.GAME_PAUSED.value, data=payload.model_dump(mode="json"))
                return game, msg, now

            game, msg, paused_at = await run_in_threadpool(_run_db, db, work)
            cls._cancel_deadline(game_id)
            _paused_times[game_id] = paused_at
            await manager.broadcast_to_game(game_id, msg)
            return game

    @classmethod
    async def resume_game(cls, db: Session | None, game_id: int, admin: Admin) -> Game:
        """Resume a paused game: shifts question start forward by paused duration."""
        async with _host_action(db, game_id):
            raw_paused_at = _paused_times.get(game_id)
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                if game.status != "paused":
                    raise HTTPException(status_code=409, detail=f"Cannot resume game with status '{game.status}'. Must be 'paused'.")
                now = _now()
                paused_at = scoring.as_utc(raw_paused_at or game.updated_at or now)
                if game.current_question_started_at:
                    game.current_question_started_at = scoring.as_utc(game.current_question_started_at) + (now - paused_at)
                game.status = "active"
                session.commit()
                session.refresh(game)
                question = session.get(Question, game.current_question_id) if game.current_question_id else None
                timer = None
                deadline = remaining = None
                if question and game.current_question_started_at:
                    opened_at = scoring.as_utc(game.current_question_started_at)
                    deadline = opened_at + timedelta(seconds=question.time_limit)
                    remaining = max(0.0, (deadline - now).total_seconds())
                    timer = (question.id, opened_at, question.time_limit)
                payload = PauseResumePayload(status="active", remaining_seconds=remaining, deadline=deadline, server_time=now)
                msg = WebSocketMessage(event=EventType.GAME_RESUMED.value, data=payload.model_dump(mode="json"))
                return game, msg, timer

            game, msg, timer = await run_in_threadpool(_run_db, db, work)
            _paused_times.pop(game_id, None)
            await manager.broadcast_to_game(game_id, msg)
            if timer is not None:
                cls._schedule_deadline(game_id, *timer)
            return game

    @classmethod
    async def reveal_answer(cls, db: Session | None, game_id: int, admin: Admin) -> ScoreQuestionOut:
        """Score the question at reveal and broadcast results and updated leaderboard."""
        async with _host_action(db, game_id):
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                if not game.current_question_id:
                    raise HTTPException(status_code=409, detail="No question is currently open to reveal.")
                result = answer_service.score_question(session, game, game.current_question_id)
                board = leaderboard_service.get_leaderboard(session, game, limit=5)
                reveal_payload = AnswerRevealPayload(
                    game_id=game_id,
                    question_id=game.current_question_id,
                    correct_option_id=result.correct_option_id,
                    distribution=result.distribution,
                    answered=result.answered,
                    correct=result.correct,
                    already_scored=result.already_scored,
                )
                reveal_msg = WebSocketMessage(
                    event=EventType.ANSWER_REVEALED.value,
                    data=reveal_payload.model_dump(mode="json"),
                )
                players = participant_service.active_players(session, game_id)
                all_stats = leaderboard_service.stats_for_all(session, game, players)
                personal_messages = []
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
                    msg = WebSocketMessage(
                        event=EventType.ANSWER_REVEALED.value,
                        data={**reveal_payload.model_dump(mode="json"), "my_stats": personal_payload.model_dump(mode="json")},
                    )
                    personal_messages.append((player.id, msg))
                board_msg = WebSocketMessage(
                    event=EventType.LEADERBOARD_UPDATED.value,
                    data=board.model_dump(mode="json"),
                )
                return result, reveal_msg, personal_messages, board_msg

            result, reveal_msg, personal_messages, board_msg = await run_in_threadpool(_run_db, db, work)
            cls._cancel_deadline(game_id)
            await manager.broadcast_to_role(game_id, "host", reveal_msg)
            await manager.broadcast_to_role(game_id, "stage", reveal_msg)
            await asyncio.gather(*(
                manager.send_to_participant(game_id, participant_id, message)
                for participant_id, message in personal_messages
            ))
            await manager.broadcast_to_game(game_id, board_msg)
            return result

    @classmethod
    async def end_game(cls, db: Session | None, game_id: int, admin: Admin) -> Game:
        """End the game session manually."""
        async with _host_action(db, game_id):
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                game.status = "finished"
                session.commit()
                session.refresh(game)
                board = leaderboard_service.get_leaderboard(session, game, limit=5)
                msg = WebSocketMessage(
                    event=EventType.GAME_FINISHED.value,
                    data={"game_id": game.id, "status": "finished", "leaderboard": board.model_dump(mode="json")},
                )
                return game, msg

            game, msg = await run_in_threadpool(_run_db, db, work)
            cls._cancel_deadline(game_id)
            await manager.broadcast_to_game(game_id, msg)
            return game

    @classmethod
    async def kick_participant(
        cls, db: Session | None, game_id: int, participant_id: int, admin: Admin
    ) -> None:
        """Kick an active player: deactivates in DB and disconnects their sockets."""
        async with _host_action(db, game_id):
            def work(session: Session):
                game = _lock_game_for_admin(session, game_id, session.get(Admin, admin.id))
                membership = (
                    session.query(GameParticipant)
                    .options(selectinload(GameParticipant.participant))
                    .filter(GameParticipant.game_id == game.id, GameParticipant.id == participant_id)
                    .first()
                )
                if membership is None:
                    raise HTTPException(status_code=404, detail=f"Participant with ID {participant_id} not found in this game.")
                nickname = membership.display_name or membership.participant.nickname
                is_anonymous = membership.is_anonymous
                membership.is_active = False
                session.commit()
                total_active = session.query(GameParticipant.id).filter(
                    GameParticipant.game_id == game.id, GameParticipant.is_active.is_(True)
                ).count()
                return game.id, membership.id, nickname, is_anonymous, total_active

            target_game_id, target_id, nickname, is_anonymous, total_active = await run_in_threadpool(
                _run_db, db, work
            )
            await manager.kick_participant(target_game_id, target_id, reason="Removed by host")
            await cls.broadcast_player_left(
                target_game_id, target_id, total_active, nickname, is_anonymous=is_anonymous
            )


orchestrator = GameOrchestrator()
