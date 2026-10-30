"""Real-protocol WebSocket load probe for a prepared QuizVoro game.

Run from quiz-backend with the backend running as a single Uvicorn worker.
The game must be in its lobby state so START produces QUESTION_STARTED.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import websockets
import psutil


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * pct))]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("QUIZVORO_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--game-id", type=int, required=True)
    parser.add_argument("--pin", default=os.getenv("QUIZVORO_GAME_PIN"))
    parser.add_argument("--username", default=os.getenv("QUIZVORO_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("QUIZVORO_ADMIN_PASSWORD"))
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--ramp-rate", type=float, default=10, help="Connections started per second")
    parser.add_argument("--duration", type=float, default=30, help="Seconds to hold sockets open")
    parser.add_argument("--connect-timeout", type=float, default=10)
    parser.add_argument("--server-pid", type=int, help="PID of the local Uvicorn process; enables server CPU and RSS sampling")
    parser.add_argument("--output", help="Optional JSON results file")
    args = parser.parse_args()

    if not args.pin or not args.username or not args.password:
        parser.error("--pin, --username, and --password are required (or set the corresponding QUIZVORO_* environment variables)")
    if args.clients < 1 or args.ramp_rate <= 0 or args.duration < 0:
        parser.error("clients and ramp-rate must be positive; duration cannot be negative")

    base = args.base_url.rstrip("/")
    ws_base = "wss://" + base[8:] if base.startswith("https://") else "ws://" + base[7:] if base.startswith("http://") else base
    api = base + "/api/v1"
    timeout = httpx.Timeout(20, connect=5)
    async with httpx.AsyncClient(timeout=timeout) as http:
        login = await http.post(f"{api}/admin/login", json={"username": args.username, "password": args.password})
        login.raise_for_status()
        admin_token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        stage_response = await http.get(f"{api}/games/{args.game_id}/stage-token", headers=headers)
        stage_response.raise_for_status()
        stage_token = stage_response.json()["stage_token"]

        async def join(index: int) -> dict:
            response = await http.post(f"{api}/games/join", json={"pin": args.pin, "nickname": f"Load{index:06d}"})
            response.raise_for_status()
            return response.json()

        joins: list[dict] = []
        join_errors: list[str] = []
        start_time = time.perf_counter()
        for index in range(args.clients):
            try:
                joins.append(await join(index))
            except Exception as exc:
                join_errors.append(f"client {index}: {type(exc).__name__}: {exc}")
            delay = 1 / args.ramp_rate
            if index + 1 < args.clients:
                await asyncio.sleep(delay)

    async def connect_one(member: dict) -> tuple[object | None, float | None, str | None]:
        url = f"{ws_base}/api/v1/ws/games/{args.game_id}/participant?{urlencode({'token': member['token']})}"
        started = time.perf_counter()
        try:
            # These are short-lived local load probes. Protocol keepalive pings
            # add false failures when the server is busy processing a ramp.
            socket = await asyncio.wait_for(websockets.connect(
                url,
                open_timeout=args.connect_timeout,
                ping_interval=None,
                close_timeout=2,
                max_queue=None,
            ), timeout=args.connect_timeout + 1)
            return socket, (time.perf_counter() - started) * 1000, None
        except Exception as exc:
            return None, None, f"participant {member.get('participant_id')}: {type(exc).__name__}: {exc}"

    async def paced_connect(index: int, member: dict) -> tuple[object | None, float | None, str | None]:
        # Pace the actual WebSocket handshakes too; otherwise gather() opens every
        # participant socket at once and can overwhelm the server before stage/host connect.
        await asyncio.sleep(index / args.ramp_rate)
        return await connect_one(member)

    errors = list(join_errors)
    sockets = []
    connect_ms = []
    stage_socket = None
    host_socket = None
    control_drainers = []
    broadcast_latencies: list[float] = []
    delivered = 0
    unexpected_disconnects = 0
    server_cpu: list[float] = []
    server_rss_mb: list[float] = []
    sampler_stop = asyncio.Event()
    sampler = None
    if args.server_pid:
        server_process = psutil.Process(args.server_pid)
        server_process.cpu_percent(None)

        async def sample_server() -> None:
            while not sampler_stop.is_set():
                try:
                    server_cpu.append(server_process.cpu_percent(None))
                    server_rss_mb.append(server_process.memory_info().rss / (1024 * 1024))
                except psutil.Error:
                    break
                try:
                    await asyncio.wait_for(sampler_stop.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass

        sampler = asyncio.create_task(sample_server())
    test_started = time.perf_counter()

    try:
        # Establish the control/display sockets before participant handshakes.
        # At larger stages, participant join broadcasts can keep the event loop
        # busy; opening these first avoids timing out the stage socket afterward.
        stage_url = f"{ws_base}/api/v1/ws/games/{args.game_id}/stage?{urlencode({'token': stage_token})}"
        host_url = f"{ws_base}/api/v1/ws/games/{args.game_id}/host?{urlencode({'token': admin_token})}"
        ws_options = {
            "open_timeout": args.connect_timeout,
            "ping_interval": None,
            "close_timeout": 2,
            "max_queue": None,
        }
        stage_socket = await websockets.connect(stage_url, **ws_options)
        host_socket = await websockets.connect(host_url, **ws_options)

        async def drain_control(socket) -> None:
            # The server sends PLAYER_JOINED to host and stage for every
            # participant. Keep reading during the ramp so the websockets
            # client's bounded receive queue cannot fill and stall keepalives.
            try:
                async for _ in socket:
                    pass
            except Exception:
                pass

        control_drainers = [
            asyncio.create_task(drain_control(stage_socket)),
            asyncio.create_task(drain_control(host_socket)),
        ]

        if not joins:
            raise RuntimeError("No participants joined; check the game PIN and confirm the game is still in its lobby.")

        connect_results = await asyncio.gather(*(paced_connect(index, member) for index, member in enumerate(joins)))
        sockets = [result[0] for result in connect_results if result[0] is not None]
        connect_ms = [result[1] for result in connect_results if result[1] is not None]
        errors.extend(result[2] for result in connect_results if result[2])

        for task in control_drainers:
            task.cancel()
        await asyncio.gather(*control_drainers, return_exceptions=True)
        control_drainers = []

        # Joining emits PLAYER_JOINED, so drain those notifications before the measured broadcast.
        async def drain(socket, seconds: float = 1.0) -> None:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    await asyncio.wait_for(socket.recv(), timeout=max(0.01, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    return
                except Exception:
                    return

        await asyncio.gather(*(drain(socket) for socket in sockets), drain(stage_socket), drain(host_socket))
        sent_at = time.perf_counter()
        try:
            await host_socket.send(json.dumps({"action": "START"}))
        except Exception as exc:
            errors.append(f"host START send: {type(exc).__name__}: {exc}")

        async def await_question(socket) -> float | None:
            nonlocal unexpected_disconnects
            try:
                deadline = time.monotonic() + args.connect_timeout
                while time.monotonic() < deadline:
                    raw = await asyncio.wait_for(socket.recv(), timeout=max(0.01, deadline - time.monotonic()))
                    message = json.loads(raw)
                    if message.get("event") == "QUESTION_STARTED":
                        return (time.perf_counter() - sent_at) * 1000
                    if message.get("event") == "ERROR":
                        raise RuntimeError(message.get("data", {}).get("detail", "broadcast rejected"))
            except Exception:
                unexpected_disconnects += 1
            return None

        arrivals = (
            await asyncio.gather(*(await_question(socket) for socket in sockets))
            if not any(error.startswith("host START send:") for error in errors)
            else [None] * len(sockets)
        )
        broadcast_latencies = [latency for latency in arrivals if latency is not None]
        delivered = len(broadcast_latencies)
        test_started = time.perf_counter()
        hold_until = test_started + args.duration
        while time.perf_counter() < hold_until:
            await asyncio.sleep(min(0.5, hold_until - time.perf_counter()))
            for socket in sockets:
                if getattr(socket, "close_code", None) is not None:
                    unexpected_disconnects += 1
        elapsed = time.perf_counter() - test_started
    finally:
        for task in control_drainers:
            task.cancel()
        if control_drainers:
            await asyncio.gather(*control_drainers, return_exceptions=True)
        if sampler:
            sampler_stop.set()
            await sampler
        async def safe_close(socket) -> None:
            if socket is None:
                return
            try:
                await socket.close()
            except Exception:
                pass

        await asyncio.gather(*(safe_close(socket) for socket in sockets), return_exceptions=True)
        await asyncio.gather(safe_close(stage_socket), safe_close(host_socket), return_exceptions=True)

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "game_id": args.game_id,
        "requested_clients": args.clients,
        "joined": len(joins),
        "connected": len(sockets),
        "connection_success_rate_pct": round(100 * len(sockets) / args.clients, 2),
        "connection_time_ms_avg": round(statistics.mean(connect_ms), 2) if connect_ms else None,
        "connection_time_ms_p95": round(percentile(connect_ms, 0.95), 2) if connect_ms else None,
        "question_started_delivered": delivered,
        "broadcast_delivery_rate_pct": round(100 * delivered / len(sockets), 2) if sockets else None,
        "broadcast_latency_ms_avg": round(statistics.mean(broadcast_latencies), 2) if broadcast_latencies else None,
        "broadcast_latency_ms_p95": round(percentile(broadcast_latencies, 0.95), 2) if broadcast_latencies else None,
        "unexpected_disconnects": unexpected_disconnects,
        "server_cpu_pct_avg": round(statistics.mean(server_cpu), 2) if server_cpu else None,
        "server_rss_mb_max": round(max(server_rss_mb), 2) if server_rss_mb else None,
        "elapsed_seconds": round(elapsed, 2),
        "errors": errors[:30],
    }
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    return 0 if len(sockets) == args.clients and delivered == len(sockets) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))





