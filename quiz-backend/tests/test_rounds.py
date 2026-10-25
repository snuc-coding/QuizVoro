"""
test_rounds.py — Tests for round management endpoints.

Covers:
  - Create round (success, duplicate round number, validation failures)
  - List rounds
  - Get round by ID
  - Update round
  - Delete round
  - Authorization checks
"""

import pytest
from fastapi.testclient import TestClient


def _create_quiz(client, headers):
    """Helper: create a quiz and return its ID."""
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "Test Quiz"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestCreateRound:
    """Tests for POST /api/v1/quizzes/{quizId}/rounds"""

    def test_create_round_success(self, client: TestClient, auth_headers):
        """Create a round → 201 with round data."""
        quiz_id = _create_quiz(client, auth_headers)

        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1, "description": "First round"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Round 1"
        assert data["round_number"] == 1
        assert data["quiz_id"] == quiz_id

    def test_create_round_without_description(self, client: TestClient, auth_headers):
        """Description is optional."""
        quiz_id = _create_quiz(client, auth_headers)
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_duplicate_round_number_returns_409(self, client: TestClient, auth_headers):
        """Same round_number in same quiz → 409 Conflict."""
        quiz_id = _create_quiz(client, auth_headers)

        client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Another Round 1", "round_number": 1},
            headers=auth_headers,
        )
        assert response.status_code == 409

    def test_same_round_number_in_different_quiz_is_ok(self, client: TestClient, auth_headers):
        """round_number=1 in quiz A and quiz B is allowed."""
        quiz_a = _create_quiz(client, auth_headers)
        quiz_b = _create_quiz(client, auth_headers)

        client.post(
            f"/api/v1/quizzes/{quiz_a}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        response = client.post(
            f"/api/v1/quizzes/{quiz_b}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_create_round_invalid_quiz_returns_404(self, client: TestClient, auth_headers):
        """Round in non-existent quiz → 404."""
        response = client.post(
            "/api/v1/quizzes/99999/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_create_round_missing_title_returns_422(self, client: TestClient, auth_headers):
        """Missing required title → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"round_number": 1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_round_invalid_round_number_returns_422(self, client: TestClient, auth_headers):
        """round_number < 1 → 422."""
        quiz_id = _create_quiz(client, auth_headers)
        response = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round", "round_number": 0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_round_unauthenticated_returns_403(self, client: TestClient):
        """No token → 403."""
        response = client.post(
            "/api/v1/quizzes/1/rounds",
            json={"title": "Round 1", "round_number": 1},
        )
        assert response.status_code == 403


class TestGetRound:
    """Tests for GET /api/v1/rounds/{roundId}"""

    def test_get_round_success(self, client: TestClient, auth_headers):
        quiz_id = _create_quiz(client, auth_headers)
        create = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        round_id = create.json()["id"]

        response = client.get(f"/api/v1/rounds/{round_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == round_id

    def test_get_nonexistent_round_returns_404(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/rounds/99999", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateRound:
    """Tests for PATCH /api/v1/rounds/{roundId}"""

    def test_update_round_title(self, client: TestClient, auth_headers):
        quiz_id = _create_quiz(client, auth_headers)
        create = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        round_id = create.json()["id"]

        patch_res = client.patch(
            f"/api/v1/rounds/{round_id}",
            json={"title": "Updated Round Title"},
            headers=auth_headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["title"] == "Updated Round Title"

    def test_update_round_null_title_returns_422(self, client: TestClient, auth_headers):
        quiz_id = _create_quiz(client, auth_headers)
        create = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        round_id = create.json()["id"]

        patch_res = client.patch(
            f"/api/v1/rounds/{round_id}",
            json={"title": None},
            headers=auth_headers,
        )
        assert patch_res.status_code == 422

    def test_update_round_null_number_returns_422(self, client: TestClient, auth_headers):
        quiz_id = _create_quiz(client, auth_headers)
        create = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        round_id = create.json()["id"]

        patch_res = client.patch(
            f"/api/v1/rounds/{round_id}",
            json={"round_number": None},
            headers=auth_headers,
        )
        assert patch_res.status_code == 422


class TestDeleteRound:
    """Tests for DELETE /api/v1/rounds/{roundId}"""

    def test_delete_round_success(self, client: TestClient, auth_headers):
        quiz_id = _create_quiz(client, auth_headers)
        create = client.post(
            f"/api/v1/quizzes/{quiz_id}/rounds",
            json={"title": "Round 1", "round_number": 1},
            headers=auth_headers,
        )
        round_id = create.json()["id"]

        delete_resp = client.delete(f"/api/v1/rounds/{round_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/v1/rounds/{round_id}", headers=auth_headers)
        assert get_resp.status_code == 404
