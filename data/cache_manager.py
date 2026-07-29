from __future__ import annotations

import time
from threading import Lock
from typing import Any

from config.settings import get_settings
from data.exchange_client import get_exchange


class CacheManager:
    """تخزين مؤقت بسيط بـ TTL لتقليل استدعاءات API."""

    def __init__(self, default_ttl_seconds: int = 30) -> None:
        self._default_ttl = default_ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None

            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._entries[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._entries[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)


_default_cache: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    global _default_cache
    if _default_cache is None:
        settings = get_settings()
        ttl = 15 if settings.env == "dev" else 30
        _default_cache = CacheManager(default_ttl_seconds=ttl)
    return _default_cache


def reset_cache_manager() -> None:
    global _default_cache
    _default_cache = None
