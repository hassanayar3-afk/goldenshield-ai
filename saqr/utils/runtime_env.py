"""
Approved Saqr .env accessors — single source for port, intervals, paths, and flags.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_PROJECT_ROOT: Optional[Path] = None


def _norm_path(p: Path) -> str:
    try:
        return os.path.normcase(str(p.resolve()))
    except OSError:
        return os.path.normcase(str(p))


def set_project_root(root: Path) -> Path:
    """Canonical Saqr install directory (folder containing gateway/, engines/, .env)."""
    global _PROJECT_ROOT
    resolved = root.resolve()
    _PROJECT_ROOT = resolved
    os.environ["SAqr_ROOT"] = str(resolved)
    return resolved


def get_project_root() -> Path:
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT
    env_root = os.getenv("SAqr_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd()


def bootstrap_environment(project_root: Path) -> Path:
    """
    Load .env from the runtime project folder only.
    SAqr_ROOT always matches the folder you actually run from (no second-path override).
    Pre-set environment variables (e.g. from run_saqr_local.bat) win over .env file values.
    """
    from dotenv import load_dotenv

    root = set_project_root(project_root)
    env_file = root / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)
    set_project_root(root)

    configured = os.getenv("SAqr_ROOT", "")
    if configured and _norm_path(Path(configured)) != _norm_path(root):
        # .env may say C:\\Saqr_Binance while you run from another copy — runtime root wins.
        set_project_root(root)

    return root


def resolve_project_path(relative_or_absolute: str) -> Path:
    """Resolve DB_PATH and similar entries relative to SAqr_ROOT."""
    p = Path(relative_or_absolute)
    if p.is_absolute():
        return p
    return (get_project_root() / p).resolve()


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


def tri_commander_enabled(default: bool = True) -> bool:
    return env_bool("TRI_COMMANDER_MODE", default)


def bot_force_active(default: bool = True) -> bool:
    return env_bool("BOT_FORCE_ACTIVE", default)


def no_sleep_mode(default: bool = True) -> bool:
    return env_bool("NO_SLEEP_MODE", default)


def demo_entry_relax(default: bool = False) -> bool:
    """
    When true: lower effective elite threshold, warm klines, optional demo seeds.
    Enable via SAQR_DEMO_ENTRY_RELAX=true for local paper validation.
    """
    return env_bool("SAQR_DEMO_ENTRY_RELAX", default) or env_bool("BOT_DEMO_ENTRY_MODE", False)


def demo_seed_trades(default: int = 0) -> int:
    try:
        return int(os.getenv("SAQR_DEMO_SEED_TRADES", str(default)))
    except ValueError:
        return default
