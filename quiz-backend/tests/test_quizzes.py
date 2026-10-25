"""
test_quizzes.py — Tests for quiz management endpoints.

Covers:
  - Create quiz (success and validation failures)
  - List quizzes
  - Get quiz by ID
  - Update quiz
  - Delete quiz
  - Unauthorized access
  - Invalid quiz ID
"""

import pytest
from fastapi.testclient import TestClient


class TestCreateQuiz:
    """Tests for POST /api/v1/quizzes"""

    def test_create_quiz_success(self, client: TestClient, auth_headers):
        """Valid quiz → 201 with quiz data."""
        response = client.post(
            "/api/v1/quizzes",
            json={"title": "Python Basics", "description": "A quiz about Python fundamentals"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Python Basics"
        assert data["description"] == "A quiz about Python fundamentals"
        assert data["is_published"] is False
        assert "id" in data
        assert "admin_id" in data

    def test_create_quiz_without_description(self, client: TestClient, auth_headers):
        """Description is optional."""
        response = client.post(
            "/api/v1/quizzes",
            json={"title": "Quick Quiz"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Quick Quiz"
        assert data["description"] is None

    def test_create_quiz_empty_title_returns_422(self, client: TestClient, auth_headers):
        """Empty title → 422."""
        response = client.post(
            "/api/v1/quizzes",
            json={"title": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_quiz_missing_title_returns_422(self, client: TestClient, auth_headers):
        """Missing title → 422."""
        response = client.post(
            "/api/v1/quizzes",
            json={"description": "no title"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_quiz_unauthenticated_returns_403(self, client: TestClient):
        """No token → 403."""
        response = client.post(
            "/api/v1/quizzes",
            json={"title": "Sneaky Quiz"},
        )
        assert response.status_code == 403


class TestListQuizzes:
    """Tests for GET /api/v1/quizzes"""

    def test_list_quizzes_empty(self, client: TestClient, auth_headers):
        """New admin with no quizzes → empty list."""
        response = client.get("/api/v1/quizzes", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_quizzes_returns_only_own_quizzes(self, client: TestClient, auth_headers):
        """Admin only sees their own quizzes."""
        # Create two quizzes
        client.post("/api/v1/quizzes", json={"title": "Quiz A"}, headers=auth_headers)
        client.post("/api/v1/quizzes", json={"title": "Quiz B"}, headers=auth_headers)

        response = client.get("/api/v1/quizzes", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetQuiz:
    """Tests for GET /api/v1/quizzes/{quizId}"""

    def test_get_quiz_success(self, client: TestClient, auth_headers):
        """Get a quiz by ID."""
        create = client.post(
            "/api/v1/quizzes",
            json={"title": "Detail Quiz"},
            headers=auth_headers,
        )
        quiz_id = create.json()["id"]

        response = client.get(f"/api/v1/quizzes/{quiz_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == quiz_id

    def test_get_nonexistent_quiz_returns_404(self, client: TestClient, auth_headers):
        """Non-existent quiz ID → 404."""
        response = client.get("/api/v1/quizzes/99999", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateQuiz:
    """Tests for PATCH /api/v1/quizzes/{quizId}"""

    def test_update_quiz_title(self, client: TestClient, auth_headers):
        """Update the title."""
        create = client.post(
            "/api/v1/quizzes",
            json={"title": "Old Title"},
            headers=auth_headers,
        )
        quiz_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/quizzes/{quiz_id}",
            json={"title": "New Title"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_update_quiz_publish(self, client: TestClient, auth_headers):
        """Publish a quiz."""
        create = client.post(
            "/api/v1/quizzes",
            json={"title": "Draft"},
            headers=auth_headers,
        )
        quiz_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/quizzes/{quiz_id}",
            json={"is_published": True},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_published"] is True

    def test_update_quiz_null_title_returns_422(self, client: TestClient, auth_headers):
        """Updating title with null must return 422, not 500."""
        create = client.post("/api/v1/quizzes", json={"title": "Original"}, headers=auth_headers)
        quiz_id = create.json()["id"]

        response = client.patch(f"/api/v1/quizzes/{quiz_id}", json={"title": None}, headers=auth_headers)
        assert response.status_code == 422

    def test_update_quiz_whitespace_title_returns_422(self, client: TestClient, auth_headers):
        """Updating title with only whitespace must return 422."""
        create = client.post("/api/v1/quizzes", json={"title": "Original"}, headers=auth_headers)
        quiz_id = create.json()["id"]

        response = client.patch(f"/api/v1/quizzes/{quiz_id}", json={"title": "   "}, headers=auth_headers)
        assert response.status_code == 422

    def test_update_published_quiz_returns_409(self, client: TestClient, auth_headers):
        """Editing content of a published quiz is rejected with 409."""
        create = client.post("/api/v1/quizzes", json={"title": "Published Quiz"}, headers=auth_headers)
        quiz_id = create.json()["id"]
        client.patch(f"/api/v1/quizzes/{quiz_id}", json={"is_published": True}, headers=auth_headers)

        # Attempt to change title while published
        res = client.patch(f"/api/v1/quizzes/{quiz_id}", json={"title": "New Title"}, headers=auth_headers)
        assert res.status_code == 409
        assert "unpublish" in res.json()["detail"].lower()


class TestDeleteQuiz:
    """Tests for DELETE /api/v1/quizzes/{quizId}"""

    def test_delete_quiz_success(self, client: TestClient, auth_headers):
        """Delete a quiz → 204, then 404 on subsequent GET."""
        create = client.post(
            "/api/v1/quizzes",
            json={"title": "To Delete"},
            headers=auth_headers,
        )
        quiz_id = create.json()["id"]

        delete_resp = client.delete(f"/api/v1/quizzes/{quiz_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/v1/quizzes/{quiz_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_nonexistent_quiz_returns_404(self, client: TestClient, auth_headers):
        """Delete non-existent quiz → 404."""
        response = client.delete("/api/v1/quizzes/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_quiz_with_games_returns_409(self, client: TestClient, auth_headers, db):
        """Deleting a quiz referenced by a Game violates RESTRICT and returns 409."""
        from app.models import Game
        create = client.post("/api/v1/quizzes", json={"title": "Game Quiz"}, headers=auth_headers)
        quiz_id = create.json()["id"]

        # Insert a game referencing this quiz
        game = Game(quiz_id=quiz_id, pin="123456", status="lobby")
        db.add(game)
        db.commit()

        # Attempt delete
        response = client.delete(f"/api/v1/quizzes/{quiz_id}", headers=auth_headers)
        assert response.status_code == 409
        assert "associated" in response.json()["detail"].lower()
