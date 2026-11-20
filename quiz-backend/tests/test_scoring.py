"""
test_scoring.py — Tests for the pure scoring rules in app/scoring.py.

Covers:
  - Points formula with exact numbers (instant, half time, at the buzzer)
  - Grace window: accepted late answers score exactly half
  - Rounding half up (not banker's rounding)
  - Wrong answers and zero-point questions score 0
  - Response time from server timestamps (naive SQLite times, time zones)
  - Late-answer boundary
  - Streaks: increment, best streak kept, reset on wrong or missed
  - Ranking: each tie-break step in order, distinct ranks
  - Rank delta, biggest climbers, close battles
"""

from datetime import datetime, timedelta, timezone

import pytest

from app import scoring
from app.scoring import Standing

T0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


def _standing(pid, score=0, correct=0, time_ms=0, joined_offset_s=0):
    return Standing(
        participant_id=pid,
        score=score,
        correct_count=correct,
        correct_time_ms=time_ms,
        joined_at=T0 + timedelta(seconds=joined_offset_s),
    )


class TestPointsFor:
    """points = round(base × (1 − 0.5 × time_taken / time_limit)) for a correct answer."""

    @pytest.mark.parametrize(
        "time_ms, time_limit_s, base, expected",
        [
            (0, 30, 1000, 1000),        # instant: full points
            (15_000, 30, 1000, 750),    # half the time gone
            (30_000, 30, 1000, 500),    # at the buzzer: half points
            (3_000, 30, 1000, 950),
            (3_018, 30, 1000, 950),     # 949.7 rounds to 950
            (6_000, 20, 1000, 850),
            (2_000, 20, 2000, 1900),
            (1, 30, 1000, 1000),        # 999.98 rounds to 1000
        ],
    )
    def test_exact_points(self, time_ms, time_limit_s, base, expected):
        assert scoring.points_for(True, time_ms, time_limit_s, base) == expected

    def test_grace_window_scores_exactly_half(self):
        assert scoring.points_for(True, 30_000 + scoring.ANSWER_GRACE_MS, 30, 1000) == 500
        assert scoring.points_for(True, 30_001, 30, 1000) == 500

    def test_rounds_half_up(self):
        """1001 × 0.5 = 500.5 → 501 (Python's round() would give 500)."""
        assert scoring.points_for(True, 30_000, 30, 1001) == 501
        assert scoring.points_for(True, 30_000, 30, 1) == 1

    def test_wrong_answer_scores_zero(self):
        assert scoring.points_for(False, 0, 30, 1000) == 0
        assert scoring.points_for(False, 15_000, 30, 1000) == 0

    def test_zero_point_question_scores_zero(self):
        assert scoring.points_for(True, 0, 30, 0) == 0

    def test_negative_time_counts_as_instant(self):
        assert scoring.points_for(True, -500, 30, 1000) == 1000


class TestResponseTime:
    def test_milliseconds_between_timestamps(self):
        assert scoring.response_time_ms(T0, T0 + timedelta(seconds=1, milliseconds=250)) == 1250

    def test_naive_times_are_treated_as_utc(self):
        """SQLite drops the time zone; a naive opened_at must still line up."""
        naive_open = T0.replace(tzinfo=None)
        assert scoring.response_time_ms(naive_open, T0 + timedelta(seconds=2)) == 2000

    def test_other_time_zones_are_converted(self):
        ist = timezone(timedelta(hours=5, minutes=30))
        answered = (T0 + timedelta(seconds=2)).astimezone(ist)
        assert scoring.response_time_ms(T0, answered) == 2000

    def test_never_negative(self):
        assert scoring.response_time_ms(T0, T0 - timedelta(seconds=1)) == 0

    def test_as_utc(self):
        assert scoring.as_utc(T0.replace(tzinfo=None)) == T0
        assert scoring.as_utc(T0).tzinfo == timezone.utc


class TestIsLate:
    def test_grace_is_300_ms(self):
        assert scoring.ANSWER_GRACE_MS == 300

    def test_on_time_and_inside_grace_are_accepted(self):
        assert scoring.is_late(30_000, 30) is False
        assert scoring.is_late(30_300, 30) is False   # deadline + grace exactly

    def test_after_grace_is_late(self):
        assert scoring.is_late(30_301, 30) is True

    def test_custom_grace(self):
        assert scoring.is_late(30_001, 30, grace_ms=0) is True
        assert scoring.is_late(30_000, 30, grace_ms=0) is False


class TestStreaks:
    def test_first_correct_starts_streak(self):
        assert scoring.next_streak(0, 0, True) == (1, 1)

    def test_correct_extends_streak_and_best(self):
        assert scoring.next_streak(5, 5, True) == (6, 6)

    def test_best_streak_kept_when_current_is_lower(self):
        assert scoring.next_streak(2, 5, True) == (3, 5)

    def test_wrong_or_missed_resets_current_keeps_best(self):
        assert scoring.next_streak(4, 6, False) == (0, 6)
        assert scoring.next_streak(0, 0, False) == (0, 0)


