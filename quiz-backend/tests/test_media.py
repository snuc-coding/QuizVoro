"""
test_media.py — Tests for media upload endpoints.

Covers:
  - Valid image upload (JPEG, PNG)
  - Unsupported file type
  - Oversized file
  - Invalid question ID
  - Unauthenticated upload

NOTE: These tests use in-memory file content — no real disk access needed
beyond what the upload handler writes to the test_media/ directory.
"""

import io
import pytest
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_quiz(client, headers):
    r = client.post("/api/v1/quizzes", json={"title": "Quiz"}, headers=headers)
    return r.json()["id"]


def _create_round(client, headers, quiz_id):
    r = client.post(
        f"/api/v1/quizzes/{quiz_id}/rounds",
        json={"title": "Round", "round_number": 1},
        headers=headers,
    )
    return r.json()["id"]


def _create_question(client, headers, round_id):
    r = client.post(
        f"/api/v1/rounds/{round_id}/questions",
        json={
            "question_text": "Media question",
            "question_type": "MCQ",
            "time_limit": 30,
            "points": 1000,
            "question_order": 1,
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": False},
            ],
        },
        headers=headers,
    )
    return r.json()["id"]


# Minimal valid 1×1 PNG (67 bytes) — avoids needing a real image file.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestMediaUpload:
    """Tests for POST /api/v1/questions/{questionId}/media"""

    def test_valid_png_upload(self, client: TestClient, auth_headers):
        """Upload a valid PNG → 201 with media_url."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        response = client.post(
            f"/api/v1/questions/{question_id}/media",
            files={"file": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["question_id"] == question_id
        assert data["media_type"] == "image"
        assert data["media_url"].startswith("/media/")
        assert data["media_url"].endswith(".png")

    def test_unsupported_file_type_returns_400(self, client: TestClient, auth_headers):
        """Upload a .txt file → 400 Unsupported file type."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        response = client.post(
            f"/api/v1/questions/{question_id}/media",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    def test_oversized_file_returns_400(self, client: TestClient, auth_headers):
        """Upload a file larger than MAX_UPLOAD_SIZE_MB → 400."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        # Create a fake 11 MB "PNG" with valid PNG signature
        big_file = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)

        response = client.post(
            f"/api/v1/questions/{question_id}/media",
            files={"file": ("big.png", io.BytesIO(big_file), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "large" in response.json()["detail"].lower()

    def test_invalid_question_id_returns_404(self, client: TestClient, auth_headers):
        """Upload to non-existent question → 404."""
        response = client.post(
            "/api/v1/questions/99999/media",
            files={"file": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_unauthenticated_upload_returns_403(self, client: TestClient):
        """No token → 403."""
        response = client.post(
            "/api/v1/questions/1/media",
            files={"file": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
        )
        assert response.status_code == 403

    def test_serve_media_success(self, client: TestClient, auth_headers):
        """GET /api/v1/questions/{questionId}/media returns the uploaded file."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        # Upload
        up_res = client.post(
            f"/api/v1/questions/{question_id}/media",
            files={"file": ("test.png", io.BytesIO(TINY_PNG), "image/png")},
            headers=auth_headers,
        )
        assert up_res.status_code == 201

        # Serve
        get_res = client.get(f"/api/v1/questions/{question_id}/media")
        assert get_res.status_code == 200
        assert get_res.content == TINY_PNG
        assert "image/png" in get_res.headers["content-type"]

    def test_serve_media_not_found(self, client: TestClient, auth_headers):
        """GET /api/v1/questions/{questionId}/media when no media exists returns 404."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        get_res = client.get(f"/api/v1/questions/{question_id}/media")
        assert get_res.status_code == 404

    def test_invalid_magic_bytes_returns_400(self, client: TestClient, auth_headers):
        """File claiming to be image/png but containing text/plain content is rejected."""
        quiz_id = _create_quiz(client, auth_headers)
        round_id = _create_round(client, auth_headers, quiz_id)
        question_id = _create_question(client, auth_headers, round_id)

        fake_png = b"THIS IS NOT A REAL PNG FILE AT ALL"
        response = client.post(
            f"/api/v1/questions/{question_id}/media",
            files={"file": ("fake.png", io.BytesIO(fake_png), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()
