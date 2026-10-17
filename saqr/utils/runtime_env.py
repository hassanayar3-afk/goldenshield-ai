"""
Approved Saqr .env accessors — single source for port, intervals, and flags.
"""

from __future__ import annotations

import os
from typing import Optional


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def loop_interval_seconds(default: float = 4.0) -> float:
    try:
        return float(os.getenv("LOOP_INTERVAL_SECONDS", str(default)))
    except ValueError:
        return default


def _read_port(key: str) -> Optional[int]:
    raw = os.getenv(key)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def service_port(default: int = 8000) -> int:
    """
    Single HTTP + WebSocket port. MOBILE_API_PORT is canonical when set.
    TERMINAL_WS_PORT must match (same uvicorn process serves /ws).
    """
    mobile = _read_port("MOBILE_API_PORT")
    terminal = _read_port("TERMINAL_WS_PORT")
    generic = _read_port("PORT")

    if mobile is not None and terminal is not None and mobile != terminal:
        raise ValueError(
            f"MOBILE_API_PORT ({mobile}) must equal TERMINAL_WS_PORT ({terminal}) — "
            "one gateway serves both HTTP and /ws"
        )

    for candidate in (mobile, terminal, generic):
        if candidate is not None:
            return candidate
    return default


def bind_host(default_local: str = "127.0.0.1", default_lan: str = "0.0.0.0") -> str:
    """Listen on all interfaces when MOBILE_WEB_DIRECT_ACCESS is enabled."""
    if env_bool("MOBILE_WEB_DIRECT_ACCESS", False):
        return default_lan
    return default_local


def recovery_stop_fraction(default: float = 0.015) -> float:
    """
    RECOVERY_STOP_PCT=1.5 means 1.5% (legacy env used 0.015 as fraction).
    Values >= 1 are treated as percent points.
    """
    try:
        raw = float(os.getenv("RECOVERY_STOP_PCT", str(default * 100)))
    except ValueError:
        return default
    if raw >= 1:
        return raw / 100.0
    return raw


def portfolio_heat_cap_fraction(default: float = 0.07) -> float:
    try:
        return float(os.getenv("PORTFOLIO_HEAT_CAP_PCT", str(default)))
    except ValueError:
        return default


def stop_market_enabled() -> bool:
    if env_bool("PAPER_TRADING", True):
        return True
    mode = os.getenv("EXECUTION_MODE", "paper").strip().lower()
    return mode in ("paper", "live", "demo")


def watchdog_enabled(default: bool = True) -> bool:
    return env_bool("WATCHDOG_ENABLED", default)
