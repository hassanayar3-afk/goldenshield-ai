"""Async-friendly HTF cache — تحديث 1h/4h عند إغلاق الشمعة (REST خفيف)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from data.ohlcv_fetcher import OHLCVFetcher

logger = logging.getLogger(__name__)


@dataclass
class HTFCandleCache:
    _fetcher: OHLCVFetcher = field(default_factory=OHLCVFetcher)
    _last_refresh: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _ttl_sec: float = 3600.0

    def touch(self, symbol: str) -> None:
        now = time.monotonic()
        with self._lock:
            last = self._last_refresh.get(symbol, 0.0)
            if now - last < self._ttl_sec:
                return
        try:
            self._fetcher.fetch(symbol, "1h", limit=5)
            self._fetcher.fetch(symbol, "4h", limit=5)
            with self._lock:
                self._last_refresh[symbol] = now
        except Exception as exc:  # noqa: BLE001
            logger.debug("HTF cache %s: %s", symbol, exc)
