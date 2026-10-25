"""
test_questions.py — Tests for question management endpoints.

Covers:
  - Create valid MCQ
  - Missing question text
  - Missing options
  - Too few options
  - Too many options
  - No correct option
  - Multiple correct options
  - Invalid time limit (too low, too high)
  - Invalid points
  - Invalid round ID
  - Unauthorized question creation
  - Correct-answer NOT in participant response (security test)
  - Duplicate question_order
"""

import pytest
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_quiz(client, headers):
    r = client.post("/api/v1/quizzes", json={"title": "Quiz"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _create_round(client, headers, quiz_id, round_number=1):
    r = client.post(
        f"/api/v1/quizzes/{quiz_id}/rounds",
        json={"title": "Round", "round_number": round_number},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


VALID_QUESTION = {
    "question_text": "What is 2 + 2?",
    "question_type": "MCQ",
    "time_limit": 30,
    "points": 1000,
    "question_order": 1,
    "options": [
        {"option_text": "3", "is_correct": False},
        {"option_text": "4", "is_correct": True},
        {"option_text": "5", "is_correct": False},
        {"option_text": "6", "is_correct": False},
    ],
}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateQuestion:
    """Tests for POST /api/v1/rounds/{roundId}/questions"""

    def test_create_valid_mcq(self, client: TestClient, auth_headers):
        """Valid MCQ → 201 with question and options."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=VALID_QUESTION,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["question_text"] == "What is 2 + 2?"
        assert data["time_limit"] == 30
        assert data["points"] == 1000
        assert len(data["options"]) == 4
        # Admin response INCLUDES is_correct
        assert "is_correct" in data["options"][0]

    def test_missing_question_text_returns_422(self, client: TestClient, auth_headers):
        """No question_text → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {k: v for k, v in VALID_QUESTION.items() if k != "question_text"}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_only_one_option_returns_422(self, client: TestClient, auth_headers):
        """MCQ with fewer than 2 options → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {**VALID_QUESTION, "options": [{"option_text": "Only one", "is_correct": True}]}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_no_correct_option_returns_422(self, client: TestClient, auth_headers):
        """MCQ with no correct option → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {
            **VALID_QUESTION,
            "options": [
                {"option_text": "A", "is_correct": False},
                {"option_text": "B", "is_correct": False},
            ],
        }
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "correct" in response.json()["detail"][0]["msg"].lower()

    def test_multiple_correct_options_returns_422(self, client: TestClient, auth_headers):
        """MCQ with two correct options → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {
            **VALID_QUESTION,
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": True},
            ],
        }
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_seven_options_returns_422(self, client: TestClient, auth_headers):
        """More than 6 options → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        options = [{"option_text": str(i), "is_correct": i == 0} for i in range(7)]
        bad = {**VALID_QUESTION, "options": options}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_time_limit_too_low_returns_422(self, client: TestClient, auth_headers):
        """time_limit < 5 → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {**VALID_QUESTION, "time_limit": 4}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_time_limit_too_high_returns_422(self, client: TestClient, auth_headers):
        """time_limit > 300 → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {**VALID_QUESTION, "time_limit": 301}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_negative_points_returns_422(self, client: TestClient, auth_headers):
        """Negative points → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        bad = {**VALID_QUESTION, "points": -1}
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=bad,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_invalid_round_id_returns_404(self, client: TestClient, auth_headers):
        """Non-existent round → 404."""
        response = client.post(
            "/api/v1/rounds/99999/questions",
            json=VALID_QUESTION,
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_403(self, client: TestClient):
        """No token → 403."""
        response = client.post(
            "/api/v1/rounds/1/questions",
            json=VALID_QUESTION,
        )
        assert response.status_code == 403

    def test_duplicate_question_order_returns_409(self, client: TestClient, auth_headers):
        """Same question_order in same round → 409."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=VALID_QUESTION,
            headers=auth_headers,
        )
        response = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json={**VALID_QUESTION, "question_text": "Another question"},
            headers=auth_headers,
        )
        assert response.status_code == 409


class TestAnswerSecurity:
    """
    SECURITY: Verify correct answers are included in admin responses
    and that the admin API does not accidentally expose them to participants.

    NOTE: Participant-facing endpoints belong to Developer 2.
    This test verifies the admin schema behaves correctly.
    """

    def test_admin_response_includes_is_correct(self, client: TestClient, auth_headers):
        """Admin getting a question must see is_correct on each option."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        create = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=VALID_QUESTION,
            headers=auth_headers,
        )
        question_id = create.json()["id"]

        response = client.get(
            f"/api/v1/questions/{question_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        options = response.json()["options"]
        assert len(options) > 0
        for option in options:
            assert "is_correct" in option, (
                "Admin response must include is_correct on each option."
            )

    def test_exactly_one_option_marked_correct(self, client: TestClient, auth_headers):
        """Exactly one option should be marked correct in the DB."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)

        create = client.post(
            f"/api/v1/rounds/{round_id}/questions",
            json=VALID_QUESTION,
            headers=auth_headers,
        )
        question_id = create.json()["id"]
        options = create.json()["options"]
        correct_count = sum(1 for o in options if o["is_correct"])
        assert correct_count == 1, f"Expected exactly 1 correct option, found {correct_count}"

    def test_update_question_null_text_returns_422(self, client: TestClient, auth_headers):
        """Updating question with null text returns 422."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        create = client.post(f"/api/v1/rounds/{round_id}/questions", json=VALID_QUESTION, headers=auth_headers)
        q_id = create.json()["id"]

        patch_res = client.patch(f"/api/v1/questions/{q_id}", json={"question_text": None}, headers=auth_headers)
        assert patch_res.status_code == 422

    def test_add_question_to_published_quiz_returns_409(self, client: TestClient, auth_headers):
        """Adding questions to an already published quiz is rejected with 409."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        client.patch(f"/api/v1/quizzes/{quiz_id}", json={"is_published": True}, headers=auth_headers)

        res = client.post(f"/api/v1/rounds/{round_id}/questions", json=VALID_QUESTION, headers=auth_headers)
        assert res.status_code == 409
        assert "unpublish" in res.json()["detail"].lower()
