"""In-memory position/book cache with idempotency keys (no blocking disk on hot path)."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any

_lock = threading.RLock()
_state: dict[str, Any] = {
    "positions": {},
    "book": {},
    "prices": {},
    "idempotency": {},
}
_events: deque[dict[str, Any]] = deque(maxlen=int(os.getenv("GS_MEMORY_DEQUE_MAX", "1000") or 1000))


def remember_idempotent(key: str, ttl_sec: float = 300.0) -> bool:
    """Return True if key is new; False if duplicate within TTL."""
    if not key:
        return True
    now = time.monotonic()
    with _lock:
        exp = _state["idempotency"].get(key)
        if exp and exp > now:
            return False
        _state["idempotency"][key] = now + ttl_sec
        return True


def publish(event: dict[str, Any]) -> None:
    with _lock:
        _events.append(event)


def snapshot() -> dict[str, Any]:
    with _lock:
        return {
            "positions": dict(_state["positions"]),
            "book": dict(_state["book"]),
            "prices": dict(_state["prices"]),
            "events_tail": list(_events)[-20:],
        }


def update_positions(positions: dict[str, Any]) -> None:
    with _lock:
        _state["positions"] = dict(positions)


def update_price(symbol: str, price: float) -> None:
    with _lock:
        _state["prices"][symbol] = price
