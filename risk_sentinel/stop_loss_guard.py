"""Stop-loss / protection order guards (additive layer on engines)."""

from __future__ import annotations

import os
from typing import Optional, Tuple

from data_highway.logging_config import setup_logger
from data_highway.runtime_env import recovery_stop_fraction, stop_market_enabled

logger = setup_logger("saqr.stop_loss")


def stop_market_allowed() -> bool:
    return stop_market_enabled()


def compute_stop_price(
    entry: float,
    side: str,
    *,
    stop_fraction: Optional[float] = None,
) -> Tuple[float, str]:
    frac = stop_fraction if stop_fraction is not None else recovery_stop_fraction()
    side_u = side.upper()
    if side_u == "BUY":
        return entry * (1.0 - frac), "SELL"
    return entry * (1.0 + frac), "BUY"


def validate_stop_distance(entry: float, stop: float, side: str) -> bool:
    try:
        min_bps = float(os.getenv("MIN_STOP_DISTANCE_BPS", "5"))
    except ValueError:
        min_bps = 5.0
    if entry <= 0:
        return False
    dist_bps = abs(entry - stop) / entry * 10_000.0
    ok = dist_bps >= min_bps
    if not ok:
        logger.info("Stop too tight bps=%.2f min=%.2f side=%s", dist_bps, min_bps, side)
    return ok
