"""مرآة WebSocket لدفتر الأوامر — fallback REST عند غياب websockets."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _BookState:
    bid_qty: float = 0.0
    ask_qty: float = 0.0
    updated_at: float = 0.0


class OrderBookMirror:
    def __init__(self) -> None:
        self._books: dict[str, _BookState] = {}
        self._lock = threading.Lock()
        self._streams_started: set[str] = set()

    def ensure_stream(self, symbol: str) -> None:
        with self._lock:
            if symbol in self._streams_started:
                return
            self._streams_started.add(symbol)
        try:
            import asyncio

            threading.Thread(
                target=lambda: asyncio.run(self._run_ws(symbol)),
                name=f"ws-book-{symbol}",
                daemon=True,
            ).start()
        except Exception:
            self._refresh_rest(symbol)

    async def _run_ws(self, symbol: str) -> None:
        try:
            import websockets
        except ImportError:
            self._refresh_rest(symbol)
            return
        stream = symbol.replace("/", "").lower() + "@depth5@100ms"
        url = f"wss://stream.binance.com:9443/ws/{stream}"
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                while True:
                    msg = await ws.recv()
                    self._parse_depth(symbol, msg)
        except Exception as exc:  # noqa: BLE001
            logger.debug("WS book %s: %s — REST fallback", symbol, exc)
            self._refresh_rest(symbol)

    def _parse_depth(self, symbol: str, raw: str) -> None:
        try:
            import json

            data = json.loads(raw)
            bids = data.get("bids") or data.get("b") or []
            asks = data.get("asks") or data.get("a") or []
            bid_qty = sum(float(b[1]) for b in bids[:5]) if bids else 0.0
            ask_qty = sum(float(a[1]) for a in asks[:5]) if asks else 0.0
            with self._lock:
                self._books[symbol] = _BookState(bid_qty, ask_qty, time.monotonic())
        except Exception:
            pass

    def _refresh_rest(self, symbol: str) -> None:
        try:
            from data.orderbook_fetcher import OrderBookFetcher

            book = OrderBookFetcher().fetch(symbol)
            bid_qty = sum(lvl.amount for lvl in book.bids[:5])
            ask_qty = sum(lvl.amount for lvl in book.asks[:5])
            with self._lock:
                self._books[symbol] = _BookState(bid_qty, ask_qty, time.monotonic())
        except Exception as exc:  # noqa: BLE001
            logger.debug("REST book %s: %s", symbol, exc)

    def snapshot(self, symbol: str) -> dict[str, float] | None:
        with self._lock:
            state = self._books.get(symbol)
        if state is None or state.bid_qty + state.ask_qty <= 0:
            self._refresh_rest(symbol)
            with self._lock:
                state = self._books.get(symbol)
        if state is None:
            return None
        total = state.bid_qty + state.ask_qty
        imbalance = (state.bid_qty - state.ask_qty) / total if total > 0 else 0.0
        return {
            "bid_qty": state.bid_qty,
            "ask_qty": state.ask_qty,
            "imbalance": imbalance,
            "updated_at": state.updated_at,
        }

    def imbalance(self, symbol: str) -> float | None:
        with self._lock:
            st = self._books.get(symbol)
        if st is None or st.bid_qty + st.ask_qty <= 0:
            self._refresh_rest(symbol)
            with self._lock:
                st = self._books.get(symbol)
        if st is None or st.bid_qty + st.ask_qty <= 0:
            return None
        return (st.bid_qty - st.ask_qty) / (st.bid_qty + st.ask_qty)


_mirror: OrderBookMirror | None = None


def get_orderbook_mirror() -> OrderBookMirror:
    global _mirror
    if _mirror is None:
        _mirror = OrderBookMirror()
    return _mirror
