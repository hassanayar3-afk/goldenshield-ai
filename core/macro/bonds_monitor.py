from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from config.settings import get_settings


@dataclass(frozen=True)
class BondsResult:
    yield_pct: float | None
    daily_change_pct: float | None
    is_stressed: bool
    is_safe: bool
    reason: str


def check_bonds() -> BondsResult:
    settings = get_settings()

    try:
        ticker = yf.Ticker("^TNX")
        history = ticker.history(period="5d")
        if history.empty or len(history) < 2:
            raise ValueError("لا بيانات سندات")

        yield_pct = float(history["Close"].iloc[-1])
        previous = float(history["Close"].iloc[-2])
        daily_change_pct = ((yield_pct - previous) / previous) * 100 if previous else 0.0
    except Exception as exc:
        return BondsResult(
            yield_pct=None,
            daily_change_pct=None,
            is_stressed=False,
            is_safe=True,
            reason=f"تعذر قراءة السندات — تمرير افتراضي: {exc}",
        )

    is_stressed = abs(daily_change_pct) >= settings.bonds_yield_spike_pct
    return BondsResult(
        yield_pct=yield_pct,
        daily_change_pct=daily_change_pct,
        is_stressed=is_stressed,
        is_safe=not is_stressed,
        reason=(
            f"تقلب سندات {daily_change_pct:+.2f}%"
            if is_stressed
            else f"السندات مستقرة ({daily_change_pct:+.2f}%)"
        ),
    )
