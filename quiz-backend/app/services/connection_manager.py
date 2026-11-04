"""
connection_manager.py — In-memory WebSocket room and connection manager.

Developer 3: Real-time WebSocket connection lifecycle.

Architecture:
  - Manages active WebSocket connections grouped by game_id.
  - Partitions connections into three roles:
      1. hosts: The admin host managing the game.
      2. participants: Players mapped by participant_id (supports multi-tab / reconnects).
      3. stages: Public displays (projectors / audience screens).
  - Designed for a few hundred concurrent participants on a single ASGI worker.
  - Multi-worker note: For multi-worker deployments (e.g., behind a load balancer
    with multiple Uvicorn instances), an external pub/sub backend such as Redis
    Pub/Sub or RabbitMQ is required to synchronize broadcasts across processes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from fastapi import WebSocket

from app.websocket_schemas import EventType, WebSocketMessage

logger = logging.getLogger("quizvoro.realtime")
SEND_TIMEOUT_SECONDS = float(os.getenv("WEBSOCKET_SEND_TIMEOUT", "2"))


class GameRoom:
    """Holds active connections for a single game session."""

    def __init__(self, game_id: int):
        self.game_id = game_id
        self.hosts: set[WebSocket] = set()
        self.participants: dict[int, set[WebSocket]] = {}
        self.stages: set[WebSocket] = set()
        self.paused_at: Any = None  # in-memory store for pause timestamp if needed


class ConnectionManager:
    """Thread-safe and async-safe room manager for live games."""

    def __init__(self):
        self._rooms: dict[int, GameRoom] = {}
        self._lock = asyncio.Lock()
        self._socket_send_locks: dict[WebSocket, asyncio.Lock] = {}

    def _get_or_create_room(self, game_id: int) -> GameRoom:
        if game_id not in self._rooms:
            self._rooms[game_id] = GameRoom(game_id)
        return self._rooms[game_id]

    def _cleanup_empty_room(self, game_id: int):
        room = self._rooms.get(game_id)
        if room:
            has_hosts = bool(room.hosts)
            has_participants = any(bool(sockets) for sockets in room.participants.values())
            has_stages = bool(room.stages)
            if not (has_hosts or has_participants or has_stages):
                self._rooms.pop(game_id, None)

    # ── Host Connection Lifecycle ─────────────────────────────────────────────

    async def connect_host(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._get_or_create_room(game_id)
            room.hosts.add(websocket)
        logger.info(f"Host connected to game {game_id}. Total hosts: {len(room.hosts)}")

    async def disconnect_host(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(game_id)
            if room and websocket in room.hosts:
                room.hosts.remove(websocket)
                self._cleanup_empty_room(game_id)
            self._socket_send_locks.pop(websocket, None)
        logger.info(f"Host disconnected from game {game_id}")

    # ── Participant Connection Lifecycle ──────────────────────────────────────

    async def connect_participant(self, game_id: int, participant_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._get_or_create_room(game_id)
            if participant_id not in room.participants:
                room.participants[participant_id] = set()
            room.participants[participant_id].add(websocket)
        logger.info(f"Participant {participant_id} connected to game {game_id}")

    async def disconnect_participant(self, game_id: int, participant_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(game_id)
            if room and participant_id in room.participants:
                room.participants[participant_id].discard(websocket)
                if not room.participants[participant_id]:
                    room.participants.pop(participant_id, None)
                self._cleanup_empty_room(game_id)
            self._socket_send_locks.pop(websocket, None)
        logger.info(f"Participant {participant_id} disconnected from game {game_id}")

    # ── Stage Display Connection Lifecycle ────────────────────────────────────

    async def connect_stage(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._get_or_create_room(game_id)
            room.stages.add(websocket)
        logger.info(f"Stage display connected to game {game_id}. Total stages: {len(room.stages)}")

    async def disconnect_stage(self, game_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(game_id)
            if room and websocket in room.stages:
                room.stages.remove(websocket)
                self._cleanup_empty_room(game_id)
            self._socket_send_locks.pop(websocket, None)
        logger.info(f"Stage display disconnected from game {game_id}")

    # ── Query Helpers ─────────────────────────────────────────────────────────

    def get_connected_participant_ids(self, game_id: int) -> set[int]:
        room = self._rooms.get(game_id)
        if not room:
            return set()
        return {pid for pid, sockets in room.participants.items() if sockets}

    def get_room(self, game_id: int) -> GameRoom | None:
        return self._rooms.get(game_id)

    # ── Safe Sending & Broadcasting ───────────────────────────────────────────

    async def _send_safe(self, websocket: WebSocket, message_dict: dict[str, Any]) -> bool:
        """Safely send JSON message. Returns False if socket is broken."""
        try:
            lock = self._socket_send_locks.setdefault(websocket, asyncio.Lock())
            async with lock:
                await asyncio.wait_for(websocket.send_json(message_dict), timeout=SEND_TIMEOUT_SECONDS)
            return True
        except Exception:
            return False

    @staticmethod
    async def _close_safe(websocket: WebSocket) -> None:
        try:
            await asyncio.wait_for(websocket.close(code=1011, reason="WebSocket send timed out"), timeout=1)
        except Exception:
            pass

    def _format_message(self, message: dict[str, Any] | WebSocketMessage) -> dict[str, Any]:
        if isinstance(message, WebSocketMessage):
            return message.to_json_dict()
        return message

    async def broadcast_to_game(self, game_id: int, message: dict[str, Any] | WebSocketMessage) -> None:
        """Broadcast message to all connected hosts, participants, and stage displays."""
        room = self._rooms.get(game_id)
        if not room:
            return

        payload = self._format_message(message)
        dead_hosts: set[WebSocket] = set()
        dead_stages: set[WebSocket] = set()
        dead_participants: list[tuple[int, WebSocket]] = []

        targets = (
            [("host", None, ws) for ws in list(room.hosts)]
            + [("stage", None, ws) for ws in list(room.stages)]
            + [("participant", pid, ws) for pid, sockets in list(room.participants.items()) for ws in list(sockets)]
        )
        results = await asyncio.gather(*(self._send_safe(ws, payload) for _, _, ws in targets))
        for (role, pid, ws), success in zip(targets, results):
            if success:
                continue
            if role == "host":
                dead_hosts.add(ws)
            elif role == "stage":
                dead_stages.add(ws)
            else:
                dead_participants.append((pid, ws))

        # Cleanup dead sockets
        if dead_hosts or dead_stages or dead_participants:
            async with self._lock:
                for ws in dead_hosts:
                    room.hosts.discard(ws)
                    self._socket_send_locks.pop(ws, None)
                for ws in dead_stages:
                    room.stages.discard(ws)
                    self._socket_send_locks.pop(ws, None)
                for pid, ws in dead_participants:
                    self._socket_send_locks.pop(ws, None)
                    if pid in room.participants:
                        room.participants[pid].discard(ws)
                        if not room.participants[pid]:
                            room.participants.pop(pid, None)
                self._cleanup_empty_room(game_id)
            await asyncio.gather(*(
                self._close_safe(ws)
                for ws in (*dead_hosts, *dead_stages, *(ws for _, ws in dead_participants))
            ))

    async def broadcast_to_role(
        self, game_id: int, role: str, message: dict[str, Any] | WebSocketMessage
    ) -> None:
        """Broadcast message only to a specific role: 'host', 'stage', or 'participant'."""
        room = self._rooms.get(game_id)
        if not room:
            return

        payload = self._format_message(message)

        if role == "host":
            targets = [("host", None, ws) for ws in list(room.hosts)]
        elif role == "stage":
            targets = [("stage", None, ws) for ws in list(room.stages)]
        elif role == "participant":
            targets = [("participant", pid, ws) for pid, sockets in list(room.participants.items()) for ws in list(sockets)]
        else:
            return
        results = await asyncio.gather(*(self._send_safe(ws, payload) for _, _, ws in targets))
        dead = [(role_name, pid, ws) for (role_name, pid, ws), ok in zip(targets, results) if not ok]
        if dead:
            async with self._lock:
                for role_name, pid, ws in dead:
                    self._socket_send_locks.pop(ws, None)
                    if role_name == "host":
                        room.hosts.discard(ws)
                    elif role_name == "stage":
                        room.stages.discard(ws)
                    elif pid in room.participants:
                        room.participants[pid].discard(ws)
                        if not room.participants[pid]:
                            room.participants.pop(pid, None)
                self._cleanup_empty_room(game_id)
            await asyncio.gather(*(self._close_safe(ws) for _, _, ws in dead))

    async def send_to_participant(
        self, game_id: int, participant_id: int, message: dict[str, Any] | WebSocketMessage
    ) -> bool:
        """Send a unicast message to a specific participant (all their connected sockets)."""
        room = self._rooms.get(game_id)
        if not room or participant_id not in room.participants:
            return False

        payload = self._format_message(message)
        sockets = list(room.participants[participant_id])
        results = await asyncio.gather(*(self._send_safe(ws, payload) for ws in sockets))
        return any(results)

    async def kick_participant(
        self, game_id: int, participant_id: int, reason: str = "Removed by host"
    ) -> None:
        """Notify participant of kick and close their active WebSocket connections."""
        room = self._rooms.get(game_id)
        if not room or participant_id not in room.participants:
            return

        kick_msg = WebSocketMessage(
            event=EventType.PLAYER_KICKED.value,
            data={"participant_id": participant_id, "reason": reason},
        ).to_json_dict()

        sockets = list(room.participants.get(participant_id, set()))
        for ws in sockets:
            await self._send_safe(ws, kick_msg)
            try:
                await ws.close(code=4003, reason=reason)
            except Exception:
                pass

        async with self._lock:
            room.participants.pop(participant_id, None)
            self._cleanup_empty_room(game_id)


# Global singleton manager instance
manager = ConnectionManager()
