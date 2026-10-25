"""
answer_service.py — The open question, answers and scoring (Developer 2).

  current_question   the question on the player's phone, e.g. "QUESTION 1/2" (never which option is correct)
  submit_answer      lock in one answer per player per question
  score_question     award points for a question, exactly once, at the reveal

All times come from the server clock. Answers open at games.current_question_started_at,
which Dev 3 sets when a question goes live and shifts forward after a pause.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import scoring
from app.game_schemas import AnswerAck, AnswerIn, CurrentQuestionOut, OptionCount, ScoreQuestionOut
from app.models import Answer, Game, GameParticipant, Option, Question, Round, ScoredQuestion
from app.schemas import ParticipantOptionOut, ParticipantQuestionOut
from app.services.participant_service import active_players, get_player_game, standing

_NOT_RUNNING = {
    "lobby": "The quiz hasn't started yet.",
    "paused": "The game is paused.",
    "finished": "This quiz has already ended.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _require_active(game: Game) -> None:
    if game.status != "active":
        raise _conflict(_NOT_RUNNING.get(game.status, "Answers are not open."))


def _is_scored(db: Session, game_id: int, question_id: int) -> bool:
    return (
        db.query(ScoredQuestion.id)
        .filter(ScoredQuestion.game_id == game_id, ScoredQuestion.question_id == question_id)
        .first()
        is not None
    )


def _answer_of(db: Session, game_id: int, player_id: int, question_id: int) -> Answer | None:
    return (
        db.query(Answer)
        .filter(
            Answer.game_id == game_id,
            Answer.game_participant_id == player_id,
            Answer.question_id == question_id,
        )
        .first()
    )


def _quiz_question_ids(db: Session, quiz_id: int) -> list[int]:
    """Every question in the quiz, in play order: round_number, then question_order."""
    return [
        question_id
        for (question_id,) in db.query(Question.id)
        .join(Round, Round.id == Question.round_id)
        .filter(Round.quiz_id == quiz_id)
        .order_by(Round.round_number, Question.question_order)
    ]


def ordered_options(question: Question) -> list[Option]:
    """A question's options by id: the order phones show them and letters A-D refer to."""
    return sorted(question.options, key=lambda option: option.id)


def participant_question(question: Question) -> ParticipantQuestionOut:
    """The question as players see it: no is_correct, options in ordered_options order."""
    out = ParticipantQuestionOut.model_validate(question)
    out.options = [ParticipantOptionOut.model_validate(option) for option in ordered_options(question)]
    return out


# ── Players ──────────────────────────────────────────────────────────────────

def current_question(db: Session, game_id: int, player: GameParticipant) -> CurrentQuestionOut:
    """The open question for this player, with the times their countdown needs."""
    game = get_player_game(db, game_id, player)
    _require_active(game)
    question = db.get(Question, game.current_question_id) if game.current_question_id else None
    if question is None or game.current_question_started_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No question is open right now.")

    opened_at = scoring.as_utc(game.current_question_started_at)
    question_ids = _quiz_question_ids(db, game.quiz_id)
    return CurrentQuestionOut(
        question=participant_question(question),
        question_number=question_ids.index(question.id) + 1,
        total_questions=len(question_ids),
        opened_at=opened_at,
        deadline=opened_at + timedelta(seconds=question.time_limit),
        server_time=_now(),
        already_answered=_answer_of(db, game.id, player.id, question.id) is not None,
    )


