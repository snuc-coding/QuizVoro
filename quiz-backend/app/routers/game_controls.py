"""
game_controls.py — Authorized host REST endpoints for game lifecycle management.

Developer 3: Host game orchestration.
Endpoints:
  POST /api/v1/games/{gameId}/start           admin: start quiz from lobby -> active
  POST /api/v1/games/{gameId}/next-question   admin: advance to next question or end
  POST /api/v1/games/{gameId}/pause           admin: pause countdown
  POST /api/v1/games/{gameId}/resume          admin: resume countdown
  POST /api/v1/games/{gameId}/reveal          admin: score question & reveal answer
  POST /api/v1/games/{gameId}/end             admin: finish game early
  POST /api/v1/games/{gameId}/kick            admin: kick participant
  GET  /api/v1/games/{gameId}/stage-token     admin: generate secure stage display token
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.game_schemas import GameOut, ScoreQuestionOut
from app.models import Admin
from app.services.game_orchestrator import create_stage_token, orchestrator, verify_stage_token
from app.websocket_schemas import StageTokenOut

router = APIRouter(
    prefix="/games",
    tags=["Game Controls (Host)"],
)


class KickRequest(BaseModel):
    participant_id: int = Field(..., gt=0, description="The game_participant.id to kick.")


@router.get(
    "/{gameId}/stage-token",
    response_model=StageTokenOut,
    summary="Get Stage Display Token",
    description="Generate a cryptographically signed token for the stage display screen.",
)
def get_stage_token(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StageTokenOut:
    """Generate secure JWT stage token (Host owner only)."""
    # Verify admin owns the quiz running this game
    from app.services.participant_service import get_game_for_admin
    get_game_for_admin(db, gameId, admin)
    token = create_stage_token(gameId)
    return StageTokenOut(game_id=gameId, stage_token=token)


@router.get(
    "/{gameId}/state",
    summary="Get Current Host Game State",
    description="Restore host controls and player list after refresh or reconnection.",
)
def get_host_game_state(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.participant_service import get_game_for_admin
    get_game_for_admin(db, gameId, admin)
    return orchestrator.game_state_snapshot(db, gameId)


@router.get(
    "/{gameId}/stage-state",
    summary="Get Current Stage State",
    description="Return the sanitized projector snapshot for a valid stage token.",
)
def get_stage_game_state(
    gameId: int,
    token: str = Query(..., description="Stage token returned by the host stage-token endpoint."),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_stage_token(token, gameId):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired stage token.")
    return orchestrator.game_state_snapshot(db, gameId)


@router.post(
    "/{gameId}/stage-token/refresh",
    response_model=StageTokenOut,
    summary="Refresh Stage Display Token",
    description="Rotate a still-valid stage token so a long-running projector can reconnect later.",
)
def refresh_stage_token(
    gameId: int,
    token: str = Query(..., description="Current stage token."),
) -> StageTokenOut:
    if not verify_stage_token(token, gameId):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired stage token.")
    return StageTokenOut(game_id=gameId, stage_token=create_stage_token(gameId))


@router.post(
    "/{gameId}/start",
    response_model=GameOut,
    summary="Start Game",
    description="Start the quiz from the lobby. Opens Question 1 and starts the timer.",
)
async def start_game(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    return await orchestrator.start_game(db, gameId, admin)


@router.post(
    "/{gameId}/next-question",
    response_model=GameOut,
    summary="Next Question",
    description="Advance to the next question in sequence, or finish the game if on the last question.",
)
async def next_question(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    return await orchestrator.next_question(db, gameId, admin)


@router.post(
    "/{gameId}/pause",
    response_model=GameOut,
    summary="Pause Game",
    description="Pause the active question countdown. Answers are refused while paused.",
)
async def pause_game(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    return await orchestrator.pause_game(db, gameId, admin)


@router.post(
    "/{gameId}/resume",
    response_model=GameOut,
    summary="Resume Game",
    description="Resume the countdown, shifting start time forward so paused duration does not count.",
)
async def resume_game(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    return await orchestrator.resume_game(db, gameId, admin)


@router.post(
    "/{gameId}/reveal",
    response_model=ScoreQuestionOut,
    summary="Reveal Answer",
    description="Close the question, award points, and broadcast correct answer and standings.",
)
async def reveal_answer(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScoreQuestionOut:
    return await orchestrator.reveal_answer(db, gameId, admin)


@router.post(
    "/{gameId}/end",
    response_model=GameOut,
    summary="End Game",
    description="End the game manually and broadcast final results.",
)
async def end_game(
    gameId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    return await orchestrator.end_game(db, gameId, admin)


@router.post(
    "/{gameId}/kick",
    status_code=status.HTTP_200_OK,
    summary="Kick Participant",
    description="Deactivate a participant from the game and disconnect their live session.",
)
async def kick_participant(
    gameId: int,
    kick_in: KickRequest,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    await orchestrator.kick_participant(db, gameId, kick_in.participant_id, admin)
    return {"success": True, "message": f"Participant {kick_in.participant_id} was removed."}
