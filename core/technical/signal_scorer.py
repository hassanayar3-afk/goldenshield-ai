from __future__ import annotations

import os
from dataclasses import dataclass

from core.constants import SIGNAL_MAX_SCORE, SIGNAL_MIN_PERCENT, meets_signal_minimum, score_to_percent
from core.technical.fvg_detector import FVGResult, FVGType
from core.technical.manipulation_guard import ManipulationGuardResult
from core.technical.mean_reversion import MeanReversionResult, ReversionSignal
from core.technical.smc_analyzer import MarketStructure, SMCResult
from core.technical.spread_filter import SpreadFilterResult
from core.technical.timeframe_aligner import TimeframeAlignment, TrendDirection
from core.technical.volume_analyzer import VolumeAnalysis, VolumeBias


@dataclass(frozen=True)
class ScoreBreakdown:
    total: int
    components: dict[str, int]
    passed_minimum: bool
    reasons: tuple[str, ...]


def _directional_scoring_enabled() -> bool:
    """طبقة مضافة: لا تحتسب نقاطاً ضد اتجاه الأطر. افتراضي مفعّل."""
    raw = os.getenv("DIRECTIONAL_COMPONENT_SCORING", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _aligned_bull(alignment: TimeframeAlignment) -> bool:
    return alignment.aligned and alignment.direction == TrendDirection.BULLISH


def _aligned_bear(alignment: TimeframeAlignment) -> bool:
    return alignment.aligned and alignment.direction == TrendDirection.BEARISH


def score_signal(
    *,
    alignment: TimeframeAlignment,
    smc: SMCResult,
    fvg: FVGResult,
    volume: VolumeAnalysis,
    mean_reversion: MeanReversionResult,
    spread: SpreadFilterResult,
    manipulation: ManipulationGuardResult,
) -> ScoreBreakdown:
    components: dict[str, int] = {}
    reasons: list[str] = []
    directional = _directional_scoring_enabled()

    if manipulation.is_suspicious:
        return ScoreBreakdown(
            total=0,
            components={"manipulation_reject": 0},
            passed_minimum=False,
            reasons=(manipulation.reason,),
        )

    if not spread.passed:
        return ScoreBreakdown(
            total=0,
            components={"spread_reject": 0},
            passed_minimum=False,
            reasons=(spread.reason,),
        )

    # توافق الأطر (3 نقاط)
    if alignment.aligned:
        components["timeframe_alignment"] = 3
        reasons.append(f"توافق {alignment.direction.value} على M15/H1/H4")
    else:
        components["timeframe_alignment"] = 0
        reasons.append("عدم توافق الأطر الزمنية")

    bull = _aligned_bull(alignment)
    bear = _aligned_bear(alignment)

    # SMC (2 نقطة) — فقط إن وافق الاتجاه عند تفعيل الطبقة
    smc_points = 0
    smc_dir_ok = True
    if directional and alignment.aligned:
        if bull and smc.structure == MarketStructure.BEARISH:
            smc_dir_ok = False
        elif bear and smc.structure == MarketStructure.BULLISH:
            smc_dir_ok = False
    if smc_dir_ok:
        if smc.bos:
            smc_points += 1
            reasons.append("BOS مؤكد")
        if smc.order_block:
            smc_points += 1
            reasons.append("Order Block نشط")
    elif smc.bos or smc.order_block:
        reasons.append("تجاهل SMC المخالف لاتجاه الأطر")
    components["smc"] = smc_points

    # FVG (1 نقطة) — فقط مع الاتجاه
    if fvg.has_active_gap and fvg.nearest_gap is not None:
        gap = fvg.nearest_gap.gap_type
        if gap == FVGType.BULLISH and (not directional or bull):
            components["fvg"] = 1
            reasons.append("FVG صاعد")
        elif gap == FVGType.BEARISH and (not directional or bear):
            components["fvg"] = 1
            reasons.append("FVG هابط")
        else:
            components["fvg"] = 0
            if directional and alignment.aligned:
                reasons.append("تجاهل FVG المخالف للاتجاه")
    else:
        components["fvg"] = 0

    # Mean Reversion (2 نقطة) — فقط مع الاتجاه
    if mean_reversion.is_setup and mean_reversion.signal == ReversionSignal.BUY:
        if not directional or bull:
            components["mean_reversion"] = 2
            reasons.append("إعداد ارتداد للمتوسط (شراء)")
        else:
            components["mean_reversion"] = 0
            reasons.append("تجاهل ارتداد شراء ضد الاتجاه")
    elif mean_reversion.is_setup and mean_reversion.signal == ReversionSignal.SELL:
        if not directional or bear:
            components["mean_reversion"] = 2
            reasons.append("إعداد ارتداد للمتوسط (بيع)")
        else:
            components["mean_reversion"] = 0
            reasons.append("تجاهل ارتداد بيع ضد الاتجاه")
    elif mean_reversion.is_setup:
        # إعداد بلا اتجاه واضح — لا يُحتسب عند الطبقة الاتجاهية
        components["mean_reversion"] = 0 if directional else 1
        reasons.append("إعداد ارتداد للمتوسط")
    else:
        components["mean_reversion"] = 0

    # Volume (1 نقطة) — فقط مع الاتجاه
    if volume.high_volume_zone and volume.bias == VolumeBias.BULLISH:
        if not directional or bull:
            components["volume"] = 1
            reasons.append("تأكيد حجم صاعد")
        else:
            components["volume"] = 0
            reasons.append("تجاهل حجم صاعد ضد الاتجاه")
    elif volume.high_volume_zone and volume.bias == VolumeBias.BEARISH:
        if not directional or bear:
            components["volume"] = 1
            reasons.append("تأكيد حجم هابط")
        else:
            components["volume"] = 0
            reasons.append("تجاهل حجم هابط ضد الاتجاه")
    else:
        components["volume"] = 0

    # Spread (1 نقطة)
    components["spread"] = 1 if spread.passed else 0

    # أوزان تكيفية خفيفة (طبقة مضافة — لا تكسر عند الفشل)
    try:
        from intelligence.adaptive_weights import apply_weight_multipliers

        components = apply_weight_multipliers(components)
    except Exception:
        pass

    total = min(SIGNAL_MAX_SCORE, sum(components.values()))
    passed = meets_signal_minimum(total)

    if passed:
        reasons.append(f"الدرجة النهائية: {score_to_percent(total)}/100")
    else:
        reasons.append(
            f"مرفوض — الدرجة {score_to_percent(total)}/100 "
            f"(المطلوب {SIGNAL_MIN_PERCENT}/100)"
        )

    return ScoreBreakdown(
        total=total,
        components=components,
        passed_minimum=passed,
        reasons=tuple(reasons),
    )


def is_trade_allowed(score: ScoreBreakdown, alignment: TimeframeAlignment, smc: SMCResult) -> bool:
    if not score.passed_minimum:
        return False
    if not alignment.aligned:
        return False
    if alignment.direction == TrendDirection.BULLISH:
        if smc.structure == MarketStructure.BEARISH and smc.choch:
            return False
        return True
    if alignment.direction == TrendDirection.BEARISH:
        if smc.structure == MarketStructure.BULLISH and smc.choch:
            return False
        return True
    return False
