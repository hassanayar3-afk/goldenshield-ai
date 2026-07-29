"""حدود يومية — عدد الصفقات."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class DailyLimitsResult:
    allowed: bool
    reason: str
    trades_today: int
    max_trades: int


def check_daily_limits(trades_today: int) -> DailyLimitsResult:
    settings = get_settings()
    max_trades = settings.max_daily_trades

    if trades_today >= max_trades:
        return DailyLimitsResult(
            allowed=False,
            reason=f"الحد اليومي للصفقات: {trades_today}/{max_trades}",
            trades_today=trades_today,
            max_trades=max_trades,
        )

    return DailyLimitsResult(
        allowed=True,
        reason=f"صفقات اليوم: {trades_today}/{max_trades}",
        trades_today=trades_today,
        max_trades=max_trades,
    )
