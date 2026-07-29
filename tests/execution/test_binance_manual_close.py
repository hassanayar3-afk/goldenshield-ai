"""إغلاق يدوي على مسار Binance — صفقات ورقية وحيّة."""

from __future__ import annotations

from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.trade_executor import TradeExecutor
from operations.telegram_dashboard import MarketState, TelegramDashboard


def test_close_paper_position_while_live_mode(monkeypatch):
    """صفقة ورقية تُغلق محلياً حتى لو EXECUTION_MODE=live."""
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("EXECUTION_BACKEND", "binance")
    monkeypatch.setenv("MT5_ENABLED", "false")
    from config.settings import load_settings

    load_settings("dev", reload=True)

    executor = TradeExecutor()
    position = Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=100.0,
        amount=0.01,
        stop_loss=97.0,
        take_profit=109.0,
        is_paper=True,
    )
    executor.position_manager.add(position)

    def _boom(*_a, **_k):
        raise AssertionError("live submit must not run for paper close")

    monkeypatch.setattr(executor.order_manager, "_submit_live_order", _boom)

    ok = executor.close_position("BTC/USDT", 105.0, reason="إغلاق يدوي")
    assert ok is True
    assert not executor.position_manager.has("BTC/USDT")


def test_dashboard_close_shows_error_on_failure(monkeypatch):
    executor = TradeExecutor()
    position = Position(
        symbol="ETH/USDT",
        side=OrderSide.BUY,
        entry_price=2000.0,
        amount=0.1,
        stop_loss=1900.0,
        take_profit=2300.0,
        is_paper=False,
    )
    executor.position_manager.add(position)

    def _fail(*_a, **_k):
        raise RuntimeError("binance down")

    monkeypatch.setattr(executor, "close_position", _fail)

    dash = TelegramDashboard.__new__(TelegramDashboard)
    dash.executor = executor
    dash.market = MarketState(prices={"ETH/USDT": 2100.0})
    dash._price_fetcher = None
    monkeypatch.setattr(dash, "_fetch_prices", lambda symbols: {"ETH/USDT": 2100.0})

    view = dash._close_position("ETH/USDT")
    assert "فشل" in view.text or "binance down" in view.text
    assert executor.position_manager.has("ETH/USDT")
