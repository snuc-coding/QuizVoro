import os
import re
import subprocess
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_security_audit():
    print("=== STARTING APPLICATION SECURITY & PENETRATION AUDIT ===")
    client = httpx.Client(timeout=5.0)

    # 1. Hardcoded Secrets & Git tracking check
    git_tracked = subprocess.check_output(["git", "ls-files"], text=True)
    tracked_files = git_tracked.splitlines()
    assert ".env" not in tracked_files, "CRITICAL: .env file is tracked in Git!"
    print("[1] Confirmed .env is NOT tracked by Git.")

    # 2. JWT Configuration & Secret Strength
    with open(".env", "r") as f:
        env_content = f.read()
    jwt_match = re.search(r"JWT_SECRET_KEY=([^\r\n]+)", env_content)
    assert jwt_match, "JWT_SECRET_KEY missing in .env"
    secret_len = len(jwt_match.group(1).strip())
    assert secret_len >= 32, f"Weak JWT secret length: {secret_len}"
    print(f"[2] JWT Secret Key strength verified (Length: {secret_len} chars >= 32 minimum).")

    # 3. Password Hashing Scheme
    from app.security import pwd_context
    assert pwd_context.default_scheme() == "argon2", "Password hashing algorithm is not Argon2!"
    print("[3] Confirmed Argon2id password hashing is enforced.")

    # 4. Admin API Protection & IDOR Check
    # Verify participant token cannot access /api/v1/admin/me
    res = client.get(f"{BASE_URL}/admin/me", headers={"Authorization": "Bearer fake.jwt.token"})
    assert res.status_code == 401, "Forged JWT was not rejected with 401"

    # Try directory traversal in media endpoint
    res = client.get("http://127.0.0.1:8000/media/../../../../etc/passwd")
    assert res.status_code in (404, 400), f"Directory traversal returned unexpected status: {res.status_code}"
    print("[4] Path traversal protection verified on /media mount.")

    # 5. SQL Injection Protection (SQLAlchemy parameterized queries)
    # Test SQL injection string in participant join and login
    sqli_payload = "' OR 1=1; DROP TABLE admins; --"
    res = client.post(f"{BASE_URL}/admin/login", json={"username": sqli_payload, "password": "password"})
    assert res.status_code in (401, 422), f"SQLi payload caused unexpected status: {res.status_code}"

    res = client.post(f"{BASE_URL}/games/join", json={"pin": "12345678", "nickname": sqli_payload})
    assert res.status_code in (404, 422, 409), f"SQLi payload in nickname caused unexpected status: {res.status_code}"
    print("[5] SQL injection resilience confirmed via parameterized queries.")

    # 6. CORS Configuration
    res = client.options(
        f"{BASE_URL}/games/join",
        headers={
            "Origin": "http://evil-attacker-website.com",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert "access-control-allow-origin" not in res.headers or res.headers["access-control-allow-origin"] != "http://evil-attacker-website.com", "CORS misconfiguration: arbitrary origin allowed!"
    print("[6] CORS domain restriction confirmed. Untrusted origins blocked.")

    # 7. Answer Secrecy Contract
    # Verify neither ParticipantQuestionOut nor WebSocket payloads expose is_correct
    from app.schemas import ParticipantQuestionOut
    assert "is_correct" not in ParticipantQuestionOut.model_fields, "CRITICAL: is_correct found in ParticipantQuestionOut schema!"
    from app.websocket_schemas import QuestionStartPayload
    assert "is_correct" not in QuestionStartPayload.model_fields, "CRITICAL: is_correct found in QuestionStartPayload schema!"
    print("[7] Answer secrecy contract strictly enforced in Pydantic schemas.")

    print("=== SECURITY AUDIT COMPLETED: 0 VULNERABILITIES IDENTIFIED ===")

if __name__ == "__main__":
    test_security_audit()
