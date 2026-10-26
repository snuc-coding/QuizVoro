"""
websocket.py — Real-time WebSocket endpoints for Host, Participant, and Stage Display.

Developer 3: WebSocket route handlers.
Endpoints:
  /api/v1/ws/games/{gameId}/host         admin: control game, receive real-time updates
  /api/v1/ws/games/{gameId}/participant  player: receive question & leaderboard updates
  /api/v1/ws/games/{gameId}/stage        stage: public display screen (read-only)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
import jwt
from sqlalchemy.orm import Session

from app.database import get_db
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


# ── Host WebSocket Endpoint ───────────────────────────────────────────────────

@router.websocket("/{gameId}/host")
async def host_websocket_endpoint(
    websocket: WebSocket,
    gameId: int,
    token: str = Query(..., description="Admin JWT Bearer access token."),
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket connection for the game host.
    Requires valid admin JWT and quiz ownership.
    """
    # 1. Authenticate Admin
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

    admin = db.get(Admin, admin_id)
    if not admin or not admin.is_active:
        await websocket.close(code=4003, reason="Admin account disabled or not found")
        return

    # 2. Verify Game Ownership
    try:
        participant_service.get_game_for_admin(db, gameId, admin)
    except Exception:
        await websocket.close(code=4003, reason="Forbidden: Not the quiz owner")
        return

    # 3. Accept Connection
    await websocket.accept()
    await manager.connect_host(gameId, websocket)

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
                if action_upper == HostAction.START.value:
                    await orchestrator.start_game(db, gameId, admin)
                elif action_upper == HostAction.NEXT_QUESTION.value:
                    await orchestrator.next_question(db, gameId, admin)
                elif action_upper == HostAction.PAUSE.value:
                    await orchestrator.pause_game(db, gameId, admin)
                elif action_upper == HostAction.RESUME.value:
                    await orchestrator.resume_game(db, gameId, admin)
                elif action_upper == HostAction.REVEAL.value:
                    await orchestrator.reveal_answer(db, gameId, admin)
                elif action_upper == HostAction.END.value:
                    await orchestrator.end_game(db, gameId, admin)
                elif action_upper == HostAction.KICK.value:
                    participant_id = data.get("participant_id")
                    if participant_id:
                        await orchestrator.kick_participant(db, gameId, int(participant_id), admin)
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
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket connection for live players.
    Requires valid participant token. Enforces answer secrecy and data isolation.
    """
    # 1. Authenticate Participant
    try:
        membership = participant_service.get_participant_by_token(db, token)
    except Exception:
        await websocket.close(code=4003, reason="Invalid participant token")
        return

    # 2. Verify Membership in this game
    if membership.game_id != gameId or not membership.is_active:
        await websocket.close(code=4003, reason="Forbidden: Removed or not in this game")
        return

    # 3. Accept Connection
    await websocket.accept()
    await manager.connect_participant(gameId, membership.id, websocket)

    # Broadcast player joined to room
    total_active = len(participant_service.active_players(db, gameId))
    await orchestrator.broadcast_player_joined(
        gameId, membership.id, membership.participant.nickname, total_active
    )

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
                    ack = answer_service.submit_answer(db, gameId, membership, answer_in)
                    await websocket.send_json({
                        "event": "ANSWER_ACK",
                        "data": ack.model_dump(mode="json"),
                    })
                    # Broadcast updated count to host and stage
                    await orchestrator.broadcast_answer_count(db, gameId, answer_in.question_id)
                except Exception as exc:
                    detail = getattr(exc, "detail", str(exc))
                    await websocket.send_json({
                        "event": EventType.ERROR.value,
                        "data": {"detail": detail},
                    })
                continue

            # Security: If a participant attempts to send a host command, reject it
            if "action" in data:
                await websocket.send_json({
                    "event": EventType.ERROR.value,
                    "data": {"detail": "Participants are not authorized to perform host controls."},
                })

    except WebSocketDisconnect:
        await manager.disconnect_participant(gameId, membership.id, websocket)
        total_left = len(participant_service.active_players(db, gameId))
        await orchestrator.broadcast_player_left(
            gameId, membership.id, total_left, membership.participant.nickname
        )
    except Exception as exc:
        logger.error(f"Participant websocket error: {exc}")
        await manager.disconnect_participant(gameId, membership.id, websocket)


# ── Stage Display WebSocket Endpoint ──────────────────────────────────────────

@router.websocket("/{gameId}/stage")
async def stage_websocket_endpoint(
    websocket: WebSocket,
    gameId: int,
    token: str = Query(..., description="Cryptographically signed stage display token."),
    db: Session = Depends(get_db),
):
    """
    Stage Display WebSocket connection for public venue screens.
    Enforces strong authentication via signed stage token.
    Enforces read-only behavior: all incoming command messages are rejected/ignored.
    """
    # 1. Validate Stage Token
    if not verify_stage_token(token, gameId):
        await websocket.close(code=4003, reason="Forbidden: Invalid stage display token")
        return

    # 2. Verify Game Exists
    try:
        participant_service.get_game_by_id(db, gameId)
    except Exception:
        await websocket.close(code=4004, reason="Game not found")
        return

    # 3. Accept Connection
    await websocket.accept()
    await manager.connect_stage(gameId, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == EventType.PING.value:
                await websocket.send_json({"event": EventType.PONG.value, "timestamp": _now().isoformat()})
                continue

            # Stage screen is strictly read-only
            await websocket.send_json({
                "event": EventType.ERROR.value,
                "data": {"detail": "Stage display is read-only. Control commands are rejected."},
            })

    except WebSocketDisconnect:
        await manager.disconnect_stage(gameId, websocket)
    except Exception as exc:
        logger.error(f"Stage websocket error: {exc}")
        await manager.disconnect_stage(gameId, websocket)
