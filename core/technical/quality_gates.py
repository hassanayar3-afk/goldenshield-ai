"""بوابات جودة الدخول — تصفية هرمية (Confluence / Re-test / Divergence / Volume)."""

from __future__ import annotations

from dataclasses import dataclass

from core.technical.indicators import closes, rsi
from core.technical.smc_analyzer import MarketStructure, SMCResult
from core.technical.timeframe_aligner import TrendDirection
from core.technical.volume_analyzer import VolumeAnalysis, VolumeBias
from data.models.candle import Candle


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    reason: str


def check_confluence(
    *,
    smc: SMCResult,
    volume: VolumeAnalysis,
    direction: TrendDirection,
) -> QualityGateResult:
    """دمج SMC + Order Block + Volume Profile."""
    structure_ok = False
    if direction == TrendDirection.BULLISH:
        structure_ok = smc.structure in {MarketStructure.BULLISH, MarketStructure.NEUTRAL} and (
            smc.order_block or smc.bos or smc.choch
        )
    elif direction == TrendDirection.BEARISH:
        structure_ok = smc.structure in {MarketStructure.BEARISH, MarketStructure.NEUTRAL} and (
            smc.order_block or smc.bos or smc.choch
        )

    volume_ok = volume.high_volume_zone or volume.price_near_poc
    if direction == TrendDirection.BULLISH and volume.bias == VolumeBias.BEARISH:
        volume_ok = volume_ok and volume.price_near_poc
    if direction == TrendDirection.BEARISH and volume.bias == VolumeBias.BULLISH:
        volume_ok = volume_ok and volume.price_near_poc

    if structure_ok and volume_ok:
        return QualityGateResult(True, "تقاطع مدارسي: SMC + Volume متوافقان")
    if not structure_ok:
        return QualityGateResult(False, "التقاطع المدارسي: لا SMC/OB واضح مع الاتجاه")
    return QualityGateResult(False, "التقاطع المدارسي: Volume Profile لا يدعم الدخول")


def check_retest(
    candles: list[Candle],
    *,
    direction: TrendDirection,
) -> QualityGateResult:
    """منع الدخول عند الملامسة فقط — انتظار شمعة تأكيد داخل/بعد Order Block."""
    if len(candles) < 3:
        return QualityGateResult(False, "Re-test: بيانات غير كافية")

    prev = candles[-2]
    last = candles[-1]
    prev_bearish = prev.close < prev.open
    prev_bullish = prev.close > prev.open
    last_bullish = last.close > last.open
    last_bearish = last.close < last.open

    if direction == TrendDirection.BULLISH:
        # OB هابط سابق + شمعة صاعدة تحترم منطقة الجسم السابق
        in_zone = last.low <= max(prev.open, prev.close) and last.close >= min(prev.open, prev.close)
        if prev_bearish and last_bullish and (in_zone or last.close > prev.close):
            return QualityGateResult(True, "Re-test: تأكيد صاعد داخل/فوق منطقة OB")
        return QualityGateResult(False, "Re-test: لا شمعة تأكيد صاعدة بعد OB")

    if direction == TrendDirection.BEARISH:
        in_zone = last.high >= min(prev.open, prev.close) and last.close <= max(prev.open, prev.close)
        if prev_bullish and last_bearish and (in_zone or last.close < prev.close):
            return QualityGateResult(True, "Re-test: تأكيد هابط داخل/تحت منطقة OB")
        return QualityGateResult(False, "Re-test: لا شمعة تأكيد هابطة بعد OB")

    return QualityGateResult(False, "Re-test: اتجاه غير واضح")


