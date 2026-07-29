"""اختبارات الطبقات المؤسسية v1.2 — كلها OFF افتراضياً."""

from __future__ import annotations

from unittest.mock import patch

from core.technical.indicators import adx
from data.models.candle import Candle
from risk.adx_filter import check_adx_filter
from risk.partial_scaling import plan_partial_scaling, should_add_scaling
from risk.profit_cap import check_profit_cap
from risk.micro_simulation import run_micro_simulation
from risk.panic_mode import check_panic_mode
from operations.smart_trade_report import format_smart_trade_report


def _candle(o, h, l, c):
    return Candle(timestamp=0, open=o, high=h, low=l, close=c, volume=1.0)


def test_adx_computes_on_trending_series():
    candles = []
    price = 100.0
    for i in range(60):
        price += 1.2
        candles.append(_candle(price - 0.5, price + 0.8, price - 0.8, price))
    value = adx(candles, period=14)
    assert value is not None
    assert 0 <= value <= 100


def test_adx_filter_disabled_passes():
    with patch("risk.adx_filter.get_settings") as gs:
        gs.return_value.adx_filter_enabled = False
        result = check_adx_filter("BTC/USDT")
    assert result.allowed is True


def test_profit_cap_disabled_passes():
    with patch("risk.profit_cap.get_settings") as gs:
        gs.return_value.profit_cap_enabled = False
        result = check_profit_cap(5.0)
    assert result.allowed is True


def test_profit_cap_blocks_when_enabled():
    with patch("risk.profit_cap.get_settings") as gs:
        gs.return_value.profit_cap_enabled = True
        gs.return_value.profit_cap_daily_pct = 3.0
        result = check_profit_cap(3.5)
    assert result.allowed is False


def test_partial_scaling_disabled_uses_full_size():
    with patch("risk.partial_scaling.get_settings") as gs:
        gs.return_value.partial_scaling_enabled = False
        plan = plan_partial_scaling(1.0)
    assert plan.enabled is False
    assert plan.initial_amount == 1.0


def test_partial_scaling_splits_when_enabled():
    with patch("risk.partial_scaling.get_settings") as gs:
        gs.return_value.partial_scaling_enabled = True
        gs.return_value.partial_scaling_initial_pct = 50
        gs.return_value.partial_scaling_add_pct = 50
        plan = plan_partial_scaling(1.0)
    assert plan.enabled is True
    assert plan.initial_amount == 0.5
    assert plan.add_amount == 0.5


def test_should_add_scaling_after_half_r():
    with patch("risk.partial_scaling.get_settings") as gs:
        gs.return_value.partial_scaling_trigger_r = 0.5
        ok, _ = should_add_scaling(
            side="buy",
            entry_price=100.0,
            current_price=102.0,
            stop_loss=96.0,
        )
    assert ok is True


def test_micro_sim_disabled_passes():
    with patch("risk.micro_simulation.get_settings") as gs:
        gs.return_value.micro_simulation_enabled = False
        result = run_micro_simulation("BTC/USDT")
    assert result.allowed is True


def test_panic_disabled_passes():
    with patch("risk.panic_mode.get_settings") as gs:
        gs.return_value.market_correlation_filter_enabled = False
        result = check_panic_mode(side="buy")
    assert result.allowed is True


def test_smart_report_format():
    text = format_smart_trade_report(
        symbol="BTC/USDT",
        side="buy",
        entry_price=100.0,
        exit_price=103.0,
        stop_loss=99.0,
        take_profit=103.0,
        pnl=3.0,
        reason="Take Profit",
        signal_score=9,
        filters="SMC+FVG",
    )
    assert "BTC/USDT" in text
    assert "R:R" in text
