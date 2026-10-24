"""
participant_service.py — Games, joining and rejoining (Developer 2).

  create_game        admin starts a live game for one of their quizzes -> 6-digit PIN
  join_game          a player joins with PIN + nickname -> secret rejoin token
  rejoin_game        a player whose phone dropped comes back with PIN + token
  get_participant_by_token   used by the X-Participant-Token dependency
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Admin, Game, GameParticipant, Participant
from app.nicknames import NicknameRejected, check_nickname, nickname_key
from app.services.quiz_service import get_quiz_and_verify_ownership

PIN_ATTEMPTS = 20


def _new_pin(db: Session) -> str:
    """A random 6-digit PIN no other game uses (games.pin is unique across all games)."""
    for _ in range(PIN_ATTEMPTS):
        pin = str(100_000 + secrets.randbelow(900_000))
        if db.query(Game.id).filter(Game.pin == pin).first() is None:
            return pin
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a free game PIN. Try again.",
    )


def create_game(db: Session, quiz_id: int, admin: Admin) -> Game:
    """Create a game in the 'lobby' state for a quiz the admin owns."""
    quiz = get_quiz_and_verify_ownership(db, quiz_id, admin)
    game = Game(quiz_id=quiz.id, pin=_new_pin(db), status="lobby")
    db.add(game)
    try:
        db.commit()
    except IntegrityError:  # two games drew the same PIN at the same moment
        db.rollback()
        game = Game(quiz_id=quiz.id, pin=_new_pin(db), status="lobby")
        db.add(game)
        db.commit()
    db.refresh(game)
    return game


def get_game_by_id(db: Session, game_id: int) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game with ID {game_id} was not found.")
    return game


def get_game_by_pin(db: Session, pin: str) -> Game:
    game = db.query(Game).filter(Game.pin == pin.strip()).first()
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No game with that PIN. Check the PIN on the screen.")
    return game


def join_game(db: Session, pin: str, raw_nickname: str) -> GameParticipant:
    """
    Add a new player to the game with this PIN.

    Joining is allowed in the lobby and while the game is running (a late joiner
    starts at 0). Not allowed once the game has finished.
    """
    game = get_game_by_pin(db, pin)
    if game.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This quiz has already ended.")

    try:
        nickname = check_nickname(raw_nickname)
    except NicknameRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None

    key = nickname_key(nickname)
    taken = (
        db.query(GameParticipant.id)
        .filter(GameParticipant.game_id == game.id, GameParticipant.nickname_key == key)
        .first()
    )
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That nickname is taken in this game. Try another.")

    participant = Participant(nickname=nickname)
    db.add(participant)
    db.flush()
    membership = GameParticipant(
        game_id=game.id,
        participant_id=participant.id,
        token=secrets.token_urlsafe(24),
        nickname_key=key,
        is_active=True,
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:  # someone took the same nickname a moment earlier
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That nickname is taken in this game. Try another.") from None
    db.refresh(membership)
    return membership


def get_participant_by_token(db: Session, token: str) -> GameParticipant:
    membership = db.query(GameParticipant).filter(GameParticipant.token == token).first() if token else None
    if membership is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Join the game again.")
    if not membership.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You were removed from this game.")
    return membership


def rejoin_game(db: Session, pin: str, token: str) -> GameParticipant:
    """Return the existing player for this PIN + token (same id, score and streak)."""
    game = get_game_by_pin(db, pin)
    membership = get_participant_by_token(db, token)
    if membership.game_id != game.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Join the game again.")
    return membership
