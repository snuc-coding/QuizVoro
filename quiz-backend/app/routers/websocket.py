"""
websocket.py — Real-time WebSocket endpoints for Host, Participant, and Stage Display.

Endpoints:
  /api/v1/ws/games/{gameId}/host         admin: control game, receive real-time updates
  /api/v1/ws/games/{gameId}/participant  player: receive question & leaderboard updates
  /api/v1/ws/games/{gameId}/stage        stage: public display screen (read-only)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.database import SessionLocal
from app.game_schemas import AnswerIn
from app.models import Admin, GameParticipant
from app.security import decode_access_token
from app.services import answer_service, participant_service
from app.services.connection_manager import manager
from app.services.game_orchestrator import orchestrator, verify_stage_token
from app.websocket_schemas import EventType, HostAction, WebSocketMessage

logger = logging.getLogger("quizvoro.websocket")

router = APIRouter(
    prefix="/ws/games",
    tags=["Real-Time WebSockets"],
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _db_call(fn, *args):
    """Run fn(db, *args) in a worker thread with a short-lived session.

    Keeps blocking SQLAlchemy calls off the event loop and releases the
    connection as soon as fn returns. fn must return plain values.
    """
    def _inner():
        with SessionLocal() as db:
            return fn(db, *args)
    return await run_in_threadpool(_inner)


# ── Sync helpers (run in threadpool) ──────────────────────────────────────────

def _auth_host(db, admin_id: int, game_id: int) -> None:
    admin = db.get(Admin, admin_id)
    if not admin or not admin.is_active:
        raise PermissionError("Admin account disabled or not found")
    participant_service.get_game_for_admin(db, game_id, admin)


def _auth_participant(db, token: str, game_id: int):
    membership = participant_service.get_participant_by_token(db, token)
    if membership.game_id != game_id or not membership.is_active:
        raise PermissionError("Removed or not in this game")
    display_name = membership.display_name or membership.participant.nickname
    return membership.id, display_name, membership.is_anonymous


def _check_stage_game(db, game_id: int) -> None:
    participant_service.get_game_by_id(db, game_id)


def _count_active(db, game_id: int) -> int:
    return len(participant_service.active_players(db, game_id))


def _submit_answer(db, game_id: int, participant_id: int, answer_in: AnswerIn) -> dict:
    membership = db.get(GameParticipant, participant_id)
    if not membership:
        raise ValueError("Participant membership no longer exists")
    ack = answer_service.submit_answer(db, game_id, membership, answer_in)
    return ack.model_dump(mode="json")


# ── Host WebSocket Endpoint ───────────────────────────────────────────────────

@router.websocket("/{gameId}/host")
async def host_websocket_endpoint(
    websocket: WebSocket,
    gameId: int,
    token: str = Query(..., description="Admin JWT Bearer access token."),
):
    """
    Authenticated WebSocket connection for the game host.
    Requires valid admin JWT and quiz ownership.
    """
    try:
        payload = decode_access_token(token)
        admin_id_str = payload.get("sub")
        if not admin_id_str:
            await websocket.close(code=4003, reason="Invalid token")
            return
        admin_id = int(admin_id_str)
    except Exception:
        await websocket.close(code=4003, reason="Could not validate credentials")
        return

    try:
        await _db_call(_auth_host, admin_id, gameId)
    except Exception:
        await websocket.close(code=4003, reason="Forbidden: Not the quiz owner")
        return

    await websocket.accept()
    await manager.connect_host(gameId, websocket)
    try:
        with SessionLocal() as state_db:
            orchestrator.ensure_deadline_timer(state_db, gameId)
    except Exception as exc:
        logger.error("Could not restore timer for host game %s: %s", gameId, exc)

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == EventType.PING.value:
                await websocket.send_json({"event": EventType.PONG.value, "timestamp": _now().isoformat()})
                continue

            action = data.get("action")
            if not action:
                continue

            action_upper = str(action).upper()
            try:
                # Orchestrator methods are async and take a session, so the
                # session must live on the event loop for the duration of the
                # action only.
                with SessionLocal() as action_db:
                    action_admin = action_db.get(Admin, admin_id)
                    if not action_admin or not action_admin.is_active:
                        raise ValueError("Admin account disabled or not found")
                    if action_upper == HostAction.START.value:
                        await orchestrator.start_game(action_db, gameId, action_admin)
                    elif action_upper == HostAction.NEXT_QUESTION.value:
                        await orchestrator.next_question(action_db, gameId, action_admin)
                    elif action_upper == HostAction.PAUSE.value:
                        await orchestrator.pause_game(action_db, gameId, action_admin)
                    elif action_upper == HostAction.RESUME.value:
                        await orchestrator.resume_game(action_db, gameId, action_admin)
                    elif action_upper == HostAction.REVEAL.value:
                        await orchestrator.reveal_answer(action_db, gameId, action_admin)
                    elif action_upper == HostAction.END.value:
                        await orchestrator.end_game(action_db, gameId, action_admin)
                    elif action_upper == HostAction.KICK.value:
                        participant_id = data.get("participant_id")
                        if participant_id:
                            await orchestrator.kick_participant(action_db, gameId, int(participant_id), action_admin)
                        else:
                            await websocket.send_json({
                                "event": EventType.ERROR.value,
                                "data": {"detail": "participant_id required for KICK action"},
                            })
                    else:
                        await websocket.send_json({
                            "event": EventType.ERROR.value,
                            "data": {"detail": f"Unknown action '{action}'"},
                        })
            except Exception as exc:
                detail = getattr(exc, "detail", str(exc))
                await websocket.send_json({
                    "event": EventType.ERROR.value,
                    "data": {"detail": detail},
                })

    except WebSocketDisconnect:
        await manager.disconnect_host(gameId, websocket)
    except Exception as exc:
        logger.error(f"Host websocket error: {exc}")
        await manager.disconnect_host(gameId, websocket)


# ── Participant WebSocket Endpoint ────────────────────────────────────────────

@router.websocket("/{gameId}/participant")
async def participant_websocket_endpoint(
    websocket: WebSocket,
    gameId: int,
    token: str = Query(..., description="Participant token returned on join/rejoin."),
):
    """
    Authenticated WebSocket connection for live players.
    Requires valid participant token. Enforces answer secrecy and data isolation.
    """
    try:
        participant_id, nickname, is_anonymous = await _db_call(_auth_participant, token, gameId)
    except Exception:
        await websocket.close(code=4003, reason="Invalid participant token")
        return

    await websocket.accept()
    await manager.connect_participant(gameId, participant_id, websocket)

    try:
        total_active = await _db_call(_count_active, gameId)
        await orchestrator.broadcast_player_joined(
            gameId, participant_id, nickname, total_active, is_anonymous=is_anonymous
        )
    except Exception as exc:
        logger.error(f"Participant join broadcast error: {exc}")

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == EventType.PING.value:
                await websocket.send_json({"event": EventType.PONG.value, "timestamp": _now().isoformat()})
                continue

            if event == "SUBMIT_ANSWER":
                try:
                    payload = data.get("data", {})
                    answer_in = AnswerIn(**payload)
                    ack = await _db_call(_submit_answer, gameId, participant_id, answer_in)
                    await websocket.send_json({"event": "ANSWER_ACK", "data": ack})
                    with SessionLocal() as answer_db:
                        await orchestrator.broadcast_answer_count(answer_db, gameId, answer_in.question_id)
                except Exception as exc:
                    detail = getattr(exc, "detail", str(exc))
                    await websocket.send_json({
                        "event": EventType.ERROR.value,
                        "data": {"detail": detail},
                    })
                continue

            if "action" in data:
                await websocket.send_json({
                    "event": EventType.ERROR.value,
                    "data": {"detail": "Participants are not authorized to perform host controls."},
                })

    except WebSocketDisconnect:
        await manager.disconnect_participant(gameId, participant_id, websocket)
        try:
            total_left = await _db_call(_count_active, gameId)
            await orchestrator.broadcast_player_left(
                gameId, participant_id, total_left, nickname, is_anonymous=is_anonymous
            )
        except Exception as exc:
            logger.error(f"Participant leave broadcast error: {exc}")
    except Exception as exc:
        logger.error(f"Participant websocket error: {exc}")
        await manager.disconnect_participant(gameId, participant_id, websocket)


# ── Stage Display WebSocket Endpoint ──────────────────────────────────────────

@router.websocket("/{gameId}/stage")
async def stage_websocket_endpoint(
    websocket: WebSocket,
    gameId: int,
    token: str = Query(..., description="Cryptographically signed stage display token."),
):
    """
    Stage Display WebSocket connection for public venue screens.
    Enforces strong authentication via signed stage token.
    Enforces read-only behavior: all incoming command messages are rejected/ignored.
    """
    if not verify_stage_token(token, gameId):
        await websocket.close(code=4003, reason="Forbidden: Invalid stage display token")
        return

    try:
        await _db_call(_check_stage_game, gameId)
    except Exception:
        await websocket.close(code=4004, reason="Game not found")
        return

    await websocket.accept()
    await manager.connect_stage(gameId, websocket)

    # Every new/reconnected projector receives a fresh snapshot before live events.
    try:
        with SessionLocal() as state_db:
            orchestrator.ensure_deadline_timer(state_db, gameId)
        state = await _db_call(orchestrator.game_state_snapshot, gameId)
        await websocket.send_json({
            "event": "STAGE_STATE",
            "data": state,
            "timestamp": _now().isoformat(),
        })
    except Exception as exc:
        logger.error("Could not restore stage state for game %s: %s", gameId, exc)

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == EventType.PING.value:
                await websocket.send_json({"event": EventType.PONG.value, "timestamp": _now().isoformat()})
                continue

            await websocket.send_json({
                "event": EventType.ERROR.value,
                "data": {"detail": "Stage display is read-only. Control commands are rejected."},
            })

    except WebSocketDisconnect:
        await manager.disconnect_stage(gameId, websocket)
    except Exception as exc:
        logger.error(f"Stage websocket error: {exc}")
        await manager.disconnect_stage(gameId, websocket)
