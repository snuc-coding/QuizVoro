import asyncio
import json
import websockets
import httpx

BASE_HTTP = "http://127.0.0.1:8000/api/v1"
BASE_WS = "ws://127.0.0.1:8000/api/v1/ws/games"

async def test_game_flow_and_websockets():
    print("=== STARTING COMPLETE GAME-FLOW & WEBSOCKET TESTING ===")
    client = httpx.AsyncClient(timeout=10.0)

    # 1. Admin login
    res = await client.post(f"{BASE_HTTP}/admin/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200, "Admin login failed"
    admin_token = res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[1] Admin authenticated.")

    # 2. Create Quiz with 2 rounds and 3 questions each
    q_res = await client.post(f"{BASE_HTTP}/quizzes", headers=admin_headers, json={
        "title": "E2E Multiplayer Live Quiz",
        "description": "Comprehensive Game-Flow Verification"
    })
    quiz_id = q_res.json()["id"]

    # Round 1
    r1 = await client.post(f"{BASE_HTTP}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Speed Round", "round_number": 1})
    r1_id = r1.json()["id"]

    # Add 3 questions in Round 1
    await client.post(f"{BASE_HTTP}/rounds/{r1_id}/questions", headers=admin_headers, json={
        "question_text": "Round 1 Question 1: What is 2 + 2?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 1,
        "options": [
            {"option_text": "4", "is_correct": True},
            {"option_text": "3", "is_correct": False},
            {"option_text": "5", "is_correct": False},
            {"option_text": "22", "is_correct": False}
        ]
    })
    await client.post(f"{BASE_HTTP}/rounds/{r1_id}/questions", headers=admin_headers, json={
        "question_text": "Round 1 Question 2: What color is the sky on a clear day?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 2,
        "options": [
            {"option_text": "Green", "is_correct": False},
            {"option_text": "Blue", "is_correct": True},
            {"option_text": "Red", "is_correct": False},
            {"option_text": "Yellow", "is_correct": False}
        ]
    })
    await client.post(f"{BASE_HTTP}/rounds/{r1_id}/questions", headers=admin_headers, json={
        "question_text": "Round 1 Question 3: How many continents are there?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 3,
        "options": [
            {"option_text": "5", "is_correct": False},
            {"option_text": "6", "is_correct": False},
            {"option_text": "7", "is_correct": True},
            {"option_text": "8", "is_correct": False}
        ]
    })

    # Round 2
    r2 = await client.post(f"{BASE_HTTP}/quizzes/{quiz_id}/rounds", headers=admin_headers, json={"title": "Final Round", "round_number": 2})
    r2_id = r2.json()["id"]

    # Add 3 questions in Round 2
    await client.post(f"{BASE_HTTP}/rounds/{r2_id}/questions", headers=admin_headers, json={
        "question_text": "Round 2 Question 1: What is H2O?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 1,
        "options": [
            {"option_text": "Water", "is_correct": True},
            {"option_text": "Oxygen", "is_correct": False},
            {"option_text": "Hydrogen", "is_correct": False},
            {"option_text": "Salt", "is_correct": False}
        ]
    })
    await client.post(f"{BASE_HTTP}/rounds/{r2_id}/questions", headers=admin_headers, json={
        "question_text": "Round 2 Question 2: Capital of France?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 2,
        "options": [
            {"option_text": "Berlin", "is_correct": False},
            {"option_text": "Madrid", "is_correct": False},
            {"option_text": "Paris", "is_correct": True},
            {"option_text": "Rome", "is_correct": False}
        ]
    })
    await client.post(f"{BASE_HTTP}/rounds/{r2_id}/questions", headers=admin_headers, json={
        "question_text": "Round 2 Question 3: Which is the fastest land animal?",
        "question_type": "MCQ", "time_limit": 10, "points": 1000, "question_order": 3,
        "options": [
            {"option_text": "Lion", "is_correct": False},
            {"option_text": "Cheetah", "is_correct": True},
            {"option_text": "Horse", "is_correct": False},
            {"option_text": "Falcon", "is_correct": False}
        ]
    })
    print(f"[2] Quiz created (ID: {quiz_id}) with 2 rounds and 6 total questions.")

    # 3. Create Live Game
    game_res = await client.post(f"{BASE_HTTP}/games", headers=admin_headers, json={"quiz_id": quiz_id})
    game_id = game_res.json()["id"]
    pin = game_res.json()["pin"]
    print(f"[3] Live Game created. Game ID: {game_id}, PIN: {pin}")

    # Stage Token
    stage_res = await client.get(f"{BASE_HTTP}/games/{game_id}/stage-token", headers=admin_headers)
    stage_token = stage_res.json()["stage_token"]

    # 4. Connect Host WebSocket
    host_ws = await websockets.connect(f"{BASE_WS}/{game_id}/host?token={admin_token}")
    print("[4] Host WebSocket connected.")

    # 5. Connect Stage WebSocket
    stage_ws = await websockets.connect(f"{BASE_WS}/{game_id}/stage?token={stage_token}")
    print("[5] Stage Display WebSocket connected.")

    # 6. Join 4 Concurrent Participants
    players = ["Alice", "Bob", "Charlie", "Diana"]
    participant_sessions = []
    participant_sockets = []

    for p_name in players:
        join_res = await client.post(f"{BASE_HTTP}/games/join", json={"pin": pin, "nickname": p_name})
        assert join_res.status_code == 201, f"Failed to join {p_name}"
        data = join_res.json()
        participant_sessions.append(data)

        # Connect participant WebSocket
        p_ws = await websockets.connect(f"{BASE_WS}/{game_id}/participant?token={data['token']}")
        participant_sockets.append(p_ws)
        print(f"    - Participant {p_name} joined and connected WS.")

    # Verify Host and Stage received PLAYER_JOINED broadcasts
    for _ in range(len(players)):
        host_msg = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
        assert host_msg["event"] == "PLAYER_JOINED", f"Expected PLAYER_JOINED, got {host_msg['event']}"
        stage_join_msg = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
        assert stage_join_msg["event"] == "PLAYER_JOINED", f"Expected PLAYER_JOINED on stage, got {stage_join_msg['event']}"
    print("[6] All 4 participants connected & verified in lobby via WebSocket across Host and Stage.")

    # Test WebSocket PING/PONG
    await host_ws.send(json.dumps({"event": "PING"}))
    pong = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
    assert pong["event"] == "PONG", "Host PING failed"

    await participant_sockets[0].send(json.dumps({"event": "PING"}))
    p_pong = json.loads(await asyncio.wait_for(participant_sockets[0].recv(), timeout=5.0))
    assert p_pong["event"] == "PONG", "Participant PING failed"
    print("[7] WebSocket Heartbeat PING/PONG verified.")

    # 7. Start Game via Host WebSocket Command
    await host_ws.send(json.dumps({"action": "START"}))
    print("[8] Host sent START command.")

    # All participants and stage should receive QUESTION_STARTED
    # Alice answers A, Bob answers B, Charlie answers A, Diana answers C
    answer_choices = ["A", "B", "A", "C"]

    for q_idx in range(6):
        print(f"\n--- Running Question {q_idx + 1} / 6 ---")

        # Collect QUESTION_STARTED on all participant sockets
        q_info = None
        for i, p_ws in enumerate(participant_sockets):
            msg = json.loads(await asyncio.wait_for(p_ws.recv(), timeout=5.0))
            assert msg["event"] == "QUESTION_STARTED", f"Expected QUESTION_STARTED on player {i}, got {msg}"
            q_info = msg["data"]["question"]
            # STRICT SECURITY CHECK: verify is_correct is NOT in options
            for opt in q_info["options"]:
                assert "is_correct" not in opt, "SECURITY VIOLATION: is_correct found in participant question payload!"

        # Stage also receives QUESTION_STARTED
        stage_msg = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
        assert stage_msg["event"] == "QUESTION_STARTED"

        # Host receives QUESTION_STARTED
        host_q_msg = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
        assert host_q_msg["event"] == "QUESTION_STARTED"
        print(f"    Verified QUESTION_STARTED broadcast for: '{q_info['question_text']}' (Options: {len(q_info['options'])}, is_correct: STRICTLY HIDDEN)")

        # Simultaneous answer submissions from all 4 players via WebSocket
        q_id = q_info["id"]
        send_tasks = []
        for i, p_ws in enumerate(participant_sockets):
            choice = answer_choices[i]
            send_tasks.append(p_ws.send(json.dumps({
                "event": "SUBMIT_ANSWER",
                "data": {"question_id": q_id, "selected_option": choice}
            })))
        await asyncio.gather(*send_tasks)

        # Each participant receives ANSWER_ACK
        for i, p_ws in enumerate(participant_sockets):
            ack = json.loads(await asyncio.wait_for(p_ws.recv(), timeout=5.0))
            assert ack["event"] == "ANSWER_ACK", f"Player {i} expected ANSWER_ACK, got {ack}"

        # Host receives 4 ANSWER_COUNT_UPDATED events, and Stage also receives 4 ANSWER_COUNT_UPDATED events
        for _ in range(4):
            count_msg = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
            assert count_msg["event"] == "ANSWER_COUNT_UPDATED"
            stage_count_msg = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
            assert stage_count_msg["event"] == "ANSWER_COUNT_UPDATED"
        print("    All 4 simultaneous answers accepted and acknowledged across Host and Stage.")

        # Test duplicate submission rejected
        await participant_sockets[0].send(json.dumps({
            "event": "SUBMIT_ANSWER",
            "data": {"question_id": q_id, "selected_option": "B"}
        }))
        dup_err = json.loads(await asyncio.wait_for(participant_sockets[0].recv(), timeout=5.0))
        assert dup_err["event"] == "ERROR", "Duplicate answer submission was not rejected with ERROR!"
        print("    Duplicate submission correctly rejected with ERROR.")

        # Host reveals answers
        await host_ws.send(json.dumps({"action": "REVEAL"}))

        # Participants receive ANSWER_REVEALED (with my_stats inside) and then LEADERBOARD_UPDATED
        for p_ws in participant_sockets:
            rev_msg = json.loads(await asyncio.wait_for(p_ws.recv(), timeout=5.0))
            assert rev_msg["event"] == "ANSWER_REVEALED", f"Expected ANSWER_REVEALED, got {rev_msg['event']}"
            assert "my_stats" in rev_msg["data"], "Expected personalized my_stats inside ANSWER_REVEALED data"
            lb_msg = json.loads(await asyncio.wait_for(p_ws.recv(), timeout=5.0))
            assert lb_msg["event"] == "LEADERBOARD_UPDATED", f"Expected LEADERBOARD_UPDATED, got {lb_msg['event']}"

        # Host receives ANSWER_REVEALED and LEADERBOARD_UPDATED
        host_rev = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
        assert host_rev["event"] == "ANSWER_REVEALED"
        host_lb = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
        assert host_lb["event"] == "LEADERBOARD_UPDATED"

        # Stage receives ANSWER_REVEALED and LEADERBOARD_UPDATED
        stage_rev = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
        assert stage_rev["event"] == "ANSWER_REVEALED"
        stage_lb = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
        assert stage_lb["event"] == "LEADERBOARD_UPDATED"
        print(f"    Scoring and Leaderboard reveal verified across Host, Stage, and Participants.")

        # Move to next question if not last
        if q_idx < 5:
            await host_ws.send(json.dumps({"action": "NEXT_QUESTION"}))

    # After question 6 reveal, host sends NEXT_QUESTION -> ends game or END command
    await host_ws.send(json.dumps({"action": "NEXT_QUESTION"}))

    # Verify GAME_FINISHED received by Host, Stage, and Participants
    fin_host = json.loads(await asyncio.wait_for(host_ws.recv(), timeout=5.0))
    assert fin_host["event"] == "GAME_FINISHED", f"Expected GAME_FINISHED on host, got {fin_host}"

    fin_stage = json.loads(await asyncio.wait_for(stage_ws.recv(), timeout=5.0))
    assert fin_stage["event"] == "GAME_FINISHED"

    for p_ws in participant_sockets:
        fin_p = json.loads(await asyncio.wait_for(p_ws.recv(), timeout=5.0))
        assert fin_p["event"] == "GAME_FINISHED"
    print("\n[9] GAME_FINISHED broadcast confirmed across all clients.")

    # 8. Edge Case: Participant attempting to join finished game
    late_join = await client.post(f"{BASE_HTTP}/games/join", json={"pin": pin, "nickname": "LatePlayer"})
    assert late_join.status_code == 409, f"Joining finished game should return 409, got {late_join.status_code}"
    print("[10] Joining finished game properly rejected with 409 Conflict.")

    # Close sockets
    await host_ws.close()
    await stage_ws.close()
    for ws in participant_sockets:
        await ws.close()
    await client.aclose()
    print("=== MULTIPLAYER GAME FLOW & WEBSOCKET AUDIT PASSED 100% ===")

if __name__ == "__main__":
    asyncio.run(test_game_flow_and_websockets())
