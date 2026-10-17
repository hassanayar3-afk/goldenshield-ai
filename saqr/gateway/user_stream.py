"""
Binance user data stream — ListenKey lifecycle, order/balance push events.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager
    from gateway.binance_client import BinanceClient
    from gateway.connection_manager import ConnectionManager

logger = setup_logger("saqr.user_stream")

LISTEN_KEY_STATE = "binance_listen_key"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserStreamService:
    db: "DatabaseManager"
    client: "BinanceClient"
    hub: "ConnectionManager"
    _listen_key: Optional[str] = field(default=None, init=False)
    _running: bool = field(default=False, init=False)
    _keepalive_task: Optional[asyncio.Task] = field(default=None, init=False)
    base_backoff: float = 0.5

    async def _backoff_sleep(self, attempt: int) -> None:
        jitter = random.uniform(0, self.base_backoff)
        await asyncio.sleep(min(self.base_backoff * (2**attempt) + jitter, 30.0))

    async def _ensure_listen_key(self) -> str:
        cached = await self.db.get_runtime_state_async(LISTEN_KEY_STATE)
        if cached and (self.client.paper_trading or not cached.startswith("paper_listen_")):
            self._listen_key = cached
            try:
                await self.client.keepalive_listen_key(cached)
                return cached
            except Exception as exc:
                logger.warning("ListenKey keepalive failed, minting new key: %s", exc)

        listen_key = await self.client.create_listen_key()
        self._listen_key = listen_key
        await self.db.set_runtime_state_async(LISTEN_KEY_STATE, listen_key, _utc_now())
        return listen_key

    async def _keepalive_loop(self) -> None:
        interval = float(os.getenv("LISTEN_KEY_KEEPALIVE_MINUTES", "25")) * 60.0
        while self._running:
            await asyncio.sleep(interval)
            if not self._listen_key:
                continue
            try:
                await self.client.keepalive_listen_key(self._listen_key)
                await self.db.set_runtime_state_async(LISTEN_KEY_STATE, self._listen_key, _utc_now())
                logger.info("ListenKey keepalive OK")
            except Exception as exc:
                logger.error("ListenKey keepalive error: %s", exc)

    @crash_proof(component="user_stream", restart_delay=2.0)
    async def run_forever(self) -> None:
        self._running = True
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(), name="listen-key-keepalive")
        try:
            while self._running:
                touch_event_loop_heartbeat()
                try:
                    await self._consume_session()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("User stream session error: %s", exc)
                if self._running:
                    await self._backoff_sleep(0)
        finally:
            if self._keepalive_task:
                self._keepalive_task.cancel()
                try:
                    await self._keepalive_task
                except asyncio.CancelledError:
                    pass

    async def _consume_session(self) -> None:
        listen_key = await self._ensure_listen_key()
        url = self.client.user_stream_url(listen_key)

        if self.client.paper_trading or listen_key.startswith("paper_listen_"):
            await self.hub.publish(
                {
                    "type": "user_stream",
                    "status": "paper",
                    "listen_key": listen_key[:12] + "...",
                }
            )
            while self._running:
                touch_event_loop_heartbeat()
                await asyncio.sleep(float(os.getenv("LOOP_INTERVAL_SECONDS", "4")))
            return

        logger.info("Connecting user data stream")
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            await self.hub.publish({"type": "user_stream", "status": "connected"})
            while self._running:
                touch_event_loop_heartbeat()
                raw = await ws.recv()
                await self._handle_event(raw)

    async def _handle_event(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return

        event_type = event.get("e")
        payload: Dict[str, Any] = {"type": "user_event", "event": event_type, "raw": event}
        await self.hub.publish(payload)

        if event_type != "executionReport":
            return

        symbol = str(event.get("s", ""))
        client_order_id = str(event.get("c", ""))
        status = str(event.get("X", ""))
        order_type = str(event.get("o", ""))

        if order_type == "STOP_MARKET" and client_order_id:
            stop_price = float(event.get("P", event.get("sp", 0)) or 0)
            await self.db.register_protection_order_async(
                client_order_id,
                symbol,
                stop_price,
                status,
                _utc_now(),
            )

        if status in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
            logger.info("Order update %s %s %s", symbol, client_order_id, status)

    def stop(self) -> None:
        self._running = False

    async def shutdown(self) -> None:
        self.stop()
        if self._listen_key:
            try:
                await self.client.close_listen_key(self._listen_key)
            except Exception as exc:
                logger.warning("ListenKey close failed: %s", exc)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "listen_key_active": bool(self._listen_key),
            "paper": self.client.paper_trading,
        }
