"""اختبارات بوابات الجودة وTrailing Stop."""

from __future__ import annotations

from core.technical.quality_gates import (
    check_confluence,
    check_retest,
    check_rsi_divergence,
    check_volume_spike,
    run_quality_gates,
)
from core.technical.smc_analyzer import MarketStructure, SMCResult
from core.technical.timeframe_aligner import TrendDirection
from core.technical.volume_analyzer import VolumeAnalysis, VolumeBias
from data.models.candle import Candle
from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.trailing_stop import evaluate_trailing_stop


def _candle(o, h, l, c, v=100.0, ts=0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v)


def test_confluence_requires_smc_and_volume():
    smc = SMCResult(
        structure=MarketStructure.BULLISH,
        bos=True,
        choch=False,
        order_block=True,
        swing_high=110.0,
        swing_low=90.0,
    )
    volume = VolumeAnalysis(
        bias=VolumeBias.BULLISH,
        poc_price=100.0,
        poc_volume=1000.0,
        price_near_poc=True,
        high_volume_zone=True,
    )
    ok = check_confluence(smc=smc, volume=volume, direction=TrendDirection.BULLISH)
    assert ok.passed is True


def test_retest_bullish_confirmation():
    candles = [
        _candle(105, 106, 100, 101, ts=1),  # bearish OB
        _candle(101, 104, 100.5, 103.5, ts=2),  # bullish confirm
    ]
    # need prev=candles[-2], so add dummy first
    candles = [_candle(104, 105, 103, 104, ts=0), *candles]
    result = check_retest(candles, direction=TrendDirection.BULLISH)
    assert result.passed is True


def test_volume_spike_detects_weak_volume():
    candles = [_candle(1, 2, 0.5, 1.5, v=10, ts=i) for i in range(25)]
    candles.append(_candle(1, 2, 0.5, 1.5, v=5, ts=99))  # weaker than avg
    result = check_volume_spike(candles, multiplier=1.5)
    assert result.passed is False


def test_volume_spike_detects_strong_volume():
    candles = [_candle(1, 2, 0.5, 1.5, v=10, ts=i) for i in range(25)]
    candles.append(_candle(1, 2, 0.5, 1.5, v=30, ts=99))
    result = check_volume_spike(candles, multiplier=1.5)
    assert result.passed is True


def test_run_quality_gates_disabled():
    smc = SMCResult(MarketStructure.NEUTRAL, False, False, False, None, None)
    volume = VolumeAnalysis(VolumeBias.NEUTRAL, None, None, False, False)
    result = run_quality_gates(
        candles_m15=[],
        candles_h1=[],
        smc=smc,
        volume=volume,
        direction=TrendDirection.BULLISH,
        enabled=False,
    )
    assert result.passed is True


def test_trailing_stop_after_partial():
    pos = Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=100.0,
        amount=0.5,
        stop_loss=100.0,  # بعد التعادل
        take_profit=106.0,
        breakeven_applied=True,
        partial_exit_done=True,
    )
    action = evaluate_trailing_stop(pos, current_price=106.0)
    # risk proxy = 6/2 = 3 · trail=1.5 · candidate=104.5
    assert action.new_stop_loss is not None
    assert action.new_stop_loss >= 100.0
    assert action.new_stop_loss > 100.0
