from __future__ import annotations

from dataclasses import dataclass

from core.constants import MAX_SPREAD_PCT
from data.models.ticker import Ticker


@dataclass(frozen=True)
class SpreadFilterResult:
    passed: bool
    spread_pct: float | None
    reason: str


def check_spread(ticker: Ticker, *, max_spread_pct: float = MAX_SPREAD_PCT) -> SpreadFilterResult:
    if ticker.spread_pct is None:
        return SpreadFilterResult(
            passed=True,
            spread_pct=None,
            reason="لا تتوفر بيانات السبريد — تمرير افتراضي",
        )

    if ticker.spread_pct <= max_spread_pct:
        return SpreadFilterResult(
            passed=True,
            spread_pct=ticker.spread_pct,
            reason="السبريد ضمن الحد المسموح",
        )

    return SpreadFilterResult(
        passed=False,
        spread_pct=ticker.spread_pct,
        reason=f"السبريد مرتفع: {ticker.spread_pct:.4f}% > {max_spread_pct}%",
    )
