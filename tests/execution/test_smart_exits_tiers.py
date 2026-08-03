"""اختبارات استراتيجية الربح الجزئي 50/30/20."""

from __future__ import annotations

from types import SimpleNamespace

from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.smart_exits import evaluate_multi_tier_tp, structural_trail_sl


def _settings(**tiers):
    return SimpleNamespace(
        breakeven_enabled=True,
        trailing_stop_enabled=True,
        trailing_stop_factor=0.5,
        institutional_v13={
            "multi_tier_tp_enabled": True,
            "structural_trailing_enabled": True,
            "partial_tp3_close_enabled": True,
            "multi_tier_tp1_pct": 0.50,
            "multi_tier_tp2_pct": 0.30,
            "multi_tier_runner_pct": 0.20,
            "multi_tier_tp1_r": 1.0,
            "multi_tier_tp2_r": 2.0,
            "multi_tier_tp3_r": 3.0,
            **tiers,
        },
    )


def test_partial_tp_50_30_20(monkeypatch) -> None:
    monkeypatch.setattr("execution.smart_exits.get_settings", lambda: _settings())
    pos = Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        amount=100.0,
        entry_price=100.0,
        stop_loss=97.0,
        take_profit=109.0,
    )
    # risk=3 → 1R at 103
    tp1 = evaluate_multi_tier_tp(pos, 103.0)
    assert abs(tp1.partial_exit_amount - 50.0) < 0.01
    assert tp1.mark_breakeven is True
    assert tp1.new_stop_loss == 100.0
    assert tp1.next_exit_tier == 1
    assert "TP1" in tp1.reason

    pos.exit_tier = 1
    pos.amount = 50.0
    pos.breakeven_applied = True
    # 2R at 106
    tp2 = evaluate_multi_tier_tp(pos, 106.0)
    assert abs(tp2.partial_exit_amount - 30.0) < 0.01
    assert tp2.enable_structural_trail is True
    assert tp2.next_exit_tier == 2

    pos.exit_tier = 2
    pos.amount = 20.0
    # 3R at 109
    tp3 = evaluate_multi_tier_tp(pos, 109.0)
    assert abs(tp3.partial_exit_amount - 20.0) < 0.01
    assert tp3.next_exit_tier == 3


def test_legacy_30_40_config_still_works(monkeypatch) -> None:
    monkeypatch.setattr(
        "execution.smart_exits.get_settings",
        lambda: _settings(
            multi_tier_tp1_pct=0.30,
            multi_tier_tp2_pct=0.40,
            multi_tier_runner_pct=0.30,
            partial_tp3_close_enabled=False,
        ),
    )
    pos = Position(
        symbol="ADA/USDT",
        side=OrderSide.BUY,
        amount=100.0,
        entry_price=1.0,
        stop_loss=0.97,
        take_profit=1.09,
    )
    tp1 = evaluate_multi_tier_tp(pos, 1.03)
    assert abs(tp1.partial_exit_amount - 30.0) < 0.01
    pos.exit_tier = 1
    pos.amount = 70.0
    tp2 = evaluate_multi_tier_tp(pos, 1.06)
    assert abs(tp2.partial_exit_amount - 40.0) < 0.01


def test_trail_after_breakeven(monkeypatch) -> None:
    monkeypatch.setattr("execution.smart_exits.get_settings", lambda: _settings())
    pos = Position(
        symbol="ETH/USDT",
        side=OrderSide.BUY,
        amount=10.0,
        entry_price=100.0,
        stop_loss=100.0,
        take_profit=112.0,
        breakeven_applied=True,
        exit_tier=2,
    )
    trail = structural_trail_sl(pos, 110.0)
    assert trail is not None
    assert trail >= 100.0
