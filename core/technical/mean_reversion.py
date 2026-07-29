from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.constants import RSI_PERIOD, SMA_PERIOD
from core.technical.indicators import closes, rsi, sma
from data.models.candle import Candle


class ReversionSignal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    NONE = "none"


@dataclass(frozen=True)
class MeanReversionResult:
    signal: ReversionSignal
    rsi_value: float | None
    sma_value: float | None
    deviation_pct: float | None
    is_setup: bool


def analyze_mean_reversion(candles: list[Candle]) -> MeanReversionResult:
    close_values = closes(candles)
    if len(close_values) < SMA_PERIOD:
        return MeanReversionResult(
            signal=ReversionSignal.NONE,
            rsi_value=None,
            sma_value=None,
            deviation_pct=None,
            is_setup=False,
        )

    rsi_value = rsi(close_values, RSI_PERIOD)
    sma_value = sma(close_values, SMA_PERIOD)
    last_close = close_values[-1]

    deviation_pct = None
    if sma_value:
        deviation_pct = ((last_close - sma_value) / sma_value) * 100

    signal = ReversionSignal.NONE
    is_setup = False

    if rsi_value is not None and sma_value is not None:
        if rsi_value <= 35 and last_close < sma_value:
            signal = ReversionSignal.BUY
            is_setup = True
        elif rsi_value >= 65 and last_close > sma_value:
            signal = ReversionSignal.SELL
            is_setup = True

    return MeanReversionResult(
        signal=signal,
        rsi_value=rsi_value,
        sma_value=sma_value,
        deviation_pct=deviation_pct,
        is_setup=is_setup,
    )
