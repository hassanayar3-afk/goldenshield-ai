"""
Approved Saqr .env accessors — single source for port, intervals, and flags.
"""

from __future__ import annotations

import os


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


def service_port(default: int = 8000) -> int:
    for key in ("MOBILE_API_PORT", "TERMINAL_WS_PORT", "PORT"):
        raw = os.getenv(key)
        if raw:
            try:
                return int(raw)
            except ValueError:
                continue
    return default


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
