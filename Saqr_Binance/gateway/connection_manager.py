"""
Central WebSocket pub/sub hub for terminal UI and internal subscribers.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Set

from fastapi import WebSocket

from utils.logger_config import setup_logger

logger = setup_logger("saqr.hub")


@dataclass
class ConnectionManager:
    """Fan-out broadcaster with bounded recent history for late joiners."""

    clients: Set[WebSocket] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _recent: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=1000))
    _heartbeat_task: asyncio.Task | None = field(default=None, init=False)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)
        await self._send_json(websocket, {"type": "welcome", "ts": time.time()})
        for msg in list(self._recent)[-50:]:
            await self._send_json(websocket, msg)
        logger.info("WS client connected (%s total)", len(self.clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(websocket)
        logger.info("WS client disconnected (%s total)", len(self.clients))

    async def publish(self, message: Dict[str, Any]) -> None:
        message.setdefault("ts", time.time())
        self._recent.append(message)
        async with self._lock:
            targets = list(self.clients)
        if not targets:
            return
        dead: List[WebSocket] = []
        for ws in targets:
            try:
                await self._send_json(ws, message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def _send_json(self, websocket: WebSocket, payload: Dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def start_heartbeat(self, interval: float = 1.0) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                await self.publish({"type": "heartbeat", "live": True})

        self._heartbeat_task = asyncio.create_task(_loop(), name="saqr-ws-heartbeat")

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "clients": len(self.clients),
            "recent_events": len(self._recent),
        }