def check_rsi_divergence(
    candles: list[Candle],
    *,
    direction: TrendDirection,
    period: int = 14,
    lookback: int = 5,
) -> QualityGateResult:
    """منع الدخول عند قمة/قاع سعري جديد بدون دعم RSI."""
    values = closes(candles)
    if len(values) < period + lookback + 2:
        return QualityGateResult(True, "Divergence: بيانات غير كافية — تمرير")

    current_rsi = rsi(values, period)
    prev_rsi = rsi(values[:-1], period)
    if current_rsi is None or prev_rsi is None:
        return QualityGateResult(True, "Divergence: RSI غير متاح — تمرير")

    window = values[-(lookback + 1) :]
    price_now = window[-1]
    price_prev_ext = max(window[:-1]) if direction == TrendDirection.BULLISH else min(window[:-1])

    if direction == TrendDirection.BULLISH:
        # قمة سعرية جديدة مع RSI أضعف → ضعف صعود
        if price_now >= price_prev_ext and current_rsi < prev_rsi:
            return QualityGateResult(
                False,
                f"Divergence: قمة سعرية بدون دعم RSI ({current_rsi:.1f}<{prev_rsi:.1f})",
            )
    elif direction == TrendDirection.BEARISH:
        if price_now <= price_prev_ext and current_rsi > prev_rsi:
            return QualityGateResult(
                False,
                f"Divergence: قاع سعري بدون دعم RSI ({current_rsi:.1f}>{prev_rsi:.1f})",
            )

    return QualityGateResult(True, "Divergence: لا ضعف زخم واضح")


def check_volume_spike(
    candles: list[Candle],
    *,
    lookback: int = 20,
    multiplier: float = 1.5,
) -> QualityGateResult:
    """Volume Spike عند منطقة الدخول."""
    if len(candles) < lookback + 1:
        return QualityGateResult(True, "Volume Spike: بيانات غير كافية — تمرير")

    vols = [c.volume for c in candles[-(lookback + 1) : -1] if c.volume is not None]
    last_vol = candles[-1].volume
    if not vols or last_vol is None or last_vol <= 0:
        return QualityGateResult(True, "Volume Spike: لا بيانات حجم — تمرير")

    avg = sum(vols) / len(vols)
    if avg <= 0:
        return QualityGateResult(True, "Volume Spike: متوسط الحجم صفر — تمرير")

    if last_vol >= avg * multiplier:
        return QualityGateResult(
            True,
            f"Volume Spike: {last_vol:.0f} ≥ {multiplier}×{avg:.0f}",
        )
    return QualityGateResult(
        False,
        f"Volume Spike: الحجم ضعيف ({last_vol:.0f} < {multiplier}×{avg:.0f})",
    )


def run_quality_gates(
    *,
    candles_m15: list[Candle],
    candles_h1: list[Candle],
    smc: SMCResult,
    volume: VolumeAnalysis,
    direction: TrendDirection,
    enabled: bool = True,
    volume_spike_multiplier: float = 1.5,
    candles_h4: list[Candle] | None = None,
) -> QualityGateResult:
    """تشغيل كل بوابات الجودة بالتسلسل."""
    if not enabled or direction == TrendDirection.NEUTRAL:
        if direction == TrendDirection.NEUTRAL:
            return QualityGateResult(False, "جودة: اتجاه محايد")
        return QualityGateResult(True, "بوابات الجودة معطّلة")

    gates = [
        check_confluence(smc=smc, volume=volume, direction=direction),
        check_retest(candles_m15 or candles_h1, direction=direction),
        check_rsi_divergence(candles_h1 or candles_m15, direction=direction),
        check_volume_spike(
            candles_h1 or candles_m15,
            multiplier=volume_spike_multiplier,
        ),
    ]
    for gate in gates:
        if not gate.passed:
            return gate

    # مصفوفة RSI+MACD متعددة الأطر (v1.3)
    try:
        from core.market_filters_extra import check_macd_rsi_divergence_matrix
        from core.technical.indicators import closes

        h1_c = closes(candles_h1 or candles_m15)
        h4_src = candles_h4 or candles_h1 or candles_m15
        h4_c = closes(h4_src)
        side = "buy" if direction == TrendDirection.BULLISH else "sell"
        matrix = check_macd_rsi_divergence_matrix(h1_c, h4_c, direction=side)
        if not matrix.allowed:
            return QualityGateResult(False, matrix.reason)
    except Exception:
        pass

    return QualityGateResult(True, "جودة الدخول: كل البوابات ناجحة")
