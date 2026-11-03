"""
participant_service.py — Games, joining and rejoining (Developer 2).

  create_game        admin starts a live game for one of their quizzes -> 8-digit PIN
                     (needs a question; publishes the quiz so it can't be edited mid-game)
  join_game          a player joins with PIN + nickname -> secret rejoin token
  rejoin_game        a player whose phone dropped comes back with PIN + token
  get_participant_by_token   used by the X-Participant-Token dependency
  get_game_for_admin / get_player_game   load a game and check who is asking
  active_players / standing               the players who count for scoring and ranking
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import scoring
from app.models import Admin, Game, GameParticipant, Participant, Question, Round
from app.nicknames import NicknameRejected, check_nickname, nickname_key
from app.services.quiz_service import get_quiz_and_verify_ownership

PIN_ATTEMPTS = 20


def _new_pin(db: Session) -> str:
    """A random 8-digit PIN (never a leading zero) no other game uses (games.pin is unique)."""
    for _ in range(PIN_ATTEMPTS):
        pin = str(10_000_000 + secrets.randbelow(90_000_000))
        if db.query(Game.id).filter(Game.pin == pin).first() is None:
            return pin
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a free game PIN. Try again.",
    )


def create_game(db: Session, quiz_id: int, admin: Admin) -> Game:
    """
    Create a game in the 'lobby' state for a quiz the admin owns.

    The quiz needs at least one question. Creating the game also publishes the
    quiz, in the same commit: Developer 1 refuses edits to a published quiz, so
    nobody can change questions or correct answers while the game is live.
    """
    quiz = get_quiz_and_verify_ownership(db, quiz_id, admin)
    has_question = (
        db.query(Question.id).join(Round, Round.id == Question.round_id).filter(Round.quiz_id == quiz.id).first()
    )
    if has_question is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add at least one question before starting a game.",
        )

    quiz.is_published = True
    game = Game(quiz_id=quiz.id, pin=_new_pin(db), status="lobby")
    db.add(game)
    try:
        db.commit()
    except IntegrityError:  # two games drew the same PIN at the same moment
        db.rollback()
        quiz.is_published = True
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


def get_game_for_admin(db: Session, game_id: int, admin: Admin) -> Game:
    """The game, if the admin owns the quiz it runs (404 / 403 otherwise)."""
    game = get_game_by_id(db, game_id)
    get_quiz_and_verify_ownership(db, game.quiz_id, admin)
    return game


def get_game_by_pin(db: Session, pin: str) -> Game:
    game = db.query(Game).filter(Game.pin == pin.strip()).first()
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No game with that PIN. Check the PIN on the screen.")
    return game


def join_game(db: Session, pin: str, raw_nickname: str | None = None, is_anonymous: bool | None = None) -> GameParticipant:
    """
    Add a new player to the game with this PIN.

    - If is_anonymous is True (or no nickname is provided), automatically assigns
      the next unique anonymous name (e.g. Anonymous_01, Anonymous_02).
    - If a nickname is provided and is_anonymous is not True, validates the nickname
      and uses it for display, maintaining full backward compatibility with tests and callers.
    """
    game = get_game_by_pin(db, pin)
    if game.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This quiz has already ended.")

    # Determine unique anonymous candidate name
    anon_count = (
        db.query(GameParticipant.id)
        .filter(GameParticipant.game_id == game.id)
        .count()
    )
    idx = anon_count + 1
    candidate_name = f"Anonymous_{idx:02d}"
    while db.query(GameParticipant.id).filter(GameParticipant.game_id == game.id, GameParticipant.display_name == candidate_name).first() is not None:
        idx += 1
        candidate_name = f"Anonymous_{idx:02d}"

    # If is_anonymous is explicitly True or raw_nickname is omitted (None)
    if is_anonymous is True or raw_nickname is None:
        display_name = candidate_name
        key = nickname_key(candidate_name)
        participant = Participant(nickname=candidate_name)
        is_anon_flag = True
    else:
        # Caller provided a nickname (empty or not) without is_anonymous=True; validate strictly
        try:
            clean_nick = check_nickname(raw_nickname)
        except NicknameRejected as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
        display_name = clean_nick
        key = nickname_key(clean_nick)
        taken = (
            db.query(GameParticipant.id)
            .filter(GameParticipant.game_id == game.id, GameParticipant.nickname_key == key)
            .first()
        )
        if taken is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That nickname is taken in this game. Try another.")
        participant = Participant(nickname=clean_nick)
        is_anon_flag = False

    db.add(participant)
    db.flush()
    membership = GameParticipant(
        game_id=game.id,
        participant_id=participant.id,
        token=secrets.token_urlsafe(24),
        nickname_key=key,
        is_active=True,
        is_anonymous=is_anon_flag,
        display_name=display_name,
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if should_be_anonymous:
            idx += 1
            fallback_name = f"Anonymous_{idx:02d}"
            p = Participant(nickname=fallback_name)
            db.add(p)
            db.flush()
            membership = GameParticipant(
                game_id=game.id,
                participant_id=p.id,
                token=secrets.token_urlsafe(24),
                nickname_key=nickname_key(fallback_name),
                is_active=True,
                is_anonymous=True,
                display_name=fallback_name,
            )
            db.add(membership)
            db.commit()
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That nickname is taken in this game. Try another.") from None

    db.refresh(membership)
    return membership


def get_participant_by_token(db: Session, token: str) -> GameParticipant:
    membership = (
        db.query(GameParticipant)
        .options(selectinload(GameParticipant.participant))  # nickname, read by /me and rejoin
        .filter(GameParticipant.token == token)
        .first()
    ) if token else None
    if membership is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Join the game again.")
    if not membership.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You were removed from this game.")
    return membership


def get_player_game(db: Session, game_id: int, membership: GameParticipant) -> Game:
    """The game a player is calling about; their token must belong to it."""
    game = get_game_by_id(db, game_id)
    if membership.game_id != game.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not in this game.")
    return game


def rejoin_game(db: Session, pin: str, token: str) -> GameParticipant:
    """Return the existing player for this PIN + token (same id, score and streak)."""
    game = get_game_by_pin(db, pin)
    membership = get_participant_by_token(db, token)
    if membership.game_id != game.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Join the game again.")
    return membership


def active_players(db: Session, game_id: int) -> list[GameParticipant]:
    """
    Players still in the game. Removed players are never scored or ranked.

    Nicknames are loaded in the same round trip (one extra SELECT for everyone,
    not one per player), so leaderboards stay fast with a full room.
    """
    return (
        db.query(GameParticipant)
        .options(selectinload(GameParticipant.participant))
        .filter(GameParticipant.game_id == game_id, GameParticipant.is_active.is_(True))
        .all()
    )


def standing(membership: GameParticipant) -> scoring.Standing:
    """A player's overall standing, as the ranking rules need it."""
    return scoring.Standing(
        participant_id=membership.id,
        score=membership.total_score,
        correct_count=membership.correct_count,
        correct_time_ms=membership.correct_time_ms,
        joined_at=membership.joined_at,
    )
