import os
import sys
import json
import io
import time
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
client = httpx.Client(timeout=10.0)

results = []

def record(endpoint, method, scenario, expected, actual, status, details=None):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "scenario": scenario,
        "expected": expected,
        "actual": actual,
        "status": status,
        "details": details or ""
    })
    print(f"[{status}] {method} {endpoint} - {scenario} (Actual: {actual})")

def run_api_tests():
    print("=== STARTING BACKEND REST API TESTING ON POSTGRESQL ===")

    # 1. AUTHENTICATION
    # Admin login with valid credentials
    r = client.post(f"{BASE_URL}/admin/login", json={"username": "admin", "password": "admin1234"})
    if r.status_code == 200 and "access_token" in r.json():
        token = r.json()["access_token"]
        record("/admin/login", "POST", "Valid admin login", "200 with JWT token", f"{r.status_code}", "PASS")
    else:
        token = None
        record("/admin/login", "POST", "Valid admin login", "200 with JWT token", f"{r.status_code} {r.text}", "FAIL")

    admin_headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Admin login with invalid password
    r = client.post(f"{BASE_URL}/admin/login", json={"username": "admin", "password": "wrongpassword"})
    record("/admin/login", "POST", "Invalid password login", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

    # Admin login with nonexistent username
    r = client.post(f"{BASE_URL}/admin/login", json={"username": "nonexistent_admin_xyz", "password": "any"})
    record("/admin/login", "POST", "Nonexistent user login", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

    # Admin login missing required field
    r = client.post(f"{BASE_URL}/admin/login", json={"username": "admin"})
    record("/admin/login", "POST", "Missing password in login body", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

    # Access protected /admin/me with valid JWT
    r = client.get(f"{BASE_URL}/admin/me", headers=admin_headers)
    record("/admin/me", "GET", "Access protected admin profile with valid JWT", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # Access protected /admin/me without JWT
    r = client.get(f"{BASE_URL}/admin/me")
    record("/admin/me", "GET", "Access protected admin profile without JWT", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

    # Access protected /admin/me with invalid JWT
    r = client.get(f"{BASE_URL}/admin/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    record("/admin/me", "GET", "Access protected admin profile with invalid JWT", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

    # 2. QUIZ MANAGEMENT
    # Create quiz valid
    r = client.post(f"{BASE_URL}/quizzes", headers=admin_headers, json={"title": "QA Test Suite Quiz", "description": "Created by automated QA"})
    if r.status_code == 201:
        quiz_id = r.json()["id"]
        record("/quizzes", "POST", "Create valid quiz", "201 Created", f"{r.status_code}", "PASS")
    else:
        quiz_id = None
        record("/quizzes", "POST", "Create valid quiz", "201 Created", f"{r.status_code} {r.text}", "FAIL")

    # Create quiz missing title
    r = client.post(f"{BASE_URL}/quizzes", headers=admin_headers, json={"description": "Missing title"})
    record("/quizzes", "POST", "Create quiz missing title", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

    # Create quiz empty title
    r = client.post(f"{BASE_URL}/quizzes", headers=admin_headers, json={"title": "   ", "description": "Empty title"})
    record("/quizzes", "POST", "Create quiz with empty whitespace title", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

    # Retrieve all quizzes
    r = client.get(f"{BASE_URL}/quizzes", headers=admin_headers)
    record("/quizzes", "GET", "List admin quizzes", "200 OK with list", f"{r.status_code} (count={len(r.json()) if r.status_code == 200 else 0})", "PASS" if r.status_code == 200 else "FAIL")

    # Retrieve individual quiz
    if quiz_id:
        r = client.get(f"{BASE_URL}/quizzes/{quiz_id}", headers=admin_headers)
        record("/quizzes/{quizId}", "GET", "Get quiz detail", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # Retrieve nonexistent quiz
    r = client.get(f"{BASE_URL}/quizzes/999999", headers=admin_headers)
    record("/quizzes/{quizId}", "GET", "Get nonexistent quiz", "404 Not Found", f"{r.status_code}", "PASS" if r.status_code == 404 else "FAIL")

    # Update quiz
    if quiz_id:
        r = client.patch(f"{BASE_URL}/quizzes/{quiz_id}", headers=admin_headers, json={"title": "QA Test Suite Quiz (Updated)"})
        record("/quizzes/{quizId}", "PATCH", "Update quiz title", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # 3. ROUND MANAGEMENT
    # Add round valid
    if quiz_id:
        r = client.post(f"{BASE_URL}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Round 1 - Core", "round_number": 1})
        if r.status_code == 201:
            round_id = r.json()["id"]
            record("/quizzes/{quizId}/rounds", "POST", "Add round 1", "201 Created", f"{r.status_code}", "PASS")
        else:
            round_id = None
            record("/quizzes/{quizId}/rounds", "POST", "Add round 1", "201 Created", f"{r.status_code} {r.text}", "FAIL")

        # Duplicate round number
        r = client.post(f"{BASE_URL}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Duplicate Round 1", "round_number": 1})
        record("/quizzes/{quizId}/rounds", "POST", "Add duplicate round number in same quiz", "409 Conflict", f"{r.status_code}", "PASS" if r.status_code == 409 else "FAIL")

        # Add round with invalid round number (< 1)
        r = client.post(f"{BASE_URL}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Invalid Round", "round_number": 0})
        record("/quizzes/{quizId}/rounds", "POST", "Add round with round_number < 1", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Add round 2
        r = client.post(f"{BASE_URL}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Round 2 - Advanced", "round_number": 2})
        round2_id = r.json().get("id") if r.status_code == 201 else None
        record("/quizzes/{quizId}/rounds", "POST", "Add round 2", "201 Created", f"{r.status_code}", "PASS" if r.status_code == 201 else "FAIL")

        # Retrieve rounds for quiz
        r = client.get(f"{BASE_URL}/quizzes/{quiz_id}/rounds", headers=admin_headers)
        record("/quizzes/{quizId}/rounds", "GET", "List rounds for quiz", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")
    else:
        round_id = None
        round2_id = None

    # Retrieve individual round
    if round_id:
        r = client.get(f"{BASE_URL}/rounds/{round_id}", headers=admin_headers)
        record("/rounds/{roundId}", "GET", "Get round detail", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # Retrieve nonexistent round
    r = client.get(f"{BASE_URL}/rounds/999999", headers=admin_headers)
    record("/rounds/{roundId}", "GET", "Get nonexistent round", "404 Not Found", f"{r.status_code}", "PASS" if r.status_code == 404 else "FAIL")

    # Edit round
    if round_id:
        r = client.patch(f"{BASE_URL}/rounds/{round_id}", headers=admin_headers, json={"title": "Round 1 - Core (Renamed)"})
        record("/rounds/{roundId}", "PATCH", "Update round title", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # 4. QUESTION MANAGEMENT
    question_payload = {
        "question_text": "What is the official currency of Japan?",
        "question_type": "MCQ",
        "time_limit": 20,
        "points": 1000,
        "question_order": 1,
        "options": [
            {"option_text": "Yen", "is_correct": True},
            {"option_text": "Won", "is_correct": False},
            {"option_text": "Yuan", "is_correct": False},
            {"option_text": "Ringgit", "is_correct": False}
        ]
    }
    if round_id:
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=question_payload)
        if r.status_code == 201:
            q1_id = r.json()["id"]
            record("/rounds/{roundId}/questions", "POST", "Create valid MCQ question", "201 Created", f"{r.status_code}", "PASS")
        else:
            q1_id = None
            record("/rounds/{roundId}/questions", "POST", "Create valid MCQ question", "201 Created", f"{r.status_code} {r.text}", "FAIL")

        # Question with fewer than 2 options
        bad_q1 = {**question_payload, "question_order": 2, "options": [{"option_text": "Only One", "is_correct": True}]}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=bad_q1)
        record("/rounds/{roundId}/questions", "POST", "Question with < 2 options", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Question with more than 6 options
        bad_q2 = {**question_payload, "question_order": 2, "options": [{"option_text": f"Opt {i}", "is_correct": (i==0)} for i in range(7)]}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=bad_q2)
        record("/rounds/{roundId}/questions", "POST", "Question with > 6 options", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Question with zero correct answers
        bad_q3 = {**question_payload, "question_order": 2, "options": [
            {"option_text": "A", "is_correct": False},
            {"option_text": "B", "is_correct": False}
        ]}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=bad_q3)
        record("/rounds/{roundId}/questions", "POST", "Question with 0 correct answers", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Question with multiple correct answers
        bad_q4 = {**question_payload, "question_order": 2, "options": [
            {"option_text": "A", "is_correct": True},
            {"option_text": "B", "is_correct": True}
        ]}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=bad_q4)
        record("/rounds/{roundId}/questions", "POST", "Question with multiple correct answers", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Question with invalid time limit (< 5s)
        bad_q5 = {**question_payload, "question_order": 2, "time_limit": 2}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=bad_q5)
        record("/rounds/{roundId}/questions", "POST", "Question with time_limit < 5", "422 Validation Error", f"{r.status_code}", "PASS" if r.status_code == 422 else "FAIL")

        # Question with duplicate order in round
        dup_order_q = {**question_payload, "question_order": 1}
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=dup_order_q)
        record("/rounds/{roundId}/questions", "POST", "Duplicate question_order in round", "409 Conflict", f"{r.status_code}", "PASS" if r.status_code == 409 else "FAIL")

        # Add question 2
        q2_payload = {
            "question_text": "Which planet is known as the Red Planet?",
            "question_type": "MCQ",
            "time_limit": 15,
            "points": 1000,
            "question_order": 2,
            "options": [
                {"option_text": "Venus", "is_correct": False},
                {"option_text": "Mars", "is_correct": True},
                {"option_text": "Jupiter", "is_correct": False},
                {"option_text": "Saturn", "is_correct": False}
            ]
        }
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=q2_payload)
        q2_id = r.json().get("id") if r.status_code == 201 else None
        record("/rounds/{roundId}/questions", "POST", "Create question 2", "201 Created", f"{r.status_code}", "PASS" if r.status_code == 201 else "FAIL")

        # Add question 3
        q3_payload = {
            "question_text": "What is the chemical symbol for Gold?",
            "question_type": "MCQ",
            "time_limit": 15,
            "points": 1000,
            "question_order": 3,
            "options": [
                {"option_text": "Au", "is_correct": True},
                {"option_text": "Ag", "is_correct": False},
                {"option_text": "Fe", "is_correct": False},
                {"option_text": "Cu", "is_correct": False}
            ]
        }
        r = client.post(f"{BASE_URL}/rounds/{round_id}/questions", headers=admin_headers, json=q3_payload)
        q3_id = r.json().get("id") if r.status_code == 201 else None
        record("/rounds/{roundId}/questions", "POST", "Create question 3", "201 Created", f"{r.status_code}", "PASS" if r.status_code == 201 else "FAIL")
    else:
        q1_id = None
        q2_id = None
        q3_id = None

    # Populate Round 2 questions
    if round2_id:
        for idx, (txt, opts) in enumerate([
            ("What is 12 x 12?", [("144", True), ("124", False), ("148", False), ("164", False)]),
            ("Who painted the Mona Lisa?", [("Leonardo da Vinci", True), ("Michelangelo", False), ("Raphael", False), ("Donatello", False)]),
            ("What is the capital of Australia?", [("Canberra", True), ("Sydney", False), ("Melbourne", False), ("Brisbane", False)])
        ], 1):
            client.post(f"{BASE_URL}/rounds/{round2_id}/questions", headers=admin_headers, json={
                "question_text": txt,
                "question_type": "MCQ",
                "time_limit": 15,
                "points": 1000,
                "question_order": idx,
                "options": [{"option_text": o[0], "is_correct": o[1]} for o in opts]
            })

    # Retrieve question detail
    if q1_id:
        r = client.get(f"{BASE_URL}/questions/{q1_id}", headers=admin_headers)
        record("/questions/{questionId}", "GET", "Get question detail as admin", "200 with options and is_correct", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # Retrieve nonexistent question
    r = client.get(f"{BASE_URL}/questions/999999", headers=admin_headers)
    record("/questions/{questionId}", "GET", "Get nonexistent question", "404 Not Found", f"{r.status_code}", "PASS" if r.status_code == 404 else "FAIL")

    # Edit question
    if q1_id:
        r = client.patch(f"{BASE_URL}/questions/{q1_id}", headers=admin_headers, json={"time_limit": 25})
        record("/questions/{questionId}", "PATCH", "Update question time limit", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    # 5. MEDIA UPLOAD
    if q1_id:
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("test.png", io.BytesIO(valid_png), "image/png")}
        r = client.post(f"{BASE_URL}/questions/{q1_id}/media", headers=admin_headers, files=files)
        record("/questions/{questionId}/media", "POST", "Upload valid PNG image", "201 Created", f"{r.status_code}", "PASS" if r.status_code == 201 else "FAIL")

        if r.status_code == 201:
            media_url = r.json().get("media_url")
            r_get = client.get(f"http://127.0.0.1:8000{media_url}")
            record(f"{media_url}", "GET", "Access stored media file", "200 OK", f"{r_get.status_code}", "PASS" if r_get.status_code == 200 else "FAIL")

        files = {"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho test"), "text/x-shellscript")}
        r = client.post(f"{BASE_URL}/questions/{q1_id}/media", headers=admin_headers, files=files)
        record("/questions/{questionId}/media", "POST", "Upload unsupported file type (shell script)", "400 Bad Request", f"{r.status_code}", "PASS" if r.status_code == 400 else "FAIL")

        files = {"file": ("fake.png", io.BytesIO(b"not-a-real-png-bytes-at-all"), "image/png")}
        r = client.post(f"{BASE_URL}/questions/{q1_id}/media", headers=admin_headers, files=files)
        record("/questions/{questionId}/media", "POST", "Upload spoofed extension with invalid magic bytes", "400 Bad Request", f"{r.status_code}", "PASS" if r.status_code == 400 else "FAIL")

        files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
        r = client.post(f"{BASE_URL}/questions/{q1_id}/media", headers=admin_headers, files=files)
        record("/questions/{questionId}/media", "POST", "Upload empty file", "400 Bad Request", f"{r.status_code}", "PASS" if r.status_code == 400 else "FAIL")

    # 6. PARTICIPANT JOIN & ANSWER SECRECY REST TESTS
    if quiz_id:
        r = client.post(f"{BASE_URL}/games", headers=admin_headers, json={"quiz_id": quiz_id})
        if r.status_code == 201:
            game = r.json()
            game_id = game["id"]
            pin = game["pin"]
            record("/games", "POST", "Create live game session", "201 Created with PIN", f"{r.status_code} PIN={pin}", "PASS")
        else:
            game_id = None
            pin = None
            record("/games", "POST", "Create live game session", "201 Created", f"{r.status_code} {r.text}", "FAIL")
    else:
        game_id = None
        pin = None

    if game_id and pin:
        r = client.post(f"{BASE_URL}/games/join", json={"pin": pin, "nickname": "PlayerAlpha"})
        if r.status_code == 201:
            p1_token = r.json()["token"]
            p1_id = r.json()["participant_id"]
            record("/games/join", "POST", "Join with valid PIN & nickname", "201 Created with token", f"{r.status_code}", "PASS")
        else:
            p1_token = None
            p1_id = None
            record("/games/join", "POST", "Join with valid PIN & nickname", "201 Created", f"{r.status_code} {r.text}", "FAIL")

        r = client.post(f"{BASE_URL}/games/join", json={"pin": pin, "nickname": "PlayerAlpha"})
        record("/games/join", "POST", "Join with duplicate nickname", "409 Conflict", f"{r.status_code}", "PASS" if r.status_code == 409 else "FAIL")

        r = client.post(f"{BASE_URL}/games/join", json={"pin": "00000000", "nickname": "Nobody"})
        record("/games/join", "POST", "Join with invalid PIN", "404 Not Found", f"{r.status_code}", "PASS" if r.status_code == 404 else "FAIL")

        if p1_token:
            r = client.post(f"{BASE_URL}/games/rejoin", json={"pin": pin, "token": p1_token})
            record("/games/rejoin", "POST", "Rejoin game with saved token", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

        r = client.post(f"{BASE_URL}/games/rejoin", json={"pin": pin, "token": "invalid_participant_token_12345"})
        record("/games/rejoin", "POST", "Rejoin game with invalid token", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

        if p1_token:
            r = client.get(f"{BASE_URL}/games/{game_id}/current-question", headers={"X-Participant-Token": p1_token})
            record("/games/{gameId}/current-question", "GET", "Get question before game starts", "409 Conflict (not started)", f"{r.status_code}", "PASS" if r.status_code == 409 else "FAIL")

        r = client.post(f"{BASE_URL}/games/{game_id}/start", headers=admin_headers)
        record("/games/{gameId}/start", "POST", "Host starts game", "200 OK status=active", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

        if p1_token:
            r = client.get(f"{BASE_URL}/games/{game_id}/current-question", headers={"X-Participant-Token": p1_token})
            if r.status_code == 200:
                q_data = r.json()
                options = q_data.get("question", {}).get("options", [])
                has_is_correct = any("is_correct" in opt for opt in options)
                if not has_is_correct:
                    record("/games/{gameId}/current-question", "GET", "Verify is_correct is NEVER exposed to participant", "is_correct omitted from options", "OMITTED (Secure)", "PASS")
                else:
                    record("/games/{gameId}/current-question", "GET", "Verify is_correct is NEVER exposed to participant", "is_correct omitted", "EXPOSED (SECURITY LEAK)", "FAIL")
            else:
                record("/games/{gameId}/current-question", "GET", "Get current question after start", "200 OK", f"{r.status_code} {r.text}", "FAIL")

        if p1_token:
            r = client.post(f"{BASE_URL}/games/{game_id}/answers", headers={"X-Participant-Token": p1_token}, json={"question_id": q1_id, "selected_option": "A"})
            record("/games/{gameId}/answers", "POST", "Submit valid answer letter A", "201 Answer locked in", f"{r.status_code}", "PASS" if r.status_code == 201 else "FAIL")

            r = client.post(f"{BASE_URL}/games/{game_id}/answers", headers={"X-Participant-Token": p1_token}, json={"question_id": q1_id, "selected_option": "B"})
            record("/games/{gameId}/answers", "POST", "Duplicate answer submission on same question", "409 Conflict (already answered)", f"{r.status_code}", "PASS" if r.status_code == 409 else "FAIL")

        if p1_token:
            r = client.post(f"{BASE_URL}/games/{game_id}/pause", headers={"X-Participant-Token": p1_token})
            record("/games/{gameId}/pause", "POST", "Participant attempts admin control", "401 Unauthorized", f"{r.status_code}", "PASS" if r.status_code == 401 else "FAIL")

        r = client.get(f"{BASE_URL}/games/{game_id}/stage-token", headers=admin_headers)
        record("/games/{gameId}/stage-token", "GET", "Host generates stage token", "200 with stage_token", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

        r = client.get(f"{BASE_URL}/games/{game_id}/leaderboard")
        record("/games/{gameId}/leaderboard", "GET", "Public leaderboard retrieval", "200 OK", f"{r.status_code}", "PASS" if r.status_code == 200 else "FAIL")

    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\nAPI Tests Complete: Total {len(results)}, Passed: {passed}, Failed: {failed}")

if __name__ == "__main__":
    run_api_tests()
