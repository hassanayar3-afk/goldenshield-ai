"""
Pre-trade spread + short-term volatility guard (additive layer on binance_client.validate_order).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Tuple

from utils.logger_config import setup_logger

if TYPE_CHECKING:
    from gateway.binance_client import BinanceClient
    from gateway.stream_service import StreamService

logger = setup_logger("saqr.spread_guard")


def max_spread_bps() -> float:
    try:
        return float(os.getenv("MAX_SPREAD_BPS", "15"))
    except ValueError:
        return 15.0


def max_volatility_bps() -> float:
    """Reject if recent 1m range vs mid exceeds this ( sudden expansion )."""
    try:
        return float(os.getenv("VOLATILITY_MAX_BPS", "120"))
    except ValueError:
        return 120.0


def _range_bps(closes: list[float]) -> float:
    if len(closes) < 5:
        return 0.0
    window = closes[-20:]
    lo = min(window)
    hi = max(window)
    mid = (lo + hi) / 2.0
    if mid <= 0:
        return 0.0
    return ((hi - lo) / mid) * 10_000.0


async def advanced_pre_trade_check(
    client: "BinanceClient",
    stream: Optional["StreamService"],
    symbol: str,
    quantity: float,
    reference_price: float,
    *,
    spread_bps_override: Optional[float] = None,
) -> Tuple[bool, str, float]:
    """
    Spread + min notional (via client) + volatility burst check.
    Returns (allowed, reason, adjusted_qty).
    """
    allowed, reason, qty = await client.validate_order(
        symbol,
        quantity,
        reference_price,
        spread_bps_override=spread_bps_override,
    )
    if not allowed:
        logger.info("Pre-trade blocked %s: %s", symbol, reason)
        return False, reason, qty

    spread = spread_bps_override
    if spread is None and stream is not None:
        spread = stream.get_spread_bps(symbol.upper())
    if spread is not None and spread > max_spread_bps():
        reason = f"spread_guard bps={spread:.2f}>{max_spread_bps()}"
        logger.warning("Pre-trade blocked %s: %s", symbol, reason)
        return False, reason, qty

    if stream is not None:
        closes = stream.get_closes(symbol.upper(), "1m", 30)
        vol_bps = _range_bps(closes)
        if vol_bps > max_volatility_bps():
            reason = f"volatility_guard bps={vol_bps:.1f}>{max_volatility_bps()}"
            logger.warning("Pre-trade blocked %s: %s", symbol, reason)
            return False, reason, qty

    return True, "ok", qty
