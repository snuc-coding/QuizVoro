"""
leaderboard_service.py — Standings for the stage screen, host and players (Developer 2).

  get_leaderboard   overall top N, or one round's standings (round_id)
  my_stats          a player's own score, rank, streak and last result
  stats_for_all     the same for every active player at once (used at the reveal)

Only scored questions count, so nothing here can reveal the open question's answer.
Removed players are left out. rank_delta is the move at the latest scoring.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import scoring
from app.game_schemas import (
    ClimberOut, CloseBattleOut, LastResult, LeaderboardEntry, LeaderboardOut, MyStatsOut,
)
from app.models import Answer, Game, GameParticipant, Question, Round, ScoredQuestion
from app.services.participant_service import active_players, get_player_game, standing

# rank moves per player: participant_id -> (previous rank, current rank)
Moves = dict[int, tuple[int | None, int | None]]


def _scored_question_ids(db: Session, game_id: int, round_id: int | None = None) -> list[int]:
    """Scored questions in the order they were scored (oldest first)."""
    query = db.query(ScoredQuestion.question_id).filter(ScoredQuestion.game_id == game_id)
    if round_id is not None:
        query = query.join(Question, Question.id == ScoredQuestion.question_id).filter(Question.round_id == round_id)
    return [question_id for (question_id,) in query.order_by(ScoredQuestion.id)]


def _build(
    game: Game,
    round_id: int | None,
    players: list[GameParticipant],
    standings: list[scoring.Standing],
    moves: Moves,
    scored_count: int,
    limit: int,
) -> LeaderboardOut:
    by_id = {player.id: player for player in players}
    ordered = sorted(standings, key=scoring.rank_key)
    top = [
        LeaderboardEntry(
            rank=position,
            participant_id=s.participant_id,
            nickname=by_id[s.participant_id].participant.nickname,
            score=s.score,
            rank_delta=scoring.rank_delta(*moves[s.participant_id]),
            streak=by_id[s.participant_id].current_streak,
            correct_count=s.correct_count,
        )
        for position, s in enumerate(ordered[:limit], start=1)
    ]
    climbers = [
        ClimberOut(
            participant_id=climber.participant_id,
            nickname=by_id[climber.participant_id].participant.nickname,
            rank_delta=climber.rank_delta,
        )
        for climber in scoring.biggest_climbers(moves)
    ]
    # Before anything is scored everyone is on 0: that's not a battle.
    battles = [
        CloseBattleOut(rank=battle.rank, participant_ids=list(battle.participant_ids), gap=battle.gap)
        for battle in scoring.close_battles([(s.participant_id, s.score) for s in ordered])
    ] if scored_count else []
    return LeaderboardOut(
        game_id=game.id,
        round_id=round_id,
        total_participants=len(players),
        scored_questions=scored_count,
        top=top,
        climbers=climbers,
        close_battles=battles,
    )


def _round_standings(
    players: list[GameParticipant], rows: list[tuple[Answer, int]]
) -> list[scoring.Standing]:
    """Standings from a set of scored answers. rows: (answer, question time limit)."""
    totals = {player.id: [0, 0, 0] for player in players}  # score, correct, correct time
    for answer, time_limit in rows:
        total = totals.get(answer.game_participant_id)
        if total is None:  # removed player
            continue
        total[0] += answer.points_awarded or 0
        if answer.is_correct:
            total[1] += 1
            total[2] += min(answer.response_time_ms, time_limit * 1000)
    return [
        scoring.Standing(player.id, *totals[player.id], joined_at=player.joined_at)
        for player in players
    ]


def _round_leaderboard(db: Session, game: Game, round_id: int, limit: int) -> LeaderboardOut:
    round_ = db.get(Round, round_id)
    if round_ is None or round_.quiz_id != game.quiz_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Round with ID {round_id} is not part of this game's quiz.",
        )
    players = active_players(db, game.id)
    question_ids = _scored_question_ids(db, game.id, round_.id)
    rows = (
        db.query(Answer, Question.time_limit)
        .join(Question, Question.id == Answer.question_id)
        .filter(Answer.game_id == game.id, Answer.question_id.in_(question_ids), Answer.is_correct.isnot(None))
        .all()
    ) if question_ids else []

    standings = _round_standings(players, rows)
    current = scoring.rank(standings)
    if len(question_ids) > 1:  # compare with the round before its latest question
        latest = question_ids[-1]
        previous = scoring.rank(_round_standings(players, [r for r in rows if r[0].question_id != latest]))
    else:
        previous = {}
    moves = {player.id: (previous.get(player.id), current[player.id]) for player in players}
    return _build(game, round_.id, players, standings, moves, len(question_ids), limit)


def get_leaderboard(db: Session, game: Game, limit: int = 10, round_id: int | None = None) -> LeaderboardOut:
    """Overall standings, or one round's when round_id is given."""
    if round_id is not None:
        return _round_leaderboard(db, game, round_id, limit)
    players = active_players(db, game.id)
    moves = {player.id: (player.previous_rank, player.rank) for player in players}
    standings = [standing(player) for player in players]
    return _build(game, None, players, standings, moves, len(_scored_question_ids(db, game.id)), limit)


def _stats(player: GameParticipant, rank: int | None, latest: int | None, answer: Answer | None) -> MyStatsOut:
    """One player's numbers. latest is the most recently scored question (None before any)."""
    last_result = None
    if latest is not None:
        last_result = LastResult(
            question_id=latest,
            answered=answer is not None,
            is_correct=bool(answer is not None and answer.is_correct),
            points=(answer.points_awarded or 0) if answer is not None else 0,
        )
    return MyStatsOut(
        participant_id=player.id,
        nickname=player.participant.nickname,
        score=player.total_score,
        rank=rank,
        rank_delta=scoring.rank_delta(player.previous_rank, player.rank),
        streak=player.current_streak,
        best_streak=player.best_streak,
        correct_count=player.correct_count,
        last_result=last_result,
    )


def my_stats(db: Session, game_id: int, player: GameParticipant) -> MyStatsOut:
    """The player's own numbers, and how they did on the latest scored question."""
    game = get_player_game(db, game_id, player)
    scored_ids = _scored_question_ids(db, game.id)
    if not scored_ids:
        return _stats(player, None, None, None)

    rank = scoring.rank([standing(p) for p in active_players(db, game.id)])[player.id]
    latest = scored_ids[-1]
    answer = (
        db.query(Answer)
        .filter(Answer.game_id == game.id, Answer.game_participant_id == player.id, Answer.question_id == latest)
        .first()
    )
    return _stats(player, rank, latest, answer)


def stats_for_all(db: Session, game: Game, players: list[GameParticipant]) -> dict[int, MyStatsOut]:
    """
    my_stats for every given player in a few queries instead of a few per player.

    The reveal sends each phone its own result; doing my_stats once per player
    re-ranked the whole room for every player, which took seconds with a few
    hundred players and held up everything else on the server meanwhile.
    """
    scored_ids = _scored_question_ids(db, game.id)
    if not scored_ids:
        return {p.id: _stats(p, None, None, None) for p in players}

    ranks = scoring.rank([standing(p) for p in players])
    latest = scored_ids[-1]
    answers = {
        a.game_participant_id: a
        for a in db.query(Answer).filter(Answer.game_id == game.id, Answer.question_id == latest)
    }
    return {p.id: _stats(p, ranks[p.id], latest, answers.get(p.id)) for p in players}
