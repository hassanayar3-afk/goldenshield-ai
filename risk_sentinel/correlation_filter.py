"""Optional cross-symbol correlation gate (additive, non-blocking default)."""

from __future__ import annotations

import os
from typing import Tuple

from data_highway.logging_config import setup_logger

logger = setup_logger("saqr.correlation")


def correlation_filter_enabled() -> bool:
    return os.getenv("CORRELATION_FILTER_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def allows_entry(symbol: str, engine: str) -> Tuple[bool, str]:
    if not correlation_filter_enabled():
        return True, "ok"
    try:
        # Placeholder for future BTC/ETH exposure caps
        _ = (symbol, engine)
        return True, "ok"
    except Exception as exc:
        logger.warning("Correlation filter error (allow): %s", exc)
        return True, "ok"
