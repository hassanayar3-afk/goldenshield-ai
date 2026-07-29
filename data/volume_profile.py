from __future__ import annotations

from data.models.candle import Candle


def calculate_volume_profile(
    candles: list[Candle],
    *,
    num_bins: int = 20,
) -> list[tuple[float, float]]:
    """
    حساب Volume Profile — توزيع الحجم على مستويات السعر.

    يُرجع قائمة من (mid_price, volume) مرتبة تصاعدياً.
    """
    if not candles:
        return []

    if num_bins < 1:
        raise ValueError("num_bins يجب أن يكون >= 1")

    price_low = min(candle.low for candle in candles)
    price_high = max(candle.high for candle in candles)

    if price_high == price_low:
        total_volume = sum(candle.volume for candle in candles)
        return [(price_low, total_volume)]

    bin_size = (price_high - price_low) / num_bins
    bins = [0.0] * num_bins

    for candle in candles:
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            bin_index = min(
                num_bins - 1,
                max(0, int((candle.close - price_low) / bin_size)),
            )
            bins[bin_index] += candle.volume
            continue

        start_bin = max(0, int((candle.low - price_low) / bin_size))
        end_bin = min(num_bins - 1, int((candle.high - price_low) / bin_size))
        covered_bins = end_bin - start_bin + 1
        volume_per_bin = candle.volume / covered_bins

        for bin_index in range(start_bin, end_bin + 1):
            bins[bin_index] += volume_per_bin

    profile: list[tuple[float, float]] = []
    for index, volume in enumerate(bins):
        if volume <= 0:
            continue
        mid_price = price_low + (index + 0.5) * bin_size
        profile.append((round(mid_price, 8), round(volume, 8)))

    return profile


def point_of_control(profile: list[tuple[float, float]]) -> tuple[float, float] | None:
    """أعلى مستوى حجم — Point of Control."""
    if not profile:
        return None
    return max(profile, key=lambda item: item[1])
