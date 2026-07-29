from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from data.models.candle import Candle
from data.volume_profile import calculate_volume_profile, point_of_control


class VolumeBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class VolumeAnalysis:
    bias: VolumeBias
    poc_price: float | None
    poc_volume: float | None
    price_near_poc: bool
    high_volume_zone: bool


def analyze_volume(candles: list[Candle], *, num_bins: int = 20) -> VolumeAnalysis:
    if len(candles) < 5:
        return VolumeAnalysis(
            bias=VolumeBias.NEUTRAL,
            poc_price=None,
            poc_volume=None,
            price_near_poc=False,
            high_volume_zone=False,
        )

    profile = calculate_volume_profile(candles, num_bins=num_bins)
    poc = point_of_control(profile)
    last_close = candles[-1].close

    if poc is None:
        return VolumeAnalysis(
            bias=VolumeBias.NEUTRAL,
            poc_price=None,
            poc_volume=None,
            price_near_poc=False,
            high_volume_zone=False,
        )

    poc_price, poc_volume = poc
    distance_pct = abs(last_close - poc_price) / poc_price * 100 if poc_price else 100
    price_near_poc = distance_pct <= 1.0

    if last_close > poc_price:
        bias = VolumeBias.BULLISH
    elif last_close < poc_price:
        bias = VolumeBias.BEARISH
    else:
        bias = VolumeBias.NEUTRAL

    return VolumeAnalysis(
        bias=bias,
        poc_price=poc_price,
        poc_volume=poc_volume,
        price_near_poc=price_near_poc,
        high_volume_zone=poc_volume > 0,
    )
