"""
routers/games.py — Live game endpoints for players and hosts (Developer 2).

Endpoints:
  POST /api/v1/games                                         admin: create a game, get its PIN
  POST /api/v1/games/join                                    player: join with PIN + nickname
  POST /api/v1/games/rejoin                                  player: come back with PIN + token
  GET  /api/v1/games/{gameId}/questions/current              player: the open question
  GET  /api/v1/games/{gameId}/current-question               player: same, for the frontend
  POST /api/v1/games/{gameId}/answers                        player: lock in an answer
  POST /api/v1/games/{gameId}/questions/{questionId}/score   admin: score at the reveal
  GET  /api/v1/games/{gameId}/leaderboard                    anyone: standings
  GET  /api/v1/games/{gameId}/me                             player: own stats

Player endpoints take the X-Participant-Token header returned by join/rejoin.
"""

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.game_schemas import (
    AnswerAck, AnswerIn, CurrentQuestionOut, GameCreate, GameOut, JoinOut, JoinRequest,
    LeaderboardOut, MyStatsOut, RejoinRequest, ScoreQuestionOut,
)
from app.models import Admin, GameParticipant
from app.services import answer_service, leaderboard_service, participant_service

router = APIRouter(
    prefix="/games",
    tags=["Games"],
)


def current_player(
    x_participant_token: str | None = Header(None, description="Token returned by join or rejoin."),
    db: Session = Depends(get_db),
) -> GameParticipant:
    """Dependency: the player behind the X-Participant-Token header (401 / 403 otherwise)."""
    return participant_service.get_participant_by_token(db, x_participant_token or "")


def _join_out(membership: GameParticipant) -> JoinOut:
    return JoinOut(
        game_id=membership.game_id,
        participant_id=membership.id,
        nickname=membership.participant.nickname,
        token=membership.token,
        game_status=membership.game.status,
    )


@router.post(
    "",
    response_model=GameOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Game",
    description="Start a live game for one of your quizzes. Returns the 8-digit PIN players join with.",
    responses={
        201: {"description": "Game created in the lobby."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Quiz not found."},
    },
)
def create_game(
    game_in: GameCreate,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GameOut:
    """POST /api/v1/games"""
    return participant_service.create_game(db, game_in.quiz_id, admin)


@router.post(
    "/join",
    response_model=JoinOut,
    status_code=status.HTTP_201_CREATED,
    summary="Join Game",
    description="Join with the PIN and a nickname. Keep the returned token to rejoin and to answer.",
    responses={
        201: {"description": "Joined."},
        404: {"description": "No game with that PIN."},
        409: {"description": "Nickname taken, or the quiz has ended."},
        422: {"description": "Nickname not allowed."},
    },
)
def join_game(join_in: JoinRequest, db: Session = Depends(get_db)) -> JoinOut:
    """POST /api/v1/games/join"""
    return _join_out(participant_service.join_game(db, join_in.pin, join_in.nickname))


@router.post(
    "/rejoin",
    response_model=JoinOut,
    summary="Rejoin Game",
    description="Come back after a dropped connection with the PIN and saved token. Score and streak are kept.",
    responses={
        200: {"description": "Rejoined as the same player."},
        401: {"description": "Token not valid for this game."},
        403: {"description": "Removed from the game."},
        404: {"description": "No game with that PIN."},
    },
)
def rejoin_game(rejoin_in: RejoinRequest, db: Session = Depends(get_db)) -> JoinOut:
    """POST /api/v1/games/rejoin"""
    return _join_out(participant_service.rejoin_game(db, rejoin_in.pin, rejoin_in.token))


_CURRENT_QUESTION_DOCS = dict(
    response_model=CurrentQuestionOut,
    description=(
        "The open question without correct answers (options listed by id), plus "
        "question_number / total_questions, opened_at, deadline and server_time."
    ),
    responses={
        200: {"description": "The open question."},
        401: {"description": "Missing or unknown token."},
        403: {"description": "Not in this game, or removed."},
        404: {"description": "No question is open."},
        409: {"description": "Game paused, not started or ended."},
    },
)


@router.get("/{gameId}/questions/current", summary="Current Question", **_CURRENT_QUESTION_DOCS)
@router.get("/{gameId}/current-question", summary="Current Question (alias)", **_CURRENT_QUESTION_DOCS)
def get_current_question(
    gameId: int,
    player: GameParticipant = Depends(current_player),
    db: Session = Depends(get_db),
) -> CurrentQuestionOut:
    """GET /api/v1/games/{gameId}/questions/current (also /current-question)"""
    return answer_service.current_question(db, gameId, player)


@router.post(
    "/{gameId}/answers",
    response_model=AnswerAck,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Answer",
    description="Lock in one answer to the open question. The reply never says whether it is correct.",
    responses={
        201: {"description": "Answer locked in."},
        401: {"description": "Missing or unknown token."},
        403: {"description": "Not in this game, or removed."},
        409: {"description": "Paused, wrong question, not open, already scored, late, or already answered."},
        422: {"description": "Option is not part of the question."},
    },
)
def submit_answer(
    gameId: int,
    answer_in: AnswerIn,
    player: GameParticipant = Depends(current_player),
    db: Session = Depends(get_db),
) -> AnswerAck:
    """POST /api/v1/games/{gameId}/answers"""
    return answer_service.submit_answer(db, gameId, player, answer_in)


@router.post(
    "/{gameId}/questions/{questionId}/score",
    response_model=ScoreQuestionOut,
    summary="Score Question",
    description=(
        "Award points for the open question at the reveal. Safe to repeat: later calls "
        "change nothing and return the same result with already_scored=true."
    ),
    responses={
        200: {"description": "Scored (or already scored)."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Game not found, or question not in this game's quiz."},
        409: {"description": "Question is not the open one."},
    },
)
def score_question(
    gameId: int,
    questionId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScoreQuestionOut:
    """POST /api/v1/games/{gameId}/questions/{questionId}/score"""
    game = participant_service.get_game_for_admin(db, gameId, admin)
    return answer_service.score_question(db, game, questionId)


@router.get(
    "/{gameId}/leaderboard",
    response_model=LeaderboardOut,
    summary="Leaderboard",
    description="Top players overall, or for one round with round_id. Includes climbers and close battles.",
    responses={
        200: {"description": "Standings."},
        404: {"description": "Game not found, or round not in this game's quiz."},
    },
)
def get_leaderboard(
    gameId: int,
    limit: int = Query(10, ge=1, le=100, description="How many players to return."),
    round_id: int | None = Query(None, gt=0, description="Standings for this round only."),
    db: Session = Depends(get_db),
) -> LeaderboardOut:
    """GET /api/v1/games/{gameId}/leaderboard"""
    game = participant_service.get_game_by_id(db, gameId)
    return leaderboard_service.get_leaderboard(db, game, limit, round_id)


@router.get(
    "/{gameId}/me",
    response_model=MyStatsOut,
    summary="My Stats",
    description="Your score, rank, streak and how you did on the latest scored question.",
    responses={
        200: {"description": "Your stats."},
        401: {"description": "Missing or unknown token."},
        403: {"description": "Not in this game, or removed."},
    },
)
def get_my_stats(
    gameId: int,
    player: GameParticipant = Depends(current_player),
    db: Session = Depends(get_db),
) -> MyStatsOut:
    """GET /api/v1/games/{gameId}/me"""
    return leaderboard_service.my_stats(db, gameId, player)
