from __future__ import annotations

import time

from core.constants import HEARTBEAT_TIMEOUT_SECONDS
from data.connection_utils import ping_exchange


class ConnectionMonitor:
    """مراقبة Heartbeat — حسب الخلفية النشطة (MT5 أو Binance)."""

    def __init__(self, timeout_seconds: int = HEARTBEAT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds
        self._last_success_monotonic: float | None = None
        self._last_error: str | None = None
        self._last_provider: str | None = None
        self._ever_succeeded = False

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_provider(self) -> str | None:
        return self._last_provider

    def record_success(self) -> None:
        self._last_success_monotonic = time.monotonic()
        self._last_error = None
        self._ever_succeeded = True

    def record_failure(self, error: str) -> None:
        self._last_error = error

    def seconds_since_last_success(self) -> float | None:
        if self._last_success_monotonic is None:
            return None
        return time.monotonic() - self._last_success_monotonic

    def is_connected(self) -> bool:
        if not self._ever_succeeded and self._last_error:
            return False
        elapsed = self.seconds_since_last_success()
        if elapsed is None:
            return True
        return elapsed <= self._timeout_seconds

    def is_disconnected(self) -> bool:
        return not self.is_connected()

    def heartbeat_binance(self) -> bool:
        self._last_provider = "binance"
        try:
            ping_exchange()
            self.record_success()
            return True
        except Exception as exc:
            self.record_failure(str(exc))
            return False

    def heartbeat_mt5(self) -> bool:
        self._last_provider = "mt5"
        try:
            from execution.mt5_bridge import get_mt5_bridge

            mt5 = get_mt5_bridge().ensure_connected()
            info = mt5.account_info()
            if info is None:
                raise RuntimeError(f"account_info فارغ: {mt5.last_error()}")
            self.record_success()
            return True
        except Exception as exc:
            self.record_failure(str(exc))
            return False

    def heartbeat(self) -> bool:
        """فحص اتصال الخلفية النشطة — لا يوقف MT5 بسبب Binance."""
        try:
            from config.runtime_profile import get_runtime_profile

            profile = get_runtime_profile()
            if profile.heartbeat_provider == "mt5":
                return self.heartbeat_mt5()
        except Exception:
            pass
        return self.heartbeat_binance()
