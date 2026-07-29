"""اختبارات إصلاحات الحماية الحرجة — SL على كل الأجزاء + halt policy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from execution.models.order import Order, OrderSide, OrderStatus
from execution.sl_attachment_guard import ensure_fill_has_sl_or_close
from risk.halt_policy import evaluate_trading_halt


def test_halt_policy_kill_keeps_manage_positions():
    with patch("risk.halt_policy.get_settings") as gs:
        gs.return_value.manage_positions_during_halt = True
        decision = evaluate_trading_halt(paused=False, kill_switch_active=True)
    assert decision.entries_blocked is True
    assert decision.manage_positions is True
    assert "Kill Switch" in decision.reason


def test_halt_policy_pause_keeps_manage_positions():
    with patch("risk.halt_policy.get_settings") as gs:
        gs.return_value.manage_positions_during_halt = True
        decision = evaluate_trading_halt(paused=True, kill_switch_active=False)
    assert decision.entries_blocked is True
    assert decision.manage_positions is True


def test_paper_fill_with_sl_confirmed():
    order = Order(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        amount=0.01,
        is_paper=True,
    )
    order.mark_filled(100.0)
    manager = MagicMock()
    with patch("execution.sl_attachment_guard.get_settings") as gs:
        gs.return_value.close_naked_tickets = True
        gs.return_value.execution_mode = "paper"
        ok = ensure_fill_has_sl_or_close(
            manager,
            order=order,
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            amount=0.01,
            stop_loss=97.0,
            take_profit=109.0,
            reference_price=100.0,
        )
    assert ok is True
    assert order.stops_confirmed is True
    manager.create_market_order.assert_not_called()


def test_naked_ticket_triggers_emergency_close():
    order = Order(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        amount=0.01,
        is_paper=True,
    )
    order.mark_filled(100.0)
    manager = MagicMock()
    with patch("execution.sl_attachment_guard.get_settings") as gs:
        gs.return_value.close_naked_tickets = True
        gs.return_value.execution_mode = "paper"
        ok = ensure_fill_has_sl_or_close(
            manager,
            order=order,
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            amount=0.01,
            stop_loss=0.0,
            take_profit=0.0,
            reference_price=100.0,
        )
    assert ok is False
    manager.create_market_order.assert_called_once()
    kwargs = manager.create_market_order.call_args.kwargs
    assert kwargs.get("allow_without_stops") is True


def test_live_create_rejects_without_sl(monkeypatch):
    from execution.order_manager import OrderManager

    class _Settings:
        execution_mode = "live"
        execution_backend = "binance"
        mt5_enabled = False
        binance_api_key = "k"
        binance_api_secret = "s"
        require_sl_on_all_chunks = True
        mt5_attach_sl_tp = True

    monkeypatch.setattr("execution.order_manager.get_settings", lambda: _Settings())
    manager = OrderManager()
    try:
        manager.create_market_order(
            "BTC/USDT",
            OrderSide.BUY,
            0.01,
            reference_price=100.0,
            stop_loss=None,
            take_profit=None,
        )
        assert False, "should have raised"
    except Exception as exc:
        assert "Zero-SL Denial" in str(exc) or "Stop Loss" in str(exc)
