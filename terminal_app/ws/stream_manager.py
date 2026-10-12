"""WebSocket stream manager — Binance depth/trade + بث للتطبيق."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    channel: str
    symbol: str
    payload: dict[str, Any]
    ts: float = field(default_factory=time.time)


class StreamManager:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()
        self._lock = threading.Lock()
        self._recent: deque[StreamEvent] = deque(maxlen=500)
        self._started: set[str] = set()

    def record(self, event: StreamEvent) -> None:
        with self._lock:
            self._recent.append(event)
        for queue in list(self._clients):
            try:
                queue.put_nowait(event)
            except Exception:
                pass

    def subscribe_queue(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._clients.add(queue)
        return queue

    def unsubscribe_queue(self, queue: asyncio.Queue) -> None:
        self._clients.discard(queue)

    def ensure_binance_stream(self, symbol: str) -> None:
        key = symbol.replace("/", "").lower()
        with self._lock:
            if key in self._started:
                return
            self._started.add(key)
        threading.Thread(
            target=lambda: asyncio.run(self._run_binance_ws(symbol)),
            name=f"binance-ws-{key}",
            daemon=True,
        ).start()

    async def _run_binance_ws(self, symbol: str) -> None:
        stream = symbol.replace("/", "").lower() + "@trade"
        url = f"wss://stream.binance.com:9443/ws/{stream}"
        try:
            import websockets
        except ImportError:
            logger.warning("websockets not installed — WS stream disabled")
            return
        while True:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for message in ws:
                        data = json.loads(message)
                        price = float(data.get("p") or data.get("price") or 0)
                        self.record(
                            StreamEvent(
                                channel="trade",
                                symbol=symbol,
                                payload={"price": price, "raw": data},
                            )
                        )
            except Exception as exc:
                logger.debug("WS reconnect %s: %s", symbol, exc)
                await asyncio.sleep(2.0)

    def snapshot_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._recent)[-limit:]
        return [
            {
                "channel": event.channel,
                "symbol": event.symbol,
                "payload": event.payload,
                "ts": event.ts,
            }
            for event in items
        ]


_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    global _manager
    if _manager is None:
        _manager = StreamManager()
    return _manager
