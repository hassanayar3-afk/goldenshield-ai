"""اختبارات التخارج الجزئي 30/40/30."""

from __future__ import annotations

from types import SimpleNamespace

from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.smart_exits import evaluate_multi_tier_tp


def test_multi_tier_tp1_and_tp2(monkeypatch) -> None:
    monkeypatch.setattr(
        "execution.smart_exits.get_settings",
        lambda: SimpleNamespace(
            breakeven_enabled=True,
            trailing_stop_enabled=True,
            institutional_v13={
                "multi_tier_tp_enabled": True,
                "multi_tier_tp1_pct": 0.30,
                "multi_tier_tp2_pct": 0.40,
            },
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
    # r = 1.0 at price 1.03
    tp1 = evaluate_multi_tier_tp(pos, 1.03)
    assert tp1.partial_exit_amount == 30.0
    assert tp1.mark_breakeven is True
    assert tp1.next_exit_tier == 1

    pos.exit_tier = 1
    pos.amount = 70.0
    # r = 2.0 at price 1.06
    tp2 = evaluate_multi_tier_tp(pos, 1.06)
    # 0.4 / 0.7 of remaining ≈ 40 of original 100 → ~40 of remaining 70
    assert abs(tp2.partial_exit_amount - 40.0) < 0.01
    assert tp2.enable_structural_trail is True
