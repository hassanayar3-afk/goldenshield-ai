"""Portfolio heat, correlation, circuit breakers (additive guards)."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def portfolio_heat_cap_pct() -> float:
    try:
        return float(os.getenv("PORTFOLIO_HEAT_CAP_PCT", "0.07") or 0.07)
    except Exception:
        return 0.07


def correlation_block_threshold() -> float:
    try:
        return float(os.getenv("GS_CORRELATION_BLOCK_PCT", "0.75") or 0.75)
    except Exception:
        return 0.75


def elite_min_score() -> float:
    try:
        return float(os.getenv("ELITE_MIN_PERCENT", "85") or 85)
    except Exception:
        return 85.0


def allow_proposal(score_percent: float, open_heat: float, correlation: float) -> tuple[bool, str]:
    if score_percent < elite_min_score():
        return False, "elite_score_below_min"
    if open_heat > portfolio_heat_cap_pct():
        return False, "portfolio_heat_cap"
    if correlation > correlation_block_threshold():
        return False, "correlation_matrix_block"
    return True, "ok"


def notify_discord_emergency(message: str) -> None:
    try:
        import os
        import requests

        url = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
        if not url:
            return
        requests.post(url, json={"content": f"[GS Neural] {message[:1800]}"}, timeout=8)
    except Exception as exc:
        logger.debug("discord emergency skip: %s", exc)


def wrap_crash_proof(func: Any) -> Any:
    """Decorator for non-fatal engine errors."""

    async def _inner(*args: object, **kwargs: object) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            logger.exception("sovereign_guard caught: %s", exc)
            notify_discord_emergency(str(exc))
            return None

    return _inner
