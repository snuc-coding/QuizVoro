"""Exercise answer submission, automatic/manual reveal, and scores at load.

Use a quiz with at least one MCQ question. The script creates a fresh game and
uses the first question's correct option. Every synthetic participant and
answer is persisted, so it intentionally does not delete test data. Run against
a staging/local backend using PostgreSQL and one Uvicorn worker (the WebSocket
room manager is process-local).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
import uuid
from urllib.parse import urlencode

import httpx
import websockets


async def receive_event(socket, expected: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(socket.recv(), timeout=max(0.05, deadline - time.monotonic()))
        message = json.loads(raw)
        if message.get("event") == "ERROR":
            raise RuntimeError(message.get("data", {}).get("detail", "WebSocket error"))
        if message.get("event") == expected:
            return message.get("data", {})
    raise TimeoutError(f"Did not receive {expected} within {timeout:g}s")


async def paced_join(http: httpx.AsyncClient, api: str, pin: str, index: int, rate: float, run_id: str):
    await asyncio.sleep(index / rate)
    response = await http.post(
        f"{api}/games/join",
        json={"pin": pin, "nickname": f"Load{run_id}{index:04d}"},
    )
    response.raise_for_status()
    return response.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("QUIZVORO_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--quiz-id", type=int, required=True, help="Owned quiz; first question is used")
    parser.add_argument("--username", default=os.getenv("QUIZVORO_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("QUIZVORO_ADMIN_PASSWORD"))
    parser.add_argument("--clients", type=int, default=500)
    parser.add_argument("--ramp-rate", type=float, default=3, help="Join/socket handshakes per second")
    parser.add_argument("--mode", choices=("timer", "manual"), default="timer")
    parser.add_argument("--timeout", type=float, default=330, help="Maximum wait for question/reveal events")
    parser.add_argument("--output", help="Optional JSON results file")
    args = parser.parse_args()
    if not args.username or not args.password:
        parser.error("--username and --password are required (or set QUIZVORO_ADMIN_* environment variables)")
    if args.clients < 1 or args.ramp_rate <= 0:
        parser.error("--clients and --ramp-rate must be positive")

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v1"
    ws_base = "wss://" + base[8:] if base.startswith("https://") else "ws://" + base[7:]
    run_id = uuid.uuid4().hex[:6]
    limits = httpx.Limits(max_connections=args.clients + 20, max_keepalive_connections=args.clients + 20)
    timeout = httpx.Timeout(40, connect=15)
    participant_sockets = []
    host_socket = None
    errors: list[str] = []
    result: dict = {
        "quiz_id": args.quiz_id,
        "requested_clients": args.clients,
        "mode": args.mode,
        "joined": 0,
        "connected": 0,
        "accepted_answers": 0,
        "revealed_to_participants": 0,
        "correct_scores": 0,
        "errors": errors,
    }

    def report() -> None:
        rendered = json.dumps(result, indent=2)
        print(rendered)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as stream:
                stream.write(rendered + "\n")

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as http:
        login = await http.post(f"{api}/admin/login", json={"username": args.username, "password": args.password})
        login.raise_for_status()
        admin_token = login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        quiz_response = await http.get(f"{api}/quizzes/{args.quiz_id}", headers=admin_headers)
        quiz_response.raise_for_status()
        quiz = quiz_response.json()
        questions = [
            question
            for round_ in sorted(quiz.get("rounds", []), key=lambda r: r.get("round_number", 0))
            for question in sorted(round_.get("questions", []), key=lambda q: q.get("question_order", 0))
        ]
        if not questions:
            raise RuntimeError("The selected quiz has no questions.")
        question = questions[0]
        correct_options = [option for option in question.get("options", []) if option.get("is_correct")]
        if len(correct_options) != 1:
            raise RuntimeError("The first question must have exactly one correct option.")
        question_id = int(question["id"])
        option_id = int(correct_options[0]["id"])
        result["question_id"] = question_id
        result["time_limit_seconds"] = question["time_limit"]

        game_response = await http.post(f"{api}/games", headers=admin_headers, json={"quiz_id": args.quiz_id})
        game_response.raise_for_status()
        game = game_response.json()
        game_id, pin = int(game["id"]), game["pin"]
        result["game_id"] = game_id

        join_results = await asyncio.gather(*(
            paced_join(http, api, pin, i, args.ramp_rate, run_id)
            for i in range(args.clients)
        ), return_exceptions=True)
        members = []
        for i, item in enumerate(join_results):
            if isinstance(item, Exception):
                errors.append(f"join {i}: {type(item).__name__}: {item}")
            else:
                members.append(item)
        result["joined"] = len(members)
        if len(members) != args.clients:
            result["passed"] = False
            report()
            return 1

        host_url = f"{ws_base}/api/v1/ws/games/{game_id}/host?{urlencode({'token': admin_token})}"
        host_socket = await websockets.connect(host_url, open_timeout=20, ping_interval=None, max_queue=None)

        async def drain_host_notifications() -> None:
            try:
                async for _ in host_socket:
                    pass
            except Exception:
                pass

        # The host receives one PLAYER_JOINED event per player. Drain them while
        # sockets connect so its receive buffer cannot back up at larger stages.
        host_drainer = asyncio.create_task(drain_host_notifications())

        async def connect_member(member: dict, index: int):
            await asyncio.sleep(index / args.ramp_rate)
            url = f"{ws_base}/api/v1/ws/games/{game_id}/participant?{urlencode({'token': member['token']})}"
            return await websockets.connect(url, open_timeout=20, ping_interval=None, max_queue=None)

        connected = await asyncio.gather(*(
            connect_member(member, i) for i, member in enumerate(members)
        ), return_exceptions=True)
        live_members = []
        for i, socket in enumerate(connected):
            if isinstance(socket, Exception):
                errors.append(f"websocket {i}: {type(socket).__name__}: {socket}")
            else:
                participant_sockets.append(socket)
                live_members.append(members[i])
        result["connected"] = len(live_members)
        if len(live_members) != args.clients:
            host_drainer.cancel()
            await asyncio.gather(host_drainer, return_exceptions=True)
            result["passed"] = False
            report()
            await asyncio.gather(*(socket.close() for socket in participant_sockets), return_exceptions=True)
            await host_socket.close()
            return 1
        host_drainer.cancel()
        await asyncio.gather(host_drainer, return_exceptions=True)

        # Run readers before START so the test does not depend on socket queue size.
        question_tasks = [asyncio.create_task(receive_event(s, "QUESTION_STARTED", 30)) for s in participant_sockets]
        await host_socket.send(json.dumps({"action": "START"}))
        questions = await asyncio.gather(*question_tasks, return_exceptions=True)
        question_failures = [q for q in questions if isinstance(q, Exception)]
        if question_failures:
            raise RuntimeError(f"QUESTION_STARTED reached only {len(questions) - len(question_failures)}/{args.clients} clients")
        if any(int(q.get("question", {}).get("id", -1)) != question_id for q in questions):
            raise RuntimeError("The game did not start on the expected first question.")

        answer_started = time.perf_counter()

        async def submit(member: dict):
            response = await http.post(
                f"{api}/games/{game_id}/answers",
                headers={"X-Participant-Token": member["token"]},
                json={"question_id": question_id, "option_id": option_id},
            )
            if response.status_code != 201:
                return response.status_code, response.text[:300]
            return 201, response.json()

        submissions = await asyncio.gather(*(submit(m) for m in live_members), return_exceptions=True)
        answer_ms = (time.perf_counter() - answer_started) * 1000
        successful = [s for s in submissions if not isinstance(s, Exception) and s[0] == 201]
        result["accepted_answers"] = len(successful)
        result["answer_burst_ms"] = round(answer_ms, 2)
        for i, submission in enumerate(submissions):
            if isinstance(submission, Exception):
                errors.append(f"answer {i}: {type(submission).__name__}: {submission}")
            elif submission[0] != 201:
                errors.append(f"answer {i}: HTTP {submission[0]}: {submission[1]}")

        reveal_tasks = [asyncio.create_task(receive_event(s, "ANSWER_REVEALED", args.timeout)) for s in participant_sockets]
        if args.mode == "manual":
            await host_socket.send(json.dumps({"action": "REVEAL"}))
        reveals = await asyncio.gather(*reveal_tasks, return_exceptions=True)
        revealed = [r for r in reveals if not isinstance(r, Exception)]
        result["revealed_to_participants"] = len(revealed)
        for i, reveal in enumerate(reveals):
            if isinstance(reveal, Exception):
                errors.append(f"reveal {i}: {type(reveal).__name__}: {reveal}")

        async def fetch_stats(member: dict):
            response = await http.get(
            f"{api}/games/{game_id}/me",
                headers={"X-Participant-Token": member["token"]},
            )
            response.raise_for_status()
            return response.json()

        stats_results = await asyncio.gather(*(fetch_stats(m) for m in live_members), return_exceptions=True)
        valid_stats = []
        for i, stats in enumerate(stats_results):
            if isinstance(stats, Exception):
                errors.append(f"stats {i}: {type(stats).__name__}: {stats}")
            else:
                valid_stats.append(stats)
        correct_scores = [
            s for s in valid_stats
            if s.get("last_result", {}).get("question_id") == question_id
            and s.get("last_result", {}).get("answered") is True
            and s.get("last_result", {}).get("is_correct") is True
            and s.get("last_result", {}).get("points", 0) >= 0
            and s.get("score", 0) >= 0
        ]
        result["stats_received"] = len(valid_stats)
        result["correct_scores"] = len(correct_scores)
        if valid_stats:
            scores = [s["score"] for s in valid_stats]
            result["score_min"] = min(scores)
            result["score_max"] = max(scores)
            result["score_avg"] = round(statistics.mean(scores), 2)

        # Close the one-question test game so it is visibly complete in the UI.
        try:
            await host_socket.send(json.dumps({"action": "END"}))
        except Exception as exc:
            errors.append(f"end game: {type(exc).__name__}: {exc}")

    success = (
        result["joined"] == args.clients
        and result["connected"] == args.clients
        and result["accepted_answers"] == args.clients
        and result["revealed_to_participants"] == args.clients
        and result.get("stats_received") == args.clients
        and result["correct_scores"] == args.clients
    )
    result["passed"] = success
    report()
    for socket in participant_sockets:
        try:
            await socket.close()
        except Exception:
            pass
    if host_socket is not None:
        try:
            await host_socket.close()
        except Exception:
            pass
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