class TestRanking:
    def test_higher_score_first(self):
        ranks = scoring.rank([_standing(1, score=500), _standing(2, score=900)])
        assert ranks == {2: 1, 1: 2}

    def test_tie_on_score_more_correct_answers_first(self):
        ranks = scoring.rank([_standing(1, score=1000, correct=1), _standing(2, score=1000, correct=2)])
        assert ranks == {2: 1, 1: 2}

    def test_tie_on_correct_lower_total_time_first(self):
        ranks = scoring.rank([
            _standing(1, score=1000, correct=2, time_ms=9_000),
            _standing(2, score=1000, correct=2, time_ms=4_000),
        ])
        assert ranks == {2: 1, 1: 2}

    def test_tie_on_time_earlier_join_first(self):
        ranks = scoring.rank([
            _standing(1, score=1000, correct=2, time_ms=4_000, joined_offset_s=10),
            _standing(2, score=1000, correct=2, time_ms=4_000, joined_offset_s=5),
        ])
        assert ranks == {2: 1, 1: 2}

    def test_full_tie_lower_participant_id_first(self):
        ranks = scoring.rank([_standing(7), _standing(3)])
        assert ranks == {3: 1, 7: 2}

    def test_score_beats_every_later_tie_break(self):
        """One point more outranks more correct answers, faster time and earlier join."""
        ranks = scoring.rank([
            _standing(1, score=1000, correct=3, time_ms=1_000, joined_offset_s=0),
            _standing(2, score=1001, correct=1, time_ms=9_000, joined_offset_s=60),
        ])
        assert ranks == {2: 1, 1: 2}

    def test_whole_chain_in_order(self):
        players = [
            _standing(10, score=900),
            _standing(11, score=1000, correct=1),
            _standing(12, score=1000, correct=2, time_ms=8_000),
            _standing(13, score=1000, correct=2, time_ms=5_000, joined_offset_s=9),
            _standing(14, score=1000, correct=2, time_ms=5_000, joined_offset_s=3),
            _standing(16, score=1000, correct=2, time_ms=5_000, joined_offset_s=1),
            _standing(15, score=1000, correct=2, time_ms=5_000, joined_offset_s=1),
        ]
        ranks = scoring.rank(players)
        assert sorted(ranks, key=ranks.get) == [15, 16, 14, 13, 12, 11, 10]

    def test_naive_and_aware_join_times_compare(self):
        naive = Standing(1, 0, 0, 0, (T0 + timedelta(seconds=1)).replace(tzinfo=None))
        aware = Standing(2, 0, 0, 0, T0)
        assert scoring.rank([naive, aware]) == {2: 1, 1: 2}

    def test_ranks_are_distinct_and_start_at_one(self):
        ranks = scoring.rank([_standing(pid) for pid in range(1, 6)])
        assert sorted(ranks.values()) == [1, 2, 3, 4, 5]

    def test_empty(self):
        assert scoring.rank([]) == {}


class TestRankDelta:
    def test_moved_up_is_positive(self):
        assert scoring.rank_delta(5, 2) == 3

    def test_moved_down_is_negative(self):
        assert scoring.rank_delta(2, 5) == -3

    def test_no_previous_rank_is_zero(self):
        assert scoring.rank_delta(None, 1) == 0
        assert scoring.rank_delta(1, None) == 0


class TestBiggestClimbers:
    def test_biggest_jump_first_then_better_rank(self):
        climbers = scoring.biggest_climbers({
            1: (5, 1),      # +4
            2: (4, 2),      # +2
            3: (6, 3),      # +3
            4: (7, 4),      # +3, worse current rank than player 3
            5: (1, 5),      # dropped
            6: (None, 6),   # new: no previous rank
        })
        assert [(c.participant_id, c.rank_delta) for c in climbers] == [(1, 4), (3, 3), (4, 3)]

    def test_limit(self):
        climbers = scoring.biggest_climbers({1: (3, 1), 2: (4, 2)}, limit=1)
        assert [c.participant_id for c in climbers] == [1]

    def test_nobody_moved_up(self):
        assert scoring.biggest_climbers({1: (1, 1), 2: (1, 2)}) == []


class TestCloseBattles:
    def test_gap_of_100_or_less_is_a_battle(self):
        battles = scoring.close_battles([(1, 1000), (2, 950), (3, 800), (4, 700)])
        assert [(b.rank, b.participant_ids, b.gap) for b in battles] == [
            (1, (1, 2), 50),
            (3, (3, 4), 100),   # exactly the gap still counts
        ]

    def test_default_gap_is_100(self):
        assert scoring.CLOSE_BATTLE_GAP == 100
        assert scoring.close_battles([(1, 1000), (2, 899)]) == []

    def test_only_top_ranks_are_checked(self):
        scores = [(1, 1000), (2, 500), (3, 490)]
        assert scoring.close_battles(scores, top=2) == []
        assert len(scoring.close_battles(scores, top=3)) == 1

    def test_custom_gap(self):
        assert scoring.close_battles([(1, 1000), (2, 990)], gap=5) == []
