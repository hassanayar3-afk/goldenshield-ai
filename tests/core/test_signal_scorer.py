from core.constants import meets_signal_minimum
from core.technical.fvg_detector import FVGResult, FVGType, FairValueGap
from core.technical.manipulation_guard import ManipulationGuardResult
from core.technical.mean_reversion import MeanReversionResult, ReversionSignal
from core.technical.signal_scorer import ScoreBreakdown, is_trade_allowed, score_signal
from core.technical.smc_analyzer import MarketStructure, SMCResult
from core.technical.spread_filter import SpreadFilterResult
from core.technical.timeframe_aligner import TimeframeAlignment, TrendDirection
from core.technical.volume_analyzer import VolumeAnalysis, VolumeBias


def _bullish_score_setup() -> ScoreBreakdown:
    alignment = TimeframeAlignment(
        aligned=True,
        direction=TrendDirection.BULLISH,
        per_timeframe={"15m": TrendDirection.BULLISH, "1h": TrendDirection.BULLISH, "4h": TrendDirection.BULLISH},
    )
    smc = SMCResult(
        structure=MarketStructure.BULLISH,
        bos=True,
        choch=False,
        order_block=True,
        swing_high=100.0,
        swing_low=90.0,
    )
    fvg = FVGResult(
        gaps=(
            FairValueGap(
                gap_type=FVGType.BULLISH,
                top=105.0,
                bottom=103.0,
                candle_index=10,
            ),
        ),
        has_active_gap=True,
        nearest_gap=FairValueGap(
            gap_type=FVGType.BULLISH,
            top=105.0,
            bottom=103.0,
            candle_index=10,
        ),
    )
    volume = VolumeAnalysis(
        bias=VolumeBias.BULLISH,
        poc_price=101.0,
        poc_volume=5000.0,
        price_near_poc=True,
        high_volume_zone=True,
    )
    mean_reversion = MeanReversionResult(
        signal=ReversionSignal.BUY,
        rsi_value=32.0,
        sma_value=100.0,
        deviation_pct=-1.5,
        is_setup=True,
    )
    spread = SpreadFilterResult(passed=True, spread_pct=0.05, reason="ok")
    manipulation = ManipulationGuardResult(
        is_suspicious=False,
        reason="clean",
        stop_hunt_detected=False,
    )

    return score_signal(
        alignment=alignment,
        smc=smc,
        fvg=fvg,
        volume=volume,
        mean_reversion=mean_reversion,
        spread=spread,
        manipulation=manipulation,
    )


def test_high_quality_signal_scores_at_least_nine():
    score = _bullish_score_setup()
    assert meets_signal_minimum(score.total)
    assert score.passed_minimum is True


def test_manipulation_reject_scores_zero():
    score = score_signal(
        alignment=TimeframeAlignment(True, TrendDirection.BULLISH, {}),
        smc=SMCResult(MarketStructure.BULLISH, True, False, True, 100, 90),
        fvg=FVGResult((), False, None),
        volume=VolumeAnalysis(VolumeBias.BULLISH, 100, 1000, True, True),
        mean_reversion=MeanReversionResult(ReversionSignal.BUY, 30, 100, -1, True),
        spread=SpreadFilterResult(True, 0.05, "ok"),
        manipulation=ManipulationGuardResult(True, "stop hunt", True),
    )
    assert score.total == 0
    assert score.passed_minimum is False


def test_is_trade_allowed_requires_score_and_alignment():
    score = _bullish_score_setup()
    alignment = TimeframeAlignment(
        aligned=True,
        direction=TrendDirection.BULLISH,
        per_timeframe={},
    )
    smc = SMCResult(MarketStructure.BULLISH, True, False, True, 100, 90)
    assert is_trade_allowed(score, alignment, smc) is True

    weak_alignment = TimeframeAlignment(False, TrendDirection.NEUTRAL, {})
    assert is_trade_allowed(score, weak_alignment, smc) is False


def test_directional_scoring_ignores_counter_trend_components(monkeypatch):
    monkeypatch.setenv("DIRECTIONAL_COMPONENT_SCORING", "true")
    alignment = TimeframeAlignment(
        aligned=True,
        direction=TrendDirection.BULLISH,
        per_timeframe={
            "15m": TrendDirection.BULLISH,
            "1h": TrendDirection.BULLISH,
            "4h": TrendDirection.BULLISH,
        },
    )
    score = score_signal(
        alignment=alignment,
        smc=SMCResult(MarketStructure.BEARISH, True, False, True, 100, 90),
        fvg=FVGResult(
            gaps=(
                FairValueGap(
                    gap_type=FVGType.BEARISH,
                    top=105.0,
                    bottom=103.0,
                    candle_index=10,
                ),
            ),
            has_active_gap=True,
            nearest_gap=FairValueGap(
                gap_type=FVGType.BEARISH,
                top=105.0,
                bottom=103.0,
                candle_index=10,
            ),
        ),
        volume=VolumeAnalysis(VolumeBias.BEARISH, 100, 1000, True, True),
        mean_reversion=MeanReversionResult(ReversionSignal.SELL, 70, 100, 1.5, True),
        spread=SpreadFilterResult(True, 0.05, "ok"),
        manipulation=ManipulationGuardResult(False, "clean", False),
    )
    assert score.components.get("smc", 0) == 0
    assert score.components.get("fvg", 0) == 0
    assert score.components.get("volume", 0) == 0
    assert score.components.get("mean_reversion", 0) == 0
    assert any("تجاهل" in r for r in score.reasons)
