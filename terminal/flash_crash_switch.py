"""صمام Flash Crash — BTC -1.5% في دقيقة → تجميد دخول."""

from __future__ import annotations

import os
from dataclasses import dataclass

from data.ticker_fetcher import TickerFetcher

_BTC = "BTC/USDT"


@dataclass(frozen=True)
class FlashCrashDecision:
    block_entries: bool
    reason: str


def evaluate_btc_flash_crash(*, drop_pct: float | None = None) -> FlashCrashDecision:
    try:
        threshold = float(os.getenv("FLASH_CRASH_BTC_1M_PCT", "1.5") or 1.5)
    except (TypeError, ValueError):
        threshold = 1.5
    try:
        fetcher = TickerFetcher()
        candles_mod = __import__("data.ohlcv_fetcher", fromlist=["OHLCVFetcher"])
        ohlcv = candles_mod.OHLCVFetcher()
        rows = ohlcv.fetch(_BTC, "1m", limit=2)
        if len(rows) < 2:
            return FlashCrashDecision(False, "BTC 1m غير كافٍ")
        prev, last = float(rows[-2].close), float(rows[-1].close)
        if prev <= 0:
            return FlashCrashDecision(False, "BTC price invalid")
        move_pct = (last - prev) / prev * 100.0
        if move_pct <= -abs(threshold):
            return FlashCrashDecision(
                True,
                f"Flash Crash Switch: BTC {move_pct:.2f}% في 1m",
            )
        return FlashCrashDecision(False, f"BTC 1m {move_pct:+.2f}%")
    except Exception as exc:  # noqa: BLE001
        return FlashCrashDecision(False, f"flash crash check skip: {exc}")
