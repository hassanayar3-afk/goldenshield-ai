"""WebSocket stream manager — خادم عميل + مرآة دفتر أوامر حية."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SYMBOLS = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT")


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
        self._recent: list[StreamEvent] = []
        self._recent_max = 500
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server_thread: threading.Thread | None = None
        self._ws_port = int(__import__("os").getenv("TERMINAL_WS_PORT", "8791") or 8791)

    def record(self, event: StreamEvent) -> None:
        with self._lock:
            self._recent.append(event)
            if len(self._recent) > self._recent_max:
                self._recent = self._recent[-self._recent_max :]
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

    def snapshot_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            items = self._recent[-limit:]
        return [
            {
                "channel": event.channel,
                "symbol": event.symbol,
                "payload": event.payload,
                "ts": event.ts,
            }
            for event in items
        ]

    def ensure_orderbook_mirror(self, symbol: str) -> None:
        try:
            from data.ws_orderbook_mirror import get_orderbook_mirror

            mirror = get_orderbook_mirror()
            mirror.ensure_stream(symbol)

            def _poll() -> None:
                while True:
                    try:
                        snap = mirror.snapshot(symbol)
                        if snap:
                            self.record(
                                StreamEvent(
                                    channel="orderbook",
                                    symbol=symbol,
                                    payload=snap,
                                )
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("orderbook poll %s: %s", symbol, exc)
                    time.sleep(0.25)

            threading.Thread(
                target=_poll,
                name=f"ob-poll-{symbol.replace('/', '')}",
                daemon=True,
            ).start()
        except Exception as exc:  # noqa: BLE001
            logger.warning("orderbook mirror unavailable: %s", exc)

    def start_ws_server(self) -> None:
        if self._server_thread and self._server_thread.is_alive():
            return
        self._server_thread = threading.Thread(
            target=lambda: asyncio.run(self._run_server()),
            name="terminal-ws-server",
            daemon=True,
        )
        self._server_thread.start()

    async def _run_server(self) -> None:
        try:
            import websockets
            from websockets.server import serve
        except ImportError:
            logger.warning("websockets not installed — client WS server disabled")
            return

        self._loop = asyncio.get_running_loop()

        async def handler(ws):  # noqa: ANN001
            queue = self.subscribe_queue()
            try:
                hello = {
                    "type": "hello",
                    "channels": ["orderbook", "trade"],
                    "snapshot": self.snapshot_recent(30),
                }
                await ws.send(json.dumps(hello, ensure_ascii=False))
                while True:
                    event = await queue.get()
                    msg = json.dumps(
                        {
                            "type": "event",
                            "channel": event.channel,
                            "symbol": event.symbol,
                            "payload": event.payload,
                            "ts": event.ts,
                        },
                        ensure_ascii=False,
                    )
                    await ws.send(msg)
            except Exception:
                pass
            finally:
                self.unsubscribe_queue(queue)

        async with serve(handler, "0.0.0.0", self._ws_port, ping_interval=20):
            logger.info("Terminal WS listening on 0.0.0.0:%s", self._ws_port)
            await asyncio.Future()

    def bootstrap_default_streams(self) -> None:
        for symbol in _DEFAULT_SYMBOLS:
            try:
                self.ensure_orderbook_mirror(symbol)
            except Exception:
                pass
        try:
            self.start_ws_server()
        except Exception as exc:  # noqa: BLE001
            logger.warning("WS server start failed: %s", exc)


_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    global _manager
    if _manager is None:
        _manager = StreamManager()
    return _manager
