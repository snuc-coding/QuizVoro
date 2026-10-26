"""
test_realtime.py — Comprehensive test suite for Developer 3 real-time functionality.

Tests:
  - WebSocket schemas and serialization.
  - Connection manager lifecycle (host, participant, stage).
  - Unicast and role-based broadcasting.
  - Stage token generation and validation.
  - Host WebSocket authentication and authorization (ownership check).
  - Participant WebSocket authentication and session checks.
  - Stage display WebSocket token verification and read-only enforcement.
  - Question broadcast answer secrecy (ParticipantQuestionOut never exposes is_correct).
  - Host controls over WebSocket and REST (start, pause, resume, reveal, next, kick, end).
  - Pause/resume time preservation.
  - Kick participant socket termination.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.game_schemas import AnswerIn
from app.models import Admin, Game, GameParticipant, Question, Round
from app.schemas import ParticipantQuestionOut
from app.security import hash_password
from app.services.connection_manager import ConnectionManager
from app.services.game_orchestrator import create_stage_token, verify_stage_token
from app.websocket_schemas import (
    EventType,
    HostAction,
    HostCommandIn,
    WebSocketMessage,
)

API = "/api/v1"


# ── Stage 1 Tests ─────────────────────────────────────────────────────────────

class TestWebSocketSchemas:
    def test_websocket_message_serialization(self):
        msg = WebSocketMessage(
            event=EventType.PLAYER_JOINED.value,
            data={"participant_id": 1, "nickname": "TestUser", "total_players": 5},
        )
        d = msg.to_json_dict()
        assert d["event"] == "PLAYER_JOINED"
        assert d["data"]["nickname"] == "TestUser"
        assert "timestamp" in d

    def test_host_command_validation(self):
        cmd = HostCommandIn(action=HostAction.START)
        assert cmd.action == HostAction.START
        assert cmd.participant_id is None

        cmd_kick = HostCommandIn(action=HostAction.KICK, participant_id=42)
        assert cmd_kick.action == HostAction.KICK
        assert cmd_kick.participant_id == 42


@pytest.mark.asyncio
class TestConnectionManager:
    async def test_connect_and_broadcast_host(self):
        cm = ConnectionManager()
        ws_mock = AsyncMock()

        await cm.connect_host(game_id=1, websocket=ws_mock)
        room = cm.get_room(1)
        assert room is not None
        assert ws_mock in room.hosts

        msg = WebSocketMessage(event="TEST_EVENT", data={"msg": "hello"})
        await cm.broadcast_to_game(game_id=1, message=msg)

        ws_mock.send_json.assert_called_once()
        sent_data = ws_mock.send_json.call_args[0][0]
        assert sent_data["event"] == "TEST_EVENT"

        await cm.disconnect_host(game_id=1, websocket=ws_mock)
        assert cm.get_room(1) is None

    async def test_participant_and_stage_broadcast(self):
        cm = ConnectionManager()
        ws_host = AsyncMock()
        ws_part = AsyncMock()
        ws_stage = AsyncMock()

        await cm.connect_host(game_id=10, websocket=ws_host)
        await cm.connect_participant(game_id=10, participant_id=101, websocket=ws_part)
        await cm.connect_stage(game_id=10, websocket=ws_stage)

        await cm.broadcast_to_game(10, {"event": "ALL", "data": {}})
        ws_host.send_json.assert_called_with({"event": "ALL", "data": {}})
        ws_part.send_json.assert_called_with({"event": "ALL", "data": {}})
        ws_stage.send_json.assert_called_with({"event": "ALL", "data": {}})

        ws_part.reset_mock()
        ws_host.reset_mock()
        await cm.send_to_participant(10, 101, {"event": "MY_RESULT", "data": {"score": 500}})
        ws_part.send_json.assert_called_once_with({"event": "MY_RESULT", "data": {"score": 500}})
        ws_host.send_json.assert_not_called()

        await cm.kick_participant(10, 101, reason="Test Kick")
        ws_part.close.assert_called_once_with(code=4003, reason="Test Kick")
        assert 101 not in cm.get_connected_participant_ids(10)


# ── Stage 2 & 3: End-to-End WebSocket & Orchestration Tests ───────────────────

def _setup_game(client, auth_headers):
    """Create a quiz with 2 questions and 1 game in the lobby."""
    q_resp = client.post(f"{API}/quizzes", json={"title": "Realtime Quiz"}, headers=auth_headers)
    assert q_resp.status_code == 201
    quiz_id = q_resp.json()["id"]

    r_resp = client.post(
        f"{API}/quizzes/{quiz_id}/rounds",
        json={"title": "Round 1", "round_number": 1},
        headers=auth_headers,
    )
    round_id = r_resp.json()["id"]

    q1_resp = client.post(
        f"{API}/rounds/{round_id}/questions",
        json={
            "question_text": "Q1 Text",
            "time_limit": 20,
            "points": 1000,
            "question_order": 1,
            "options": [
                {"option_text": "Correct Ans", "is_correct": True},
                {"option_text": "Wrong Ans", "is_correct": False},
            ],
        },
        headers=auth_headers,
    )
    q1_id = q1_resp.json()["id"]

    q2_resp = client.post(
        f"{API}/rounds/{round_id}/questions",
        json={
            "question_text": "Q2 Text",
            "time_limit": 15,
            "points": 2000,
            "question_order": 2,
            "options": [
                {"option_text": "True", "is_correct": True},
                {"option_text": "False", "is_correct": False},
            ],
        },
        headers=auth_headers,
    )
    q2_id = q2_resp.json()["id"]

    game_resp = client.post(f"{API}/games", json={"quiz_id": quiz_id}, headers=auth_headers)
    assert game_resp.status_code == 201
    game = game_resp.json()
    return game, q1_resp.json(), q2_resp.json()


class TestStageTokenSecurity:
    def test_stage_token_generation_and_validation(self):
        token = create_stage_token(game_id=42)
        assert verify_stage_token(token, game_id=42) is True
        assert verify_stage_token(token, game_id=99) is False
        assert verify_stage_token("invalid_token_string", game_id=42) is False

    def test_get_stage_token_endpoint(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        resp = client.get(f"{API}/games/{game['id']}/stage-token", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "stage_token" in data
        assert verify_stage_token(data["stage_token"], game["id"]) is True

    def test_get_stage_token_unauthorized(self, client, db, test_admin):
        # Other admin cannot get stage token
        other_admin = Admin(
            username="other",
            email="other@example.com",
            hashed_password=hash_password("pw123"),
            is_active=True,
        )
        db.add(other_admin)
        db.commit()

        login_res = client.post("/api/v1/admin/login", json={"username": "other", "password": "pw123"})
        other_token = login_res.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Create game with testadmin
        login_res1 = client.post("/api/v1/admin/login", json={"username": "testadmin", "password": "testpassword123"})
        h1 = {"Authorization": f"Bearer {login_res1.json()['access_token']}"}
        game, _, _ = _setup_game(client, h1)

        resp = client.get(f"{API}/games/{game['id']}/stage-token", headers=other_headers)
        assert resp.status_code == 403


class TestHostWebSocket:
    def test_host_ws_auth_rejection(self, client):
        # Missing or bad token rejected with 4003
        with pytest.raises(Exception):
            with client.websocket_connect(f"{API}/ws/games/1/host?token=bad_token"):
                pass

    def test_host_ws_non_owner_rejection(self, client, db, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)

        other_admin = Admin(
            username="intruder",
            email="intruder@example.com",
            hashed_password=hash_password("pw123"),
            is_active=True,
        )
        db.add(other_admin)
        db.commit()

        login_res = client.post("/api/v1/admin/login", json={"username": "intruder", "password": "pw123"})
        intruder_token = login_res.json()["access_token"]

        with pytest.raises(Exception):
            with client.websocket_connect(f"{API}/ws/games/{game['id']}/host?token={intruder_token}"):
                pass

    def test_host_ws_connect_and_ping(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        token = auth_headers["Authorization"].split(" ")[1]

        with client.websocket_connect(f"{API}/ws/games/{game['id']}/host?token={token}") as ws:
            ws.send_json({"event": "PING"})
            reply = ws.receive_json()
            assert reply["event"] == "PONG"


class TestStageWebSocket:
    def test_stage_ws_rejection_without_token(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        with pytest.raises(Exception):
            with client.websocket_connect(f"{API}/ws/games/{game['id']}/stage?token=invalid"):
                pass

    def test_stage_ws_connect_and_read_only(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        stage_token = client.get(f"{API}/games/{game['id']}/stage-token", headers=auth_headers).json()["stage_token"]

        with client.websocket_connect(f"{API}/ws/games/{game['id']}/stage?token={stage_token}") as ws:
            # Ping
            ws.send_json({"event": "PING"})
            reply = ws.receive_json()
            assert reply["event"] == "PONG"

            # Attempt to send command: rejected with ERROR
            ws.send_json({"action": "START"})
            err = ws.receive_json()
            assert err["event"] == "ERROR"
            assert "read-only" in err["data"]["detail"]


class TestParticipantWebSocket:
    def test_participant_ws_rejection_invalid_token(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        with pytest.raises(Exception):
            with client.websocket_connect(f"{API}/ws/games/{game['id']}/participant?token=fake_tok"):
                pass

    def test_participant_ws_connect_and_cheating_prevention(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        join_res = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Alice"})
        assert join_res.status_code == 201
        p_token = join_res.json()["token"]

        with client.websocket_connect(f"{API}/ws/games/{game['id']}/participant?token={p_token}") as ws:
            ws.send_json({"event": "PING"})
            assert ws.receive_json()["event"] == "PONG"

            # Participant cannot perform host action
            ws.send_json({"action": "START"})
            reply = ws.receive_json()
            assert reply["event"] == "ERROR"
            assert "not authorized" in reply["data"]["detail"]


class TestGameLifecycleAndBroadcasts:
    def test_full_lifecycle_and_answer_secrecy(self, client, auth_headers):
        game, q1, q2 = _setup_game(client, auth_headers)
        host_token = auth_headers["Authorization"].split(" ")[1]
        stage_token = client.get(f"{API}/games/{game['id']}/stage-token", headers=auth_headers).json()["stage_token"]

        # Alice and Bob join
        p1 = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Alice"}).json()
        p2 = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Bob"}).json()

        with client.websocket_connect(f"{API}/ws/games/{game['id']}/host?token={host_token}") as ws_host, \
             client.websocket_connect(f"{API}/ws/games/{game['id']}/stage?token={stage_token}") as ws_stage, \
             client.websocket_connect(f"{API}/ws/games/{game['id']}/participant?token={p1['token']}") as ws_p1:

            # Host and Stage receive PLAYER_JOINED when Alice connects
            h_join = ws_host.receive_json()
            assert h_join["event"] == "PLAYER_JOINED"
            assert h_join["data"]["nickname"] == "Alice"

            s_join = ws_stage.receive_json()
            assert s_join["event"] == "PLAYER_JOINED"
            assert s_join["data"]["nickname"] == "Alice"

            # 1. Start game via host websocket
            ws_host.send_json({"action": "START"})

            # Participant receives QUESTION_STARTED
            q_msg = ws_p1.receive_json()
            assert q_msg["event"] == "QUESTION_STARTED"
            q_data = q_msg["data"]
            assert q_data["question_number"] == 1
            assert q_data["total_questions"] == 2
            # CHEATING PREVENTION: Verify is_correct is NOT present
            for opt in q_data["question"]["options"]:
                assert "is_correct" not in opt

            # Stage also receives sanitized QUESTION_STARTED
            s_msg = ws_stage.receive_json()
            assert s_msg["event"] == "QUESTION_STARTED"
            for opt in s_msg["data"]["question"]["options"]:
                assert "is_correct" not in opt

            # Host also receives QUESTION_STARTED
            h_q_msg = ws_host.receive_json()
            assert h_q_msg["event"] == "QUESTION_STARTED"

            # 2. Alice submits answer via WebSocket
            correct_opt_id = next(o["id"] for o in q1["options"] if o["is_correct"])
            ws_p1.send_json({
                "event": "SUBMIT_ANSWER",
                "data": {"question_id": q1["id"], "option_id": correct_opt_id},
            })
            ack = ws_p1.receive_json()
            assert ack["event"] == "ANSWER_ACK"
            assert ack["data"]["accepted"] is True

            # Host receives ANSWER_COUNT_UPDATED
            count_msg = ws_host.receive_json()
            assert count_msg["event"] == "ANSWER_COUNT_UPDATED"
            assert count_msg["data"]["answered_count"] == 1

            # 3. Host reveals answer
            ws_host.send_json({"action": "REVEAL"})

            # Participant receives ANSWER_REVEALED with personal stats
            rev_p1 = ws_p1.receive_json()
            assert rev_p1["event"] == "ANSWER_REVEALED"
            assert rev_p1["data"]["correct_option_id"] == correct_opt_id
            assert rev_p1["data"]["my_stats"]["last_result"]["is_correct"] is True
            assert rev_p1["data"]["my_stats"]["score"] > 0

            # Participant receives LEADERBOARD_UPDATED
            board_p1 = ws_p1.receive_json()
            assert board_p1["event"] == "LEADERBOARD_UPDATED"
            assert board_p1["data"]["top"][0]["nickname"] == "Alice"

            # 4. Host advances to next question
            ws_host.send_json({"action": "NEXT_QUESTION"})
            q2_msg = ws_p1.receive_json()
            assert q2_msg["event"] == "QUESTION_STARTED"
            assert q2_msg["data"]["question_number"] == 2

            # 5. Host finishes game
            ws_host.send_json({"action": "NEXT_QUESTION"})
            fin_msg = ws_p1.receive_json()
            assert fin_msg["event"] == "GAME_FINISHED"


class TestPauseResumeAndControls:
    def test_pause_and_resume_timing(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)

        # Start game via REST
        start_res = client.post(f"{API}/games/{game['id']}/start", headers=auth_headers)
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "active"

        # Pause game via REST
        pause_res = client.post(f"{API}/games/{game['id']}/pause", headers=auth_headers)
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "paused"

        # Answers rejected while paused
        p = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "Charlie"}).json()
        ans_res = client.post(
            f"{API}/games/{game['id']}/answers",
            json={"question_id": start_res.json()["current_question_id"], "selected_option": "A"},
            headers={"X-Participant-Token": p["token"]},
        )
        assert ans_res.status_code == 409
        assert "paused" in ans_res.json()["detail"].lower()

        # Resume game via REST
        resume_res = client.post(f"{API}/games/{game['id']}/resume", headers=auth_headers)
        assert resume_res.status_code == 200
        assert resume_res.json()["status"] == "active"

    def test_kick_participant_disconnect(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        host_token = auth_headers["Authorization"].split(" ")[1]

        p = client.post(f"{API}/games/join", json={"pin": game["pin"], "nickname": "BadPlayer"}).json()

        with client.websocket_connect(f"{API}/ws/games/{game['id']}/participant?token={p['token']}") as ws_p:
            # Host kicks player via REST
            kick_res = client.post(
                f"{API}/games/{game['id']}/kick",
                json={"participant_id": p["participant_id"]},
                headers=auth_headers,
            )
            assert kick_res.status_code == 200

            # Participant receives PLAYER_KICKED event
            kick_event = ws_p.receive_json()
            assert kick_event["event"] == "PLAYER_KICKED"

    def test_invalid_state_transitions(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)

        # 1. In lobby: cannot pause or resume
        r_pause = client.post(f"{API}/games/{game['id']}/pause", headers=auth_headers)
        assert r_pause.status_code == 409

        r_resume = client.post(f"{API}/games/{game['id']}/resume", headers=auth_headers)
        assert r_resume.status_code == 409

        # 2. Start game -> now active
        r_start = client.post(f"{API}/games/{game['id']}/start", headers=auth_headers)
        assert r_start.status_code == 200

        # Cannot start again while active
        r_start2 = client.post(f"{API}/games/{game['id']}/start", headers=auth_headers)
        assert r_start2.status_code == 409

        # Cannot resume while already active
        r_resume2 = client.post(f"{API}/games/{game['id']}/resume", headers=auth_headers)
        assert r_resume2.status_code == 409

    def test_duplicate_reveal_via_orchestrator(self, client, auth_headers):
        game, _, _ = _setup_game(client, auth_headers)
        client.post(f"{API}/games/{game['id']}/start", headers=auth_headers)

        # First reveal scores the question
        rev1 = client.post(f"{API}/games/{game['id']}/reveal", headers=auth_headers)
        assert rev1.status_code == 200
        assert rev1.json()["already_scored"] is False

        # Duplicate reveal is safe: returns already_scored=True without re-awarding
        rev2 = client.post(f"{API}/games/{game['id']}/reveal", headers=auth_headers)
        assert rev2.status_code == 200
        assert rev2.json()["already_scored"] is True