def submit_answer(db: Session, game_id: int, player: GameParticipant, answer_in: AnswerIn) -> AnswerAck:
    """
    Lock in the player's answer to the open question.

    Whether it is correct is decided when the question is scored, and the reply
    never says. Late, duplicate and out-of-turn answers are rejected.
    """
    game = get_player_game(db, game_id, player)
    _require_active(game)
    if answer_in.question_id != game.current_question_id:
        raise _conflict("That question is not open.")

    now = _now()
    opened_at = game.current_question_started_at
    if opened_at is None or now < scoring.as_utc(opened_at):
        raise _conflict("Answers haven't opened yet.")
    if _is_scored(db, game.id, answer_in.question_id):
        raise _conflict("This question is closed.")

    question = db.get(Question, answer_in.question_id)
    option = db.get(Option, answer_in.option_id)
    if option is None or option.question_id != question.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That option is not part of this question.",
        )
    if _answer_of(db, game.id, player.id, question.id) is not None:
        raise _conflict("You already answered this question.")

    time_ms = scoring.response_time_ms(opened_at, now)
    if scoring.is_late(time_ms, question.time_limit):
        raise _conflict("Time's up. Your answer arrived after the timer ended.")

    db.add(Answer(
        game_id=game.id,
        game_participant_id=player.id,
        question_id=question.id,
        chosen_option_id=option.id,
        response_time_ms=time_ms,
        answered_at=now,
    ))
    try:
        db.commit()
    except IntegrityError:  # a double tap: the first request already saved an answer
        db.rollback()
        raise _conflict("You already answered this question.") from None
    return AnswerAck(question_id=question.id, option_id=option.id, response_time_ms=time_ms)


# ── Scoring (the reveal) ─────────────────────────────────────────────────────

def _question_in_game(db: Session, game: Game, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None or question.round.quiz_id != game.quiz_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} is not part of this game's quiz.",
        )
    return question


def _award_points(db: Session, game: Game, question: Question) -> None:
    """Score every active player's answer, then update streaks and ranks."""
    correct_ids = {option.id for option in question.options if option.is_correct}
    limit_ms = question.time_limit * 1000
    answers = {
        answer.game_participant_id: answer
        for answer in db.query(Answer).filter(Answer.game_id == game.id, Answer.question_id == question.id)
    }
    players = active_players(db, game.id)

    for player in players:
        answer = answers.get(player.id)
        correct = answer is not None and answer.chosen_option_id in correct_ids
        if answer is not None:
            answer.is_correct = correct
            answer.points_awarded = scoring.points_for(
                correct, answer.response_time_ms, question.time_limit, question.points
            )
            player.total_score += answer.points_awarded
        if correct:
            player.correct_count += 1
            # Grace-window answers count as arriving exactly at the deadline.
            player.correct_time_ms += min(answer.response_time_ms, limit_ms)
        player.current_streak, player.best_streak = scoring.next_streak(
            player.current_streak, player.best_streak, correct
        )

    new_ranks = scoring.rank([standing(player) for player in players])
    for player in players:
        player.previous_rank = player.rank
        player.rank = new_ranks[player.id]


def _result(db: Session, game_id: int, question: Question, already_scored: bool) -> ScoreQuestionOut:
    """What the reveal shows. Built from the scored answers, so every call agrees."""
    scored = (
        db.query(Answer)
        .filter(Answer.game_id == game_id, Answer.question_id == question.id, Answer.is_correct.isnot(None))
        .all()
    )
    counts = Counter(answer.chosen_option_id for answer in scored)
    options = sorted(question.options, key=lambda option: option.id)
    return ScoreQuestionOut(
        game_id=game_id,
        question_id=question.id,
        correct_option_id=next(option.id for option in options if option.is_correct),
        distribution=[OptionCount(option_id=option.id, count=counts[option.id]) for option in options],
        answered=len(scored),
        correct=sum(1 for answer in scored if answer.is_correct),
        already_scored=already_scored,
    )


def score_question(db: Session, game: Game, question_id: int) -> ScoreQuestionOut:
    """
    Award points for one question. Safe to call more than once.

    The scored_questions row is inserted first and is the guard: if this question
    was already scored (or two reveal requests race), nothing changes and the
    stored result comes back with already_scored=True.

    Callers check who is asking (the router checks the admin owns the quiz), so
    Dev 3 can also call this from a timer.
    """
    question = _question_in_game(db, game, question_id)
    if _is_scored(db, game.id, question.id):
        return _result(db, game.id, question, already_scored=True)
    if question.id != game.current_question_id or game.current_question_started_at is None:
        raise _conflict("Only the open question can be scored.")

    db.add(ScoredQuestion(game_id=game.id, question_id=question.id))
    try:
        db.flush()
    except IntegrityError:  # another reveal scored it a moment earlier
        db.rollback()
        return _result(db, game.id, question, already_scored=True)

    _award_points(db, game, question)
    db.commit()
    return _result(db, game.id, question, already_scored=False)
