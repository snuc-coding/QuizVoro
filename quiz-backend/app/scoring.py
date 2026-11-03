"""
scoring.py — The scoring rules, as pure functions (Developer 2).

No database, no HTTP: every function takes plain values and returns plain values,
so each rule can be tested exactly. The services call these; nothing here changes
during a live game, which is what makes it safe.

Rules (from the project spec):
  - Correct answer:  points = round(base_points × (1 − 0.5 × time_taken / time_limit))
                     i.e. an instant answer earns the full base points, an answer at
                     the buzzer earns half. Wrong or no answer: 0.
  - time_taken is measured on the SERVER from when answers opened.
  - Answers more than ANSWER_GRACE_MS after the deadline are rejected.
  - Streak: consecutive correct answers; a wrong or missed answer resets it to 0.
  - Ranking tie-break order:
        1. higher total score
        2. more correct answers
        3. lower total response time on correct answers
        4. earlier join
        5. lower participant id (only so two runs always give the same order)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# Network slack after the deadline: an answer tapped at the buzzer can take a few
# hundred milliseconds to reach the server. Inside the grace window it is accepted
# and scored as if it arrived exactly at the deadline (half points).
ANSWER_GRACE_MS = 300

# Two neighbouring ranks this close in score are flagged as a "close battle".
CLOSE_BATTLE_GAP = 100


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC (SQLite drops the timezone; PostgreSQL keeps it)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def response_time_ms(opened_at: datetime, answered_at: datetime) -> int:
    """Milliseconds between answers opening and the answer arriving (never negative)."""
    delta = as_utc(answered_at) - as_utc(opened_at)
    return max(0, int(delta.total_seconds() * 1000))


def is_late(time_ms: int, time_limit_s: int, grace_ms: int = ANSWER_GRACE_MS) -> bool:
    """True when the answer arrived after the deadline plus the grace window."""
    return time_ms > time_limit_s * 1000 + grace_ms


def points_for(correct: bool, time_ms: int, time_limit_s: int, base_points: int) -> int:
    """
    Points for one answer.

    Times are clamped to [0, time_limit] so an answer inside the grace window
    scores exactly half, never less. Rounds half up (500.5 -> 501) so results
    don't depend on Python's banker's rounding.
    """
    if not correct or base_points <= 0:
        return 0
    limit_ms = max(1, time_limit_s * 1000)
    taken = min(max(time_ms, 0), limit_ms)
    # points = base * (1 - taken / (2 * limit)). Keep this in integer
    # arithmetic so half-point rounding cannot drift with floating precision.
    numerator = base_points * (2 * limit_ms - taken)
    denominator = 2 * limit_ms
    return (numerator + limit_ms) // denominator


def next_streak(current: int, best: int, correct: bool) -> tuple[int, int]:
    """Return (new current streak, new best streak) after one question."""
    if not correct:
        return 0, best
    current += 1
    return current, max(best, current)


@dataclass(frozen=True)
class Standing:
    """What the ranking needs to know about one player."""
    participant_id: int
    score: int
    correct_count: int
    correct_time_ms: int
    joined_at: datetime


def rank_key(s: Standing) -> tuple:
    return (-s.score, -s.correct_count, s.correct_time_ms, as_utc(s.joined_at), s.participant_id)


def rank(standings: list[Standing]) -> dict[int, int]:
    """
    Map participant_id -> rank (1 = first). Every player gets a distinct rank:
    the tie-break chain always separates two players, so the order is identical
    on every run.
    """
    ordered = sorted(standings, key=rank_key)
    return {s.participant_id: position for position, s in enumerate(ordered, start=1)}


def rank_delta(previous_rank: int | None, current_rank: int | None) -> int:
    """Places climbed since the last leaderboard (positive = moved up)."""
    if previous_rank is None or current_rank is None:
        return 0
    return previous_rank - current_rank


@dataclass(frozen=True)
class Climber:
    participant_id: int
    rank_delta: int


def biggest_climbers(ranks: dict[int, tuple[int | None, int | None]], limit: int = 3) -> list[Climber]:
    """
    ranks: participant_id -> (previous_rank, current_rank).
    Players who moved up, biggest jump first (ties: better current rank first).
    """
    climbers = [
        (rank_delta(prev, cur), cur, pid)
        for pid, (prev, cur) in ranks.items()
        if rank_delta(prev, cur) > 0
    ]
    climbers.sort(key=lambda item: (-item[0], item[1]))
    return [Climber(pid, delta) for delta, _cur, pid in climbers[:limit]]


@dataclass(frozen=True)
class CloseBattle:
    rank: int                  # the higher of the two ranks (smaller number)
    participant_ids: tuple[int, int]
    gap: int


def close_battles(
    ordered_scores: list[tuple[int, int]], gap: int = CLOSE_BATTLE_GAP, top: int = 10
) -> list[CloseBattle]:
    """
    ordered_scores: [(participant_id, score)] in rank order (rank 1 first).
    Flags neighbouring pairs within the top `top` ranks whose scores differ by
    `gap` points or less.
    """
    battles: list[CloseBattle] = []
    head = ordered_scores[:top]
    for index in range(len(head) - 1):
        (upper_id, upper_score), (lower_id, lower_score) = head[index], head[index + 1]
        difference = upper_score - lower_score
        if difference <= gap:
            battles.append(CloseBattle(index + 1, (upper_id, lower_id), difference))
    return battles
