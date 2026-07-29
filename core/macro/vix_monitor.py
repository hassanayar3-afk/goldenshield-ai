from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from config.settings import get_settings


@dataclass(frozen=True)
class VIXResult:
    value: float | None
    is_elevated: bool
    is_safe: bool
    reason: str


def check_vix() -> VIXResult:
    settings = get_settings()

    try:
        ticker = yf.Ticker("^VIX")
        history = ticker.history(period="2d")
        if history.empty:
            raise ValueError("لا بيانات VIX")

        value = float(history["Close"].iloc[-1])
    except Exception as exc:
        return VIXResult(
            value=None,
            is_elevated=False,
            is_safe=True,
            reason=f"تعذر قراءة VIX — تمرير افتراضي: {exc}",
        )

    is_elevated = value >= settings.vix_threshold
    return VIXResult(
        value=value,
        is_elevated=is_elevated,
        is_safe=not is_elevated,
        reason=(
            f"VIX={value:.2f} مرتفع"
            if is_elevated
            else f"VIX={value:.2f} ضمن الحدود"
        ),
    )
