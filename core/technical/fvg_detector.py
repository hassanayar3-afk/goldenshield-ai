from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from data.models.candle import Candle


class FVGType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass(frozen=True)
class FairValueGap:
    gap_type: FVGType
    top: float
    bottom: float
    candle_index: int


@dataclass(frozen=True)
class FVGResult:
    gaps: tuple[FairValueGap, ...]
    has_active_gap: bool
    nearest_gap: FairValueGap | None


def detect_fvg(candles: list[Candle], *, lookback: int = 20) -> FVGResult:
    gaps: list[FairValueGap] = []
    start_index = max(2, len(candles) - lookback)

    for index in range(start_index, len(candles)):
        left = candles[index - 2]
        right = candles[index]

        if left.high < right.low:
            gaps.append(
                FairValueGap(
                    gap_type=FVGType.BULLISH,
                    top=right.low,
                    bottom=left.high,
                    candle_index=index,
                )
            )
        elif left.low > right.high:
            gaps.append(
                FairValueGap(
                    gap_type=FVGType.BEARISH,
                    top=left.low,
                    bottom=right.high,
                    candle_index=index,
                )
            )

    nearest = gaps[-1] if gaps else None
    return FVGResult(
        gaps=tuple(gaps),
        has_active_gap=bool(gaps),
        nearest_gap=nearest,
    )
