"""WebSocket connection manager for team messenger."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TeamMessengerManager:
    """Tracks active WebSocket connections per team."""

    def __init__(self) -> None:
        self._rooms: dict[int, dict[int, WebSocket]] = {}

    async def connect(self, team_id: int, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if team_id not in self._rooms:
            self._rooms[team_id] = {}
        self._rooms[team_id][user_id] = websocket
        logger.debug("User %d connected to team %d messenger", user_id, team_id)

    def disconnect(self, team_id: int, user_id: int) -> None:
        room = self._rooms.get(team_id)
        if room and user_id in room:
            del room[user_id]
        if room and not room:
            del self._rooms[team_id]
        logger.debug("User %d disconnected from team %d messenger", user_id, team_id)

    async def broadcast(self, team_id: int, payload: dict[str, Any]) -> None:
        """Send a JSON event to all connected clients in a team room."""
        room = self._rooms.get(team_id, {})
        message = json.dumps(payload, default=str)
        dead: list[int] = []
        for user_id, ws in room.items():
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(user_id)
        for user_id in dead:
            self.disconnect(team_id, user_id)


messenger_manager = TeamMessengerManager()
