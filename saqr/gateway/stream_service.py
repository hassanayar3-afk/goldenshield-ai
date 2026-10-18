"""
Live Binance kline + bookTicker WebSocket engine (public market data).
Works with PAPER_TRADING=True: real candles, no signed order traffic.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

import websockets
from websockets.exceptions import ConnectionClosed

from utils.crash_wrapper import crash_proof, touch_event_loop_heartbeat
from utils.logger_config import setup_logger

logger = setup_logger("saqr.stream")

KlineKey = Tuple[str, str]


@dataclass
class KlineSeries:
    closes: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    highs: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    lows: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    last_event: Optional[Dict[str, Any]] = None


@dataclass
class StreamService:
    hub: Any
    symbols: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in os.getenv(
                "STREAM_SYMBOLS",
                "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT",
            ).split(",")
            if s.strip()
        ]
    )
    intervals: List[str] = field(
        default_factory=lambda: [
            i.strip()
            for i in os.getenv("STREAM_INTERVALS", "1m,5m,1h,4h").split(",")
            if i.strip()
        ]
    )
    _series: Dict[KlineKey, KlineSeries] = field(default_factory=dict)
    _books: Dict[str, Dict[str, float]] = field(default_factory=dict)
    _running: bool = False
    _ws: Any = field(default=None, init=False, repr=False)
    max_retries: int = 8
    base_backoff: float = 0.5

    def _ws_base(self) -> str:
        raw = os.getenv("BINANCE_MARKET_WS_URL", "wss://stream.binance.com:9443").rstrip("/")
        # Combined stream URL is {host}/stream?streams=... (not .../ws/stream)
        if raw.endswith("/ws"):
            return raw[:-3].rstrip("/")
        return raw

    def _series_for(self, symbol: str, interval: str) -> KlineSeries:
        key = (symbol.upper(), interval)
        if key not in self._series:
            self._series[key] = KlineSeries()
        return self._series[key]

    def get_closes(self, symbol: str, interval: str, limit: int = 100) -> List[float]:
        series = self._series_for(symbol, interval)
        data = list(series.closes)
        return data[-limit:]

    def get_last_close(self, symbol: str, interval: str) -> Optional[float]:
        series = self._series_for(symbol, interval)
        if series.closes:
            return series.closes[-1]
        ev = series.last_event
        if ev and ev.get("close"):
            try:
                return float(ev["close"])
            except (TypeError, ValueError):
                pass
        return None

    def get_spread_bps(self, symbol: str) -> Optional[float]:
        book = self._books.get(symbol.upper())
        if not book:
            return None
        bid = book.get("bid", 0.0)
        ask = book.get("ask", 0.0)
        if bid <= 0 or ask <= 0:
            return None
        mid = (bid + ask) / 2.0
        return ((ask - bid) / mid) * 10_000.0

    async def warm_start(self, client: Any) -> None:
        """Seed klines + bookTicker so engines are not stuck FLAT/NEUTRAL on cold start."""
        for symbol in self.symbols:
            sym = symbol.upper()
            try:
                book = await client.fetch_book_ticker(sym)
                if book.get("bid", 0) > 0 and book.get("ask", 0) > 0:
                    self._books[sym] = {
                        "bid": book["bid"],
                        "ask": book["ask"],
                        "ts": time.time(),
                    }
            except Exception as exc:
                logger.warning("warm bookTicker %s: %s", sym, exc)

            for interval in self.intervals:
                try:
                    rows = await client.fetch_klines(sym, interval, limit=200)
                    series = self._series_for(sym, interval)
                    for row in rows:
                        if len(row) < 5:
                            continue
                        c = float(row[4])
                        h = float(row[2])
                        l = float(row[3])
                        series.closes.append(c)
                        series.highs.append(h)
                        series.lows.append(l)
                    if series.closes:
                        series.last_event = {
                            "symbol": sym,
                            "interval": interval,
                            "close": series.closes[-1],
                            "closed": True,
                            "event_time": time.time(),
                        }
                except Exception as exc:
                    logger.warning("warm klines %s %s: %s", sym, interval, exc)
        logger.info("Stream warm_start complete (books=%s)", len(self._books))

    def build_combined_stream_url(self) -> str:
        parts: List[str] = []
        for symbol in self.symbols:
            sym = symbol.lower()
            for interval in self.intervals:
                parts.append(f"{sym}@kline_{interval}")
            parts.append(f"{sym}@bookTicker")
        streams = "/".join(parts)
        return f"{self._ws_base()}/stream?streams={streams}"

    async def _backoff_sleep(self, attempt: int) -> None:
        jitter = random.uniform(0, self.base_backoff)
        delay = self.base_backoff * (2**attempt) + jitter
        await asyncio.sleep(min(delay, 30.0))

    @crash_proof(component="stream_service", restart_delay=2.0)
    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            touch_event_loop_heartbeat()
            try:
                await self._consume_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Stream session ended: %s", exc)
            if not self._running:
                break
            await self._backoff_sleep(0)

    async def _consume_once(self) -> None:
        url = self.build_combined_stream_url()
        logger.info("Connecting kline stream (%s symbols)", len(self.symbols))
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            self._ws = ws
            await self.hub.publish({"type": "stream", "status": "connected", "url": self._ws_base()})
            while self._running:
                touch_event_loop_heartbeat()
                raw = await ws.recv()
                await self._dispatch(raw)

    async def _dispatch(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return

        data = payload.get("data", payload)
        event = data.get("e")
        if event == "bookTicker":
            symbol = str(data.get("s", "")).upper()
            bid = float(data.get("b", 0))
            ask = float(data.get("a", 0))
            self._books[symbol] = {"bid": bid, "ask": ask, "ts": time.time()}
            return

        if event != "kline":
            return

        k = data.get("k") or {}
        symbol = str(k.get("s", "")).upper()
        interval = str(k.get("i", ""))
        if not symbol or not interval:
            return

        close = float(k.get("c", 0))
        high = float(k.get("h", 0))
        low = float(k.get("l", 0))
        closed = bool(k.get("x", False))

        series = self._series_for(symbol, interval)
        if close > 0:
            series.last_event = {
                "symbol": symbol,
                "interval": interval,
                "close": close,
                "closed": closed,
                "event_time": data.get("E"),
            }
        if closed:
            series.closes.append(close)
            series.highs.append(high)
            series.lows.append(low)

        if closed:
            await self.hub.publish(
                {
                    "type": "kline",
                    "symbol": symbol,
                    "interval": interval,
                    "close": close,
                    "closed": True,
                }
            )

    def stop(self) -> None:
        self._running = False

    def snapshot(self) -> Dict[str, Any]:
        keys = [f"{s}:{i}" for s, i in self._series.keys()]
        return {
            "series": len(keys),
            "books": len(self._books),
            "symbols": self.symbols,
            "intervals": self.intervals,
        }
