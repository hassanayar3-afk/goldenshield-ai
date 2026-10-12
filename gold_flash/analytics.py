"""تحليل Z-Score / Mean Reversion + Micro POC — بدون تلوث SMC."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class FlashSignal:
    side: str  # buy | sell
    z_score: float
    micro_poc: float
    reason: str


def _mean_std(values: deque[float]) -> tuple[float, float]:
    if len(values) < 5:
        return 0.0, 0.0
    data = list(values)
    mu = sum(data) / len(data)
    var = sum((x - mu) ** 2 for x in data) / max(len(data) - 1, 1)
    return mu, math.sqrt(max(var, 1e-12))


def evaluate_flash_analytics(
    closes: deque[float],
    *,
    z_entry: float = 2.0,
) -> FlashSignal | None:
    if len(closes) < 10:
        return None
    mu, sigma = _mean_std(closes)
    last = closes[-1]
    if sigma <= 0:
        return None
    z = (last - mu) / sigma
    poc = mu
    if z <= -z_entry:
        return FlashSignal("buy", z, poc, f"Z-Score {z:.2f} oversold → mean revert")
    if z >= z_entry:
        return FlashSignal("sell", z, poc, f"Z-Score {z:.2f} overbought → mean revert")
    return None
