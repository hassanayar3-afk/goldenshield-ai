"""اختبارات تمرير SL/TP إلى MT5 — بروتوكول صارم بلا فتح عاري."""

from __future__ import annotations

import pytest

from core.exceptions import ExecutionError
from execution.models.order import OrderSide
from execution.mt5_bridge import MT5OrderResult
from execution.order_manager import OrderManager


class _Settings:
    execution_mode = "live"
    execution_backend = "mt5"
    mt5_enabled = True
    mt5_attach_sl_tp = True
    require_sl_on_all_chunks = True


def test_mt5_order_passes_sl_tp(monkeypatch):
    calls: list[dict] = []

    class Bridge:
        def place_market(self, symbol, *, side, amount, stop_loss=None, take_profit=None):
            calls.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                }
            )
            return MT5OrderResult(ticket=99, symbol="BTCUSD", volume=0.1, price=50000.0, retcode=0)

        def get_position_sl(self, symbol):
            return 49000.0

        def get_position_tp(self, symbol):
            return 52000.0

        def modify_position_sl_tp(self, *args, **kwargs):
            raise AssertionError("should not modify when attach succeeds")

    monkeypatch.setattr("execution.order_manager.get_settings", lambda: _Settings())
    monkeypatch.setattr("execution.mt5_bridge.get_mt5_bridge", lambda: Bridge())

    manager = OrderManager()
    order = manager.create_market_order(
        "BTC/USDT",
        OrderSide.BUY,
        0.01,
        reference_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
    )

    assert order.status.value == "filled"
    assert calls[0]["stop_loss"] == 49000.0
    assert calls[0]["take_profit"] == 52000.0
    assert order.stops_confirmed is True


def test_mt5_rejects_when_broker_refuses_stops(monkeypatch):
    """ممنوع فتح ثم تعديل — الرفض الكامل عند فشل SL/TP مع الأمر."""

    class Bridge:
        def place_market(self, symbol, *, side, amount, stop_loss=None, take_profit=None):
            if stop_loss is not None or take_profit is not None:
                raise ExecutionError("invalid stops")
            raise AssertionError("يجب ألا يُفتح مركز بلا SL/TP")

        def modify_position_sl_tp(self, *args, **kwargs):
            raise AssertionError("لا تعديل بعد فتح عاري")

    monkeypatch.setattr("execution.order_manager.get_settings", lambda: _Settings())
    monkeypatch.setattr("execution.mt5_bridge.get_mt5_bridge", lambda: Bridge())

    with pytest.raises(ExecutionError, match="SL|TP|فشل|stops"):
        OrderManager().create_market_order(
            "BTC/USDT",
            OrderSide.BUY,
            0.01,
            reference_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
        )


def test_mt5_closes_if_stops_not_confirmed_on_platform(monkeypatch):
    closed: list[dict] = []

    class Bridge:
        def place_market(self, symbol, *, side, amount, stop_loss=None, take_profit=None):
            if side.lower() == "sell":
                closed.append({"amount": amount})
                return MT5OrderResult(ticket=2, symbol="BTCUSD", volume=amount, price=50000.0, retcode=0)
            return MT5OrderResult(ticket=1, symbol="BTCUSD", volume=0.01, price=50000.0, retcode=0)

        def get_position_sl(self, symbol):
            return None

        def get_position_tp(self, symbol):
            return None

        def modify_position_sl_tp(self, *args, **kwargs):
            return False

    monkeypatch.setattr("execution.order_manager.get_settings", lambda: _Settings())
    monkeypatch.setattr("execution.mt5_bridge.get_mt5_bridge", lambda: Bridge())

    with pytest.raises(ExecutionError, match="بلا SL/TP"):
        OrderManager().create_market_order(
            "BTC/USDT",
            OrderSide.BUY,
            0.01,
            reference_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
        )
    assert closed  # أُغلق الحجم العاري


def test_entry_without_tp_rejected(monkeypatch):
    monkeypatch.setattr("execution.order_manager.get_settings", lambda: _Settings())

    with pytest.raises(ExecutionError, match="Stop Loss و Take Profit"):
        OrderManager().create_market_order(
            "BTC/USDT",
            OrderSide.BUY,
            0.01,
            reference_price=50000.0,
            stop_loss=49000.0,
            take_profit=None,
        )
