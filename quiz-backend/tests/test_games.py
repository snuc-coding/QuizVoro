"""
test_games.py — Tests for the live game endpoints (Developer 2).

Covers:
  - Create game (PIN, ownership, auth)
  - Join: success, wrong PIN, taken nickname, blocked nickname, ended quiz
  - Rejoin: same player and score, bad token, other game's token, removed player
  - Current question: no correct answers, timing, question number / total,
    already_answered, paused, none open
  - Submit answer: accepted, late, grace window, duplicate, wrong question,
    wrong option, paused, not open yet, after scoring, removed player;
    selected_option as a letter or index (mapping, range, exactly-one rule)
  - Score question: exact points, ranks, streak resets, scoring twice changes
    nothing, owner only, removed players ignored
  - Leaderboard: overall, per round, rank_delta, climbers, close battles, limit
  - My stats: before and after scoring, last result
  - The correct answer is never leaked to players before scoring

Developer 3 owns the game lifecycle (start, next question, pause, remove a
player), so these tests set those columns directly through the db fixture.
Stored response times are pinned before scoring so the points are exact.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models import Admin, Answer, Game, GameParticipant, Option, Question
from app.security import hash_password
from app.services import answer_service, participant_service

API = "/api/v1"


# ── Helpers ───────────────────────────────────────────────────────────────────

@dataclass
class Q:
    id: int
    round_id: int
    right: int
    wrong: int
    other: int


@dataclass
class Quiz:
    id: int
    round1: int
    round2: int
    q1: Q
    q2: Q
    q3: Q


@dataclass
class Player:
    id: int
    token: str

    @property
    def headers(self) -> dict:
        return {"X-Participant-Token": self.token}


def _question(client, headers, round_id, order, time_limit=30, points=1000) -> Q:
    r = client.post(
        f"{API}/rounds/{round_id}/questions",
        json={
            "question_text": f"Question {order}",
            "time_limit": time_limit,
            "points": points,
            "question_order": order,
            "options": [
                {"option_text": "Right", "is_correct": True},
                {"option_text": "Wrong", "is_correct": False},
                {"option_text": "Other", "is_correct": False},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    ids = {o["option_text"]: o["id"] for o in r.json()["options"]}
    return Q(r.json()["id"], round_id, ids["Right"], ids["Wrong"], ids["Other"])


def _make_quiz(client, headers) -> Quiz:
    """Round 1: Q1 and Q2 (30 s, 1000 points). Round 2: Q3 (20 s, 2000 points)."""
    quiz_id = client.post(f"{API}/quizzes", json={"title": "Live Quiz"}, headers=headers).json()["id"]
    rounds = [
        client.post(
            f"{API}/quizzes/{quiz_id}/rounds",
            json={"title": f"Round {n}", "round_number": n},
            headers=headers,
        ).json()["id"]
        for n in (1, 2)
    ]
    return Quiz(
        id=quiz_id,
        round1=rounds[0],
        round2=rounds[1],
        q1=_question(client, headers, rounds[0], 1),
        q2=_question(client, headers, rounds[0], 2),
        q3=_question(client, headers, rounds[1], 1, time_limit=20, points=2000),
    )


def _create_game(client, headers, quiz_id) -> dict:
    r = client.post(f"{API}/games", json={"quiz_id": quiz_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _join(client, pin, nickname) -> Player:
    r = client.post(f"{API}/games/join", json={"pin": pin, "nickname": nickname})
    assert r.status_code == 201, r.text
    return Player(r.json()["participant_id"], r.json()["token"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _update_game(db, game_id, **values) -> None:
    db.expire_all()
    game = db.get(Game, game_id)
    for name, value in values.items():
        setattr(game, name, value)
    db.commit()


def _open(db, game_id, question: Q, seconds_ago=1.0) -> None:
    """What Developer 3 does when a question goes live."""
    _update_game(
        db, game_id,
        status="active",
        current_question_id=question.id,
        current_question_started_at=_now() - timedelta(seconds=seconds_ago),
    )


def _remove(db, player: Player) -> None:
    """What Developer 3 does when the host kicks a player."""
    db.expire_all()
    db.get(GameParticipant, player.id).is_active = False
    db.commit()


def _row(db, player: Player) -> GameParticipant:
    db.expire_all()
    return db.get(GameParticipant, player.id)


def _answer(client, game_id, player: Player, question: Q, option_id):
    return client.post(
        f"{API}/games/{game_id}/answers",
        json={"question_id": question.id, "option_id": option_id},
        headers=player.headers,
    )


def _answer_rows(db, question: Q) -> list[Answer]:
    db.expire_all()
    return db.query(Answer).filter(Answer.question_id == question.id).all()


def _play(client, db, game_id, player: Player, question: Q, option_id, time_ms) -> None:
    """Answer through the API, then pin the stored response time so points are exact."""
    r = _answer(client, game_id, player, question, option_id)
    assert r.status_code == 201, r.text
    db.expire_all()
    answer = db.query(Answer).filter_by(game_participant_id=player.id, question_id=question.id).one()
    answer.response_time_ms = time_ms
    db.commit()


def _score(client, headers, game_id, question: Q):
    return client.post(f"{API}/games/{game_id}/questions/{question.id}/score", headers=headers)


def _board(client, game_id, **params) -> dict:
    r = client.get(f"{API}/games/{game_id}/leaderboard", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _me(client, game_id, player: Player) -> dict:
    r = client.get(f"{API}/games/{game_id}/me", headers=player.headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def quiz(client, auth_headers) -> Quiz:
    return _make_quiz(client, auth_headers)


@pytest.fixture
def game(client, auth_headers, quiz) -> dict:
    return _create_game(client, auth_headers, quiz.id)


@pytest.fixture
def other_headers(client, db) -> dict:
    """A second admin who does not own the quiz."""
    db.add(Admin(
        username="otheradmin",
        email="other@example.com",
        hashed_password=hash_password("otherpassword123"),
        is_active=True,
    ))
    db.commit()
    r = client.post(f"{API}/admin/login", json={"username": "otheradmin", "password": "otherpassword123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def players(client, game) -> list[Player]:
    """Asha, Bala, Chitra and Dev, joined in that order."""
    return [_join(client, game["pin"], name) for name in ("Asha", "Bala", "Chitra", "Dev")]


@pytest.fixture
def after_q1(client, db, auth_headers, quiz, game, players) -> dict:
    """Q1 scored: Asha right in 3 s (950), Bala right in 15 s (750), Chitra wrong, Dev silent."""
    asha, bala, chitra, _dev = players
    _open(db, game["id"], quiz.q1)
    _play(client, db, game["id"], asha, quiz.q1, quiz.q1.right, 3_000)
    _play(client, db, game["id"], bala, quiz.q1, quiz.q1.right, 15_000)
    _play(client, db, game["id"], chitra, quiz.q1, quiz.q1.wrong, 1_000)
    r = _score(client, auth_headers, game["id"], quiz.q1)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def after_q2(client, db, auth_headers, quiz, game, players, after_q1) -> dict:
    """
    Q2 scored: Asha wrong, Bala right instantly (1000), Chitra right at the
    buzzer (500), Dev right inside the grace window (500).
    """
    asha, bala, chitra, dev = players
    _open(db, game["id"], quiz.q2)
    _play(client, db, game["id"], asha, quiz.q2, quiz.q2.wrong, 2_000)
    _play(client, db, game["id"], bala, quiz.q2, quiz.q2.right, 0)
    _play(client, db, game["id"], chitra, quiz.q2, quiz.q2.right, 30_000)
    _play(client, db, game["id"], dev, quiz.q2, quiz.q2.right, 30_200)
    r = _score(client, auth_headers, game["id"], quiz.q2)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def after_q3(client, db, auth_headers, quiz, game, players, after_q2) -> dict:
    """Dev is removed. Q3 (round 2) scored: Asha right in 2 s (1900), Bala silent, Chitra wrong."""
    asha, _bala, chitra, dev = players
    _remove(db, dev)
    _open(db, game["id"], quiz.q3)
    _play(client, db, game["id"], asha, quiz.q3, quiz.q3.right, 2_000)
    _play(client, db, game["id"], chitra, quiz.q3, quiz.q3.wrong, 4_000)
    r = _score(client, auth_headers, game["id"], quiz.q3)
    assert r.status_code == 200, r.text
    return r.json()


# ── Create game ───────────────────────────────────────────────────────────────

class TestCreateGame:
    """Tests for POST /api/v1/games"""

    def test_create_game(self, client: TestClient, auth_headers, quiz):
        r = client.post(f"{API}/games", json={"quiz_id": quiz.id}, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["quiz_id"] == quiz.id
        assert data["status"] == "lobby"
        assert data["current_question_id"] is None
        assert len(data["pin"]) == 8 and data["pin"].isdigit()

    def test_each_game_gets_its_own_pin(self, client, auth_headers, quiz):
        first = _create_game(client, auth_headers, quiz.id)
        second = _create_game(client, auth_headers, quiz.id)
        assert first["pin"] != second["pin"]

    def test_pin_is_always_8_digits(self, db, monkeypatch):
        """The smallest and largest PINs the generator can draw are both 8 digits."""
        bounds = []
        for draw, expected in ((0, "10000000"), (89_999_999, "99999999")):
            monkeypatch.setattr(
                participant_service.secrets, "randbelow",
                lambda bound, draw=draw: bounds.append(bound) or draw,
            )
            assert participant_service._new_pin(db) == expected
        assert bounds == [90_000_000, 90_000_000]

    def test_pin_already_in_use_is_skipped(self, client, auth_headers, quiz, monkeypatch):
        draws = iter([0, 0, 1])     # the second game draws the first game's PIN, then a free one
        monkeypatch.setattr(participant_service.secrets, "randbelow", lambda bound: next(draws))
        first = _create_game(client, auth_headers, quiz.id)
        second = _create_game(client, auth_headers, quiz.id)
        assert (first["pin"], second["pin"]) == ("10000000", "10000001")

    def test_requires_admin(self, client, quiz):
        r = client.post(f"{API}/games", json={"quiz_id": quiz.id})
        assert r.status_code == 403

    def test_other_admins_quiz_is_forbidden(self, client, quiz, other_headers):
        r = client.post(f"{API}/games", json={"quiz_id": quiz.id}, headers=other_headers)
        assert r.status_code == 403

    def test_unknown_quiz_404(self, client, auth_headers):
        r = client.post(f"{API}/games", json={"quiz_id": 9999}, headers=auth_headers)
        assert r.status_code == 404


# ── Join ──────────────────────────────────────────────────────────────────────

class TestJoin:
    """Tests for POST /api/v1/games/join"""

    def test_join_returns_token(self, client, game):
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Rathi"})
        assert r.status_code == 201
        data = r.json()
        assert data["game_id"] == game["id"]
        assert data["nickname"] == "Rathi"
        assert data["game_status"] == "lobby"
        assert len(data["token"]) >= 20

    def test_nickname_is_cleaned(self, client, game):
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "  Rathi   K  "})
        assert r.json()["nickname"] == "Rathi K"

    def test_wrong_pin_404(self, client, game):
        r = client.post(f"{API}/games/join", json={"pin": "00000000", "nickname": "Rathi"})
        assert r.status_code == 404

    @pytest.mark.parametrize("taken", ["Rathi", "RATHI", "  rathi "])
    def test_taken_nickname_409(self, client, game, taken):
        _join(client, game["pin"], "Rathi")
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": taken})
        assert r.status_code == 409
        assert "taken" in r.json()["detail"]

    def test_same_nickname_in_another_game_is_fine(self, client, auth_headers, quiz, game):
        other = _create_game(client, auth_headers, quiz.id)
        _join(client, game["pin"], "Rathi")
        _join(client, other["pin"], "Rathi")

    @pytest.mark.parametrize("nickname", ["b1tch", "BigDick", "Big Dick", "fuckface", "Shit"])
    def test_blocked_nickname_422(self, client, game, nickname):
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": nickname})
        assert r.status_code == 422
        assert r.json()["detail"] == "Please pick a different nickname."

    @pytest.mark.parametrize("nickname", ["Dickson", "Hassan", "Shitij"])
    def test_real_names_are_not_blocked(self, client, game, nickname):
        _join(client, game["pin"], nickname)

    @pytest.mark.parametrize("nickname", ["", "   ", "!!!", "A" * 17])
    def test_invalid_nickname_422(self, client, game, nickname):
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": nickname})
        assert r.status_code == 422

    def test_cannot_join_finished_game(self, client, db, game):
        _update_game(db, game["id"], status="finished")
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Rathi"})
        assert r.status_code == 409

    def test_late_joiner_can_join_running_game(self, client, db, quiz, game):
        _open(db, game["id"], quiz.q1)
        r = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Rathi"})
        assert r.status_code == 201
        assert r.json()["game_status"] == "active"


# ── Rejoin ────────────────────────────────────────────────────────────────────

class TestRejoin:
    """Tests for POST /api/v1/games/rejoin"""

    def test_rejoin_keeps_player_and_score(self, client, game, players, after_q1):
        asha = players[0]
        r = client.post(f"{API}/games/rejoin", json={"pin": game["pin"], "token": asha.token})
        assert r.status_code == 200
        assert r.json()["participant_id"] == asha.id
        assert r.json()["nickname"] == "Asha"
        assert _me(client, game["id"], asha)["score"] == 950

    def test_unknown_token_401(self, client, game):
        r = client.post(f"{API}/games/rejoin", json={"pin": game["pin"], "token": "not-a-real-token"})
        assert r.status_code == 401

    def test_token_from_another_game_401(self, client, auth_headers, quiz, game):
        other = _create_game(client, auth_headers, quiz.id)
        stranger = _join(client, other["pin"], "Rathi")
        r = client.post(f"{API}/games/rejoin", json={"pin": game["pin"], "token": stranger.token})
        assert r.status_code == 401

    def test_wrong_pin_404(self, client, game, players):
        r = client.post(f"{API}/games/rejoin", json={"pin": "00000000", "token": players[0].token})
        assert r.status_code == 404

    def test_removed_player_403(self, client, db, game, players):
        _remove(db, players[0])
        r = client.post(f"{API}/games/rejoin", json={"pin": game["pin"], "token": players[0].token})
        assert r.status_code == 403


# ── Current question ──────────────────────────────────────────────────────────

class TestCurrentQuestion:
    """Tests for GET /api/v1/games/{gameId}/questions/current"""

    def _get(self, client, game, player):
        return client.get(f"{API}/games/{game['id']}/questions/current", headers=player.headers)

    def test_returns_question_without_correct_answers(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        r = self._get(client, game, players[0])
        assert r.status_code == 200
        question = r.json()["question"]
        assert question["id"] == quiz.q1.id
        assert {o["id"] for o in question["options"]} == {quiz.q1.right, quiz.q1.wrong, quiz.q1.other}
        for option in question["options"]:
            assert set(option) == {"id", "option_text", "question_id"}
        assert "is_correct" not in r.text

    def test_options_are_listed_by_id(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        ids = [o["id"] for o in self._get(client, game, players[0]).json()["question"]["options"]]
        assert ids == sorted(ids) == [quiz.q1.right, quiz.q1.wrong, quiz.q1.other]

    def test_options_sorted_even_if_loaded_out_of_order(self):
        """The database may return options in any order; the phone always gets them by id."""
        question = Question(
            id=1, question_text="?", question_type="MCQ", time_limit=30, points=1000,
            question_order=1, media_url=None, media_type=None, round_id=1,
            options=[Option(id=9, option_text="C", question_id=1), Option(id=3, option_text="A", question_id=1),
                     Option(id=5, option_text="B", question_id=1)],
        )
        out = answer_service.participant_question(question)
        assert [o.id for o in out.options] == [3, 5, 9]
        assert [o.id for o in answer_service.ordered_options(question)] == [3, 5, 9]

    def test_timing(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1, seconds_ago=5)
        data = self._get(client, game, players[0]).json()
        opened = _parse(data["opened_at"])
        deadline = _parse(data["deadline"])
        server_time = _parse(data["server_time"])
        assert deadline - opened == timedelta(seconds=30)
        assert timedelta(seconds=5) <= server_time - opened < timedelta(seconds=8)

    @pytest.mark.parametrize("name, number", [("q1", 1), ("q2", 2), ("q3", 3)])
    def test_question_number_and_total(self, client, db, auth_headers, quiz, game, players, name, number):
        _make_quiz(client, auth_headers)     # another quiz's questions must not count
        _open(db, game["id"], getattr(quiz, name))
        data = self._get(client, game, players[0]).json()
        assert (data["question_number"], data["total_questions"]) == (number, 3)

    def test_question_number_follows_round_then_question_order(self, client, db, auth_headers):
        """Play order is round_number then question_order, not creation order or raw question_order."""
        quiz_id = client.post(f"{API}/quizzes", json={"title": "Out of order"}, headers=auth_headers).json()["id"]
        rounds = {
            number: client.post(
                f"{API}/quizzes/{quiz_id}/rounds",
                json={"title": f"Round {number}", "round_number": number},
                headers=auth_headers,
            ).json()["id"]
            for number in (2, 1)                                   # round 2 created first
        }
        second_round = _question(client, auth_headers, rounds[2], 1)
        round_one_late = _question(client, auth_headers, rounds[1], 10)   # created before order 5
        round_one_early = _question(client, auth_headers, rounds[1], 5)
        game = _create_game(client, auth_headers, quiz_id)
        player = _join(client, game["pin"], "Rathi")

        for question, number in ((round_one_early, 1), (round_one_late, 2), (second_round, 3)):
            _open(db, game["id"], question)
            data = self._get(client, game, player).json()
            assert (data["question"]["id"], data["question_number"], data["total_questions"]) == (question.id, number, 3)

    def test_already_answered_flips_after_answering(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        assert self._get(client, game, players[0]).json()["already_answered"] is False
        _answer(client, game["id"], players[0], quiz.q1, quiz.q1.wrong)
        assert self._get(client, game, players[0]).json()["already_answered"] is True
        assert self._get(client, game, players[1]).json()["already_answered"] is False

    def test_no_question_open_404(self, client, db, game, players):
        _update_game(db, game["id"], status="active")
        assert self._get(client, game, players[0]).status_code == 404

    def test_lobby_409(self, client, game, players):
        assert self._get(client, game, players[0]).status_code == 409

    def test_paused_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _update_game(db, game["id"], status="paused")
        r = self._get(client, game, players[0])
        assert r.status_code == 409
        assert "paused" in r.json()["detail"]

    def test_missing_or_unknown_token_401(self, client, db, quiz, game):
        _open(db, game["id"], quiz.q1)
        assert client.get(f"{API}/games/{game['id']}/questions/current").status_code == 401
        r = client.get(
            f"{API}/games/{game['id']}/questions/current",
            headers={"X-Participant-Token": "not-a-real-token"},
        )
        assert r.status_code == 401

    def test_token_from_another_game_403(self, client, db, auth_headers, quiz, game):
        other = _create_game(client, auth_headers, quiz.id)
        stranger = _join(client, other["pin"], "Rathi")
        _open(db, game["id"], quiz.q1)
        assert self._get(client, game, stranger).status_code == 403

    def test_removed_player_403(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _remove(db, players[0])
        assert self._get(client, game, players[0]).status_code == 403


# ── Submit answer ─────────────────────────────────────────────────────────────

class TestSubmitAnswer:
    """Tests for POST /api/v1/games/{gameId}/answers"""

    def test_answer_is_locked_in(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1, seconds_ago=2)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 201
        data = r.json()
        assert set(data) == {"accepted", "question_id", "option_id", "response_time_ms"}
        assert data["accepted"] is True
        assert data["question_id"] == quiz.q1.id
        assert data["option_id"] == quiz.q1.right
        assert 2_000 <= data["response_time_ms"] < 5_000

        [row] = _answer_rows(db, quiz.q1)
        assert row.chosen_option_id == quiz.q1.right
        assert row.is_correct is None          # decided at scoring
        assert row.points_awarded is None

    def test_reply_is_the_same_for_right_and_wrong(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        right = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        wrong = _answer(client, game["id"], players[1], quiz.q1, quiz.q1.wrong)
        assert right.status_code == wrong.status_code == 201
        assert set(right.json()) == set(wrong.json())
        assert right.json()["accepted"] == wrong.json()["accepted"] is True

    def test_wrong_question_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        r = _answer(client, game["id"], players[0], quiz.q2, quiz.q2.right)
        assert r.status_code == 409
        assert r.json()["detail"] == "That question is not open."

    def test_option_from_another_question_422(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q2.right)
        assert r.status_code == 422

    def test_unknown_option_422(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        assert _answer(client, game["id"], players[0], quiz.q1, 99_999).status_code == 422

    def test_late_answer_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1, seconds_ago=31)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert "Time's up" in r.json()["detail"]
        assert _answer_rows(db, quiz.q1) == []

    def test_answer_in_grace_window_is_accepted(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1, seconds_ago=30.05)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 201
        assert 30_000 < r.json()["response_time_ms"] <= 30_300

    def test_duplicate_answer_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        assert _answer(client, game["id"], players[0], quiz.q1, quiz.q1.wrong).status_code == 201
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert r.json()["detail"] == "You already answered this question."
        [row] = _answer_rows(db, quiz.q1)
        assert row.chosen_option_id == quiz.q1.wrong    # first answer stands

    def test_database_blocks_a_double_tap(self, client, db, quiz, game, players, monkeypatch):
        """Two requests racing past the duplicate check: the unique constraint stops the second."""
        _open(db, game["id"], quiz.q1)
        assert _answer(client, game["id"], players[0], quiz.q1, quiz.q1.wrong).status_code == 201
        monkeypatch.setattr(answer_service, "_answer_of", lambda *args: None)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert len(_answer_rows(db, quiz.q1)) == 1

    # ── selected_option: a letter "A"-"D" or an index 0-3, by option id order ──

    def _pick(self, client, game, player, question, **choice):
        return client.post(
            f"{API}/games/{game['id']}/answers",
            json={"question_id": question.id, **choice},
            headers=player.headers,
        )

    @pytest.mark.parametrize("choice, picked", [
        ("A", "right"), ("a", "right"), (" a ", "right"), (0, "right"),
        ("B", "wrong"), ("b", "wrong"), (1, "wrong"),
        ("C", "other"), ("c", "other"), (2, "other"),
    ])
    def test_selected_option_maps_to_options_by_id(self, client, db, quiz, game, players, choice, picked):
        _open(db, game["id"], quiz.q1)
        r = self._pick(client, game, players[0], quiz.q1, selected_option=choice)
        assert r.status_code == 201, r.text
        expected = getattr(quiz.q1, picked)     # right < wrong < other by id
        assert r.json()["option_id"] == expected
        [row] = _answer_rows(db, quiz.q1)
        assert row.chosen_option_id == expected

    def test_selected_option_d_on_a_four_option_question(self, client, db, auth_headers, quiz, game, players):
        r = client.post(f"{API}/rounds/{quiz.round2}/questions", json={
            "question_text": "Four options",
            "question_order": 2,
            "options": [{"option_text": t, "is_correct": t == "4th"} for t in ("1st", "2nd", "3rd", "4th")],
        }, headers=auth_headers)
        four = Q(r.json()["id"], quiz.round2, 0, 0, 0)
        fourth = max(o["id"] for o in r.json()["options"])
        _open(db, game["id"], four)
        assert self._pick(client, game, players[0], four, selected_option="D").json()["option_id"] == fourth
        assert self._pick(client, game, players[1], four, selected_option=3).json()["option_id"] == fourth

    @pytest.mark.parametrize("choice", ["D", "d", 3])
    def test_selected_option_beyond_the_questions_options_422(self, client, db, quiz, game, players, choice):
        _open(db, game["id"], quiz.q1)        # Q1 has three options: A-C
        r = self._pick(client, game, players[0], quiz.q1, selected_option=choice)
        assert r.status_code == 422
        assert r.json()["detail"] == "That option is not part of this question."
        assert _answer_rows(db, quiz.q1) == []

    def test_option_id_and_selected_option_together_422(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        r = self._pick(client, game, players[0], quiz.q1, option_id=quiz.q1.right, selected_option="A")
        assert r.status_code == 422
        assert _answer_rows(db, quiz.q1) == []

    @pytest.mark.parametrize("choice", [{}, {"option_id": None}, {"selected_option": None}])
    def test_neither_option_id_nor_selected_option_422(self, client, db, quiz, game, players, choice):
        _open(db, game["id"], quiz.q1)
        assert self._pick(client, game, players[0], quiz.q1, **choice).status_code == 422

    @pytest.mark.parametrize("choice", ["E", "z", "", "AB", "2", 4, -1, 1.5, True, [0]])
    def test_bad_selected_option_422(self, client, db, quiz, game, players, choice):
        _open(db, game["id"], quiz.q1)
        assert self._pick(client, game, players[0], quiz.q1, selected_option=choice).status_code == 422

    def test_selected_option_is_still_one_answer_per_question(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        assert self._pick(client, game, players[0], quiz.q1, option_id=quiz.q1.wrong).status_code == 201
        r = self._pick(client, game, players[0], quiz.q1, selected_option="A")
        assert r.status_code == 409
        assert r.json()["detail"] == "You already answered this question."

    def test_answers_by_letter_are_scored(self, client, db, auth_headers, quiz, game, players):
        asha, bala = players[0], players[1]
        _open(db, game["id"], quiz.q1)
        self._pick(client, game, asha, quiz.q1, selected_option="a")
        self._pick(client, game, bala, quiz.q1, selected_option=1)
        result = _score(client, auth_headers, game["id"], quiz.q1).json()
        assert (result["answered"], result["correct"]) == (2, 1)
        assert _row(db, asha).correct_count == 1 and _row(db, asha).total_score > 0
        assert _row(db, bala).total_score == 0

    def test_paused_game_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _update_game(db, game["id"], status="paused")
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert r.json()["detail"] == "The game is paused."

    @pytest.mark.parametrize("game_status", ["lobby", "finished"])
    def test_game_not_running_409(self, client, db, quiz, game, players, game_status):
        _open(db, game["id"], quiz.q1)
        _update_game(db, game["id"], status=game_status)
        assert _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right).status_code == 409

    def test_before_answers_open_409(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1, seconds_ago=-5)   # opens in 5 s ("get ready" screen)
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert r.json()["detail"] == "Answers haven't opened yet."

    def test_after_scoring_409(self, client, db, auth_headers, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _score(client, auth_headers, game["id"], quiz.q1)    # host reveals early
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 409
        assert r.json()["detail"] == "This question is closed."

    def test_removed_player_403(self, client, db, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _remove(db, players[0])
        r = _answer(client, game["id"], players[0], quiz.q1, quiz.q1.right)
        assert r.status_code == 403
        assert r.json()["detail"] == "You were removed from this game."

    def test_token_from_another_game_403(self, client, db, auth_headers, quiz, game):
        other = _create_game(client, auth_headers, quiz.id)
        stranger = _join(client, other["pin"], "Rathi")
        _open(db, game["id"], quiz.q1)
        assert _answer(client, game["id"], stranger, quiz.q1, quiz.q1.right).status_code == 403

    def test_missing_token_401(self, client, db, quiz, game):
        _open(db, game["id"], quiz.q1)
        r = client.post(f"{API}/games/{game['id']}/answers", json={"question_id": quiz.q1.id, "option_id": quiz.q1.right})
        assert r.status_code == 401


# ── Score question ────────────────────────────────────────────────────────────

def _snapshot(db) -> list[tuple]:
    db.expire_all()
    players = [
        (p.id, p.total_score, p.correct_count, p.correct_time_ms, p.current_streak, p.best_streak, p.rank, p.previous_rank)
        for p in db.query(GameParticipant).order_by(GameParticipant.id)
    ]
    answers = [(a.id, a.is_correct, a.points_awarded) for a in db.query(Answer).order_by(Answer.id)]
    return players + answers


def _state(p: GameParticipant) -> tuple:
    """(score, correct, correct time, streak, best streak, rank, previous rank)"""
    return (p.total_score, p.correct_count, p.correct_time_ms, p.current_streak, p.best_streak, p.rank, p.previous_rank)


class TestScoreQuestion:
    """Tests for POST /api/v1/games/{gameId}/questions/{questionId}/score"""

    def test_reveal_result(self, quiz, game, after_q1):
        assert after_q1 == {
            "game_id": game["id"],
            "question_id": quiz.q1.id,
            "correct_option_id": quiz.q1.right,
            "distribution": [
                {"option_id": quiz.q1.right, "count": 2},
                {"option_id": quiz.q1.wrong, "count": 1},
                {"option_id": quiz.q1.other, "count": 0},
            ],
            "answered": 3,
            "correct": 2,
            "already_scored": False,
        }

    def test_points_streaks_and_ranks_after_first_question(self, db, quiz, players, after_q1):
        asha, bala, chitra, dev = (_row(db, p) for p in players)
        assert _state(asha) == (950, 1, 3_000, 1, 1, 1, None)
        assert _state(bala) == (750, 1, 15_000, 1, 1, 2, None)
        assert _state(chitra) == (0, 0, 0, 0, 0, 3, None)
        assert _state(dev) == (0, 0, 0, 0, 0, 4, None)     # tied with Chitra, joined later

        answers = {a.game_participant_id: a for a in _answer_rows(db, quiz.q1)}
        assert (answers[asha.id].is_correct, answers[asha.id].points_awarded) == (True, 950)
        assert (answers[bala.id].is_correct, answers[bala.id].points_awarded) == (True, 750)
        assert (answers[chitra.id].is_correct, answers[chitra.id].points_awarded) == (False, 0)
        assert dev.id not in answers

    def test_second_question_grace_answer_and_tie_break(self, db, players, after_q2):
        asha, bala, chitra, dev = (_row(db, p) for p in players)
        assert (bala.total_score, bala.rank, bala.previous_rank, bala.current_streak) == (1750, 1, 2, 2)
        assert (asha.total_score, asha.rank, asha.previous_rank, asha.current_streak, asha.best_streak) == (950, 2, 1, 0, 1)
        assert (chitra.total_score, chitra.correct_time_ms, chitra.rank) == (500, 30_000, 3)
        # The grace-window answer scores exactly half, and its time counts as the
        # deadline: Dev ties Chitra on every rule but join order.
        assert (dev.total_score, dev.correct_time_ms, dev.rank) == (500, 30_000, 4)
        assert (after_q2["answered"], after_q2["correct"]) == (4, 3)

    def test_missed_question_resets_streak(self, client, db, auth_headers, quiz, game, players, after_q2):
        bala = players[1]
        assert _row(db, bala).current_streak == 2
        _open(db, game["id"], quiz.q3)
        _play(client, db, game["id"], players[0], quiz.q3, quiz.q3.right, 1_000)
        _score(client, auth_headers, game["id"], quiz.q3)
        assert (_row(db, bala).current_streak, _row(db, bala).best_streak) == (0, 2)

    def test_scoring_twice_changes_nothing(self, client, db, auth_headers, quiz, game, after_q1):
        before = _snapshot(db)
        r = _score(client, auth_headers, game["id"], quiz.q1)
        assert r.status_code == 200
        assert r.json() == {**after_q1, "already_scored": True}
        assert _snapshot(db) == before

    def test_repeat_after_next_question_opened(self, client, db, auth_headers, quiz, game, after_q1):
        _open(db, game["id"], quiz.q2)
        before = _snapshot(db)
        r = _score(client, auth_headers, game["id"], quiz.q1)
        assert r.status_code == 200
        assert r.json()["already_scored"] is True
        assert _snapshot(db) == before

    def test_racing_reveals_score_once(self, client, db, auth_headers, quiz, game, after_q1, monkeypatch):
        """A second reveal that slips past the pre-check hits the scored_questions guard."""
        before = _snapshot(db)
        monkeypatch.setattr(answer_service, "_is_scored", lambda *args: False)
        r = _score(client, auth_headers, game["id"], quiz.q1)
        assert r.status_code == 200
        assert r.json() == {**after_q1, "already_scored": True}
        assert _snapshot(db) == before

    def test_only_quiz_owner_can_score(self, client, db, quiz, game, other_headers):
        _open(db, game["id"], quiz.q1)
        assert _score(client, other_headers, game["id"], quiz.q1).status_code == 403
        assert _score(client, {}, game["id"], quiz.q1).status_code == 403

    def test_only_open_question_can_be_scored(self, client, db, auth_headers, quiz, game, players):
        _open(db, game["id"], quiz.q1)
        _play(client, db, game["id"], players[0], quiz.q1, quiz.q1.right, 1_000)
        before = _snapshot(db)
        r = _score(client, auth_headers, game["id"], quiz.q2)
        assert r.status_code == 409
        assert r.json()["detail"] == "Only the open question can be scored."
        assert _snapshot(db) == before

    def test_nothing_open_409(self, client, auth_headers, quiz, game):
        assert _score(client, auth_headers, game["id"], quiz.q1).status_code == 409

    def test_question_from_another_quiz_404(self, client, db, auth_headers, quiz, game):
        other_quiz = _make_quiz(client, auth_headers)
        _open(db, game["id"], quiz.q1)
        assert _score(client, auth_headers, game["id"], other_quiz.q1).status_code == 404

    def test_unknown_game_404(self, client, auth_headers, quiz):
        assert _score(client, auth_headers, 9999, quiz.q1).status_code == 404

    def test_removed_player_is_not_scored_or_ranked(self, client, db, auth_headers, quiz, game, players):
        asha, bala, chitra, dev = players
        _open(db, game["id"], quiz.q1)
        _play(client, db, game["id"], dev, quiz.q1, quiz.q1.right, 1_000)
        _play(client, db, game["id"], asha, quiz.q1, quiz.q1.right, 3_000)
        _remove(db, dev)
        result = _score(client, auth_headers, game["id"], quiz.q1).json()
        assert (result["answered"], result["correct"]) == (1, 1)
        assert (_row(db, dev).total_score, _row(db, dev).rank) == (0, None)
        assert [_row(db, p).rank for p in (asha, bala, chitra)] == [1, 2, 3]
        [dev_answer] = [a for a in _answer_rows(db, quiz.q1) if a.game_participant_id == dev.id]
        assert dev_answer.is_correct is None and dev_answer.points_awarded is None


# ── Leaderboard ───────────────────────────────────────────────────────────────

def _top(board) -> list[tuple]:
    return [(e["rank"], e["nickname"], e["score"], e["rank_delta"]) for e in board["top"]]


class TestLeaderboard:
    """Tests for GET /api/v1/games/{gameId}/leaderboard"""

    def test_before_any_scoring(self, client, game, players):
        board = _board(client, game["id"])
        assert _top(board) == [(1, "Asha", 0, 0), (2, "Bala", 0, 0), (3, "Chitra", 0, 0), (4, "Dev", 0, 0)]
        assert (board["total_participants"], board["scored_questions"]) == (4, 0)
        assert board["climbers"] == [] and board["close_battles"] == []

    def test_overall_after_two_questions(self, client, game, players, after_q2):
        board = _board(client, game["id"])
        assert _top(board) == [(1, "Bala", 1750, 1), (2, "Asha", 950, -1), (3, "Chitra", 500, 0), (4, "Dev", 500, 0)]
        assert [e["streak"] for e in board["top"]] == [2, 0, 1, 1]
        assert [e["correct_count"] for e in board["top"]] == [2, 1, 1, 1]
        assert board["climbers"] == [{"participant_id": players[1].id, "nickname": "Bala", "rank_delta": 1}]
        assert board["close_battles"] == [{"rank": 3, "participant_ids": [players[2].id, players[3].id], "gap": 0}]
        assert (board["round_id"], board["total_participants"], board["scored_questions"]) == (None, 4, 2)

    def test_limit(self, client, game, after_q2):
        assert [e["nickname"] for e in _board(client, game["id"], limit=2)["top"]] == ["Bala", "Asha"]
        assert client.get(f"{API}/games/{game['id']}/leaderboard", params={"limit": 0}).status_code == 422

    def test_removed_player_left_out(self, client, game, after_q3):
        board = _board(client, game["id"])
        assert _top(board) == [(1, "Asha", 2850, 1), (2, "Bala", 1750, -1), (3, "Chitra", 500, 0)]
        assert board["total_participants"] == 3

    def test_round_one_standings(self, client, quiz, game, players, after_q3):
        board = _board(client, game["id"], round_id=quiz.round1)
        # Round 1 alone, compared with round 1 before Q2 (Asha led after Q1).
        assert _top(board) == [(1, "Bala", 1750, 1), (2, "Asha", 950, -1), (3, "Chitra", 500, 0)]
        assert (board["round_id"], board["scored_questions"], board["total_participants"]) == (quiz.round1, 2, 3)
        assert [c["nickname"] for c in board["climbers"]] == ["Bala"]

    def test_round_two_standings(self, client, quiz, game, players, after_q3):
        board = _board(client, game["id"], round_id=quiz.round2)
        assert _top(board) == [(1, "Asha", 1900, 0), (2, "Bala", 0, 0), (3, "Chitra", 0, 0)]
        assert board["scored_questions"] == 1
        assert board["climbers"] == []
        assert board["close_battles"] == [{"rank": 2, "participant_ids": [players[1].id, players[2].id], "gap": 0}]

    def test_round_not_in_this_quiz_404(self, client, auth_headers, game):
        other_quiz = _make_quiz(client, auth_headers)
        r = client.get(f"{API}/games/{game['id']}/leaderboard", params={"round_id": other_quiz.round1})
        assert r.status_code == 404

    def test_unknown_game_404(self, client):
        assert client.get(f"{API}/games/9999/leaderboard").status_code == 404


# ── My stats ──────────────────────────────────────────────────────────────────

class TestMyStats:
    """Tests for GET /api/v1/games/{gameId}/me"""

    def test_before_scoring(self, client, game, players):
        assert _me(client, game["id"], players[0]) == {
            "participant_id": players[0].id,
            "nickname": "Asha",
            "score": 0,
            "rank": None,
            "rank_delta": 0,
            "streak": 0,
            "best_streak": 0,
            "correct_count": 0,
            "last_result": None,
        }

    def test_after_scoring(self, client, quiz, game, players, after_q1):
        asha, _bala, chitra, dev = players
        me = _me(client, game["id"], asha)
        assert (me["score"], me["rank"], me["streak"], me["best_streak"], me["correct_count"]) == (950, 1, 1, 1, 1)
        assert me["last_result"] == {"question_id": quiz.q1.id, "answered": True, "is_correct": True, "points": 950}
        assert _me(client, game["id"], chitra)["last_result"] == {
            "question_id": quiz.q1.id, "answered": True, "is_correct": False, "points": 0,
        }
        assert _me(client, game["id"], dev)["last_result"] == {
            "question_id": quiz.q1.id, "answered": False, "is_correct": False, "points": 0,
        }

    def test_rank_delta(self, client, game, players, after_q2):
        asha, bala = players[0], players[1]
        assert (_me(client, game["id"], bala)["rank"], _me(client, game["id"], bala)["rank_delta"]) == (1, 1)
        me = _me(client, game["id"], asha)
        assert (me["rank"], me["rank_delta"], me["streak"], me["best_streak"]) == (2, -1, 0, 1)

    def test_requires_token(self, client, game):
        assert client.get(f"{API}/games/{game['id']}/me").status_code == 401

    def test_removed_player_403(self, client, db, game, players):
        _remove(db, players[0])
        assert client.get(f"{API}/games/{game['id']}/me", headers=players[0].headers).status_code == 403


# ── The answer is never leaked before scoring ─────────────────────────────────

class TestNoLeakBeforeScoring:
    """Nothing a player (or the stage screen) can call reveals the open question's answer."""

    def _player_views(self, client, game, player) -> list:
        return [
            client.get(f"{API}/games/{game['id']}/questions/current", headers=player.headers),
            client.get(f"{API}/games/{game['id']}/me", headers=player.headers),
            client.get(f"{API}/games/{game['id']}/leaderboard"),
            client.post(f"{API}/games/rejoin", json={"pin": game["pin"], "token": player.token}),
        ]

    def test_open_question(self, client, db, quiz, game, players):
        asha, bala = players[0], players[1]
        _open(db, game["id"], quiz.q1)
        acks = [
            _answer(client, game["id"], asha, quiz.q1, quiz.q1.right),
            _answer(client, game["id"], bala, quiz.q1, quiz.q1.wrong),
        ]
        responses = acks + self._player_views(client, game, asha) + self._player_views(client, game, bala)
        for r in responses:
            assert r.status_code in (200, 201), r.text
            assert "is_correct" not in r.text
            assert "correct_option" not in r.text
            assert "points_awarded" not in r.text
        assert _me(client, game["id"], asha)["last_result"] is None
        assert all(e["score"] == 0 for e in _board(client, game["id"])["top"])

    def test_next_question_stays_hidden_after_a_reveal(self, client, db, quiz, game, players, after_q1):
        asha = players[0]
        _open(db, game["id"], quiz.q2)
        assert _answer(client, game["id"], asha, quiz.q2, quiz.q2.right).status_code == 201
        current = client.get(f"{API}/games/{game['id']}/questions/current", headers=asha.headers)
        assert "is_correct" not in current.text
        me = _me(client, game["id"], asha)
        assert me["last_result"]["question_id"] == quiz.q1.id     # only the revealed question
        assert (me["score"], me["streak"]) == (950, 1)
        assert _board(client, game["id"])["top"][0]["score"] == 950
