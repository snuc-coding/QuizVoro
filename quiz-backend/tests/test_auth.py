"""
test_auth.py — Tests for admin authentication endpoints.

Covers:
  - Successful login
  - Invalid password
  - Invalid username
  - Missing fields
  - Protected endpoint without token
  - Protected endpoint with expired/invalid token
  - /admin/me endpoint
"""

import pytest
from fastapi.testclient import TestClient


class TestAdminLogin:
    """Tests for POST /api/v1/admin/login"""

    def test_successful_login_returns_token(self, client: TestClient, test_admin):
        """Valid credentials → 200 with access_token."""
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "testadmin", "password": "testpassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        # Never return the password or hash
        assert "password" not in data
        assert "hashed_password" not in data

    def test_wrong_password_returns_401(self, client: TestClient, test_admin):
        """Wrong password → 401."""
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        # Vague error — doesn't tell attacker if username or password was wrong
        assert "Invalid" in response.json()["detail"]

    def test_nonexistent_username_returns_401(self, client: TestClient):
        """Username that doesn't exist → 401 (not 404, to avoid username enumeration)."""
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "nobody", "password": "password"},
        )
        assert response.status_code == 401

    def test_missing_username_returns_422(self, client: TestClient):
        """Missing required field → 422 Unprocessable Entity."""
        response = client.post(
            "/api/v1/admin/login",
            json={"password": "testpassword123"},
        )
        assert response.status_code == 422

    def test_oversized_password_returns_422(self, client: TestClient):
        """Password longer than 128 chars is rejected to protect Argon2."""
        long_pass = "A" * 150
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "testadmin", "password": long_pass},
        )
        assert response.status_code == 422

    def test_rate_limiting_after_repeated_failures(self, client: TestClient):
        """After 5 failed login attempts from same IP, 6th attempt returns 429."""
        from app.routers.auth import _reset_attempts
        _reset_attempts("testclient")

        for _ in range(5):
            res = client.post(
                "/api/v1/admin/login",
                json={"username": "attacker", "password": "wrongpassword"},
            )
            assert res.status_code == 401

        # 6th attempt should trigger 429 Too Many Requests
        rate_limited_res = client.post(
            "/api/v1/admin/login",
            json={"username": "attacker", "password": "wrongpassword"},
        )
        assert rate_limited_res.status_code == 429
        assert "too many" in rate_limited_res.json()["detail"].lower()

        _reset_attempts("testclient")

    def test_missing_password_returns_422(self, client: TestClient):
        """Missing password → 422."""
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "testadmin"},
        )
        assert response.status_code == 422

    def test_empty_body_returns_422(self, client: TestClient):
        """Empty body → 422."""
        response = client.post("/api/v1/admin/login", json={})
        assert response.status_code == 422

    def test_empty_username_returns_422(self, client: TestClient):
        """Empty string username → 422 (min_length=1)."""
        response = client.post(
            "/api/v1/admin/login",
            json={"username": "", "password": "testpassword123"},
        )
        assert response.status_code == 422


class TestGetMe:
    """Tests for GET /api/v1/admin/me"""

    def test_get_me_with_valid_token(self, client: TestClient, test_admin, auth_headers):
        """Valid token → 200 with admin profile (no password)."""
        response = client.get("/api/v1/admin/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["email"] == "testadmin@example.com"
        assert "hashed_password" not in data
        assert "password" not in data

    def test_get_me_without_token_returns_403(self, client: TestClient):
        """No Authorization header → 403 (HTTPBearer auto_error=True)."""
        response = client.get("/api/v1/admin/me")
        assert response.status_code == 403

    def test_get_me_with_invalid_token_returns_401(self, client: TestClient):
        """Garbage token → 401."""
        response = client.get(
            "/api/v1/admin/me",
            headers={"Authorization": "Bearer this.is.not.a.valid.token"},
        )
        assert response.status_code == 401

    def test_get_me_with_malformed_header_returns_403(self, client: TestClient):
        """Missing 'Bearer' prefix → 403."""
        response = client.get(
            "/api/v1/admin/me",
            headers={"Authorization": "notbearer sometoken"},
        )
        assert response.status_code == 403
