from unittest.mock import MagicMock

from execution.trade_executor import TradeExecutor
from operations.alert_dispatcher import AlertDispatcher
from operations.panic_button import PanicButton
from operations.runtime_state import OperationsRuntime
from operations.telegram_commands import TelegramCommandHandler
from risk.risk_orchestrator import RiskOrchestrator


def test_panic_button_closes_positions():
    risk = RiskOrchestrator()
    risk.initialize(10000.0)
    executor = TradeExecutor(risk_orchestrator=risk)
    alerts = AlertDispatcher(telegram=MagicMock(configured=False))
    panic = PanicButton(executor, alerts)

    from execution.models.order import OrderSide
    from execution.models.trade import Position

    executor.position_manager.add(
        Position(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=100.0,
            amount=0.1,
            stop_loss=97.0,
            take_profit=106.0,
        )
    )

    result = panic.trigger({"BTC/USDT": 101.0}, reason="اختبار")

    assert result.triggered is True
    assert result.closed_symbols == ("BTC/USDT",)
    assert executor.position_manager.count() == 0


def test_telegram_pause_and_resume():
    risk = RiskOrchestrator()
    risk.initialize(10000.0)
    executor = TradeExecutor(risk_orchestrator=risk)
    runtime = OperationsRuntime()
    alerts = AlertDispatcher(telegram=MagicMock(configured=False))
    panic = PanicButton(executor, alerts)
    handler = TelegramCommandHandler(
        runtime=runtime,
        executor=executor,
        risk=risk,
        panic=panic,
        telegram=MagicMock(configured=False),
    )

    reply, _ = handler.handle("/pause")
    assert "موقوف" in reply
    assert runtime.paused is True

    reply, _ = handler.handle("/resume")
    assert "يعمل" in reply
    assert runtime.paused is False


def test_telegram_status_includes_balance():
    risk = RiskOrchestrator()
    risk.initialize(5000.0)
    executor = TradeExecutor(risk_orchestrator=risk)
    runtime = OperationsRuntime()
    alerts = AlertDispatcher(telegram=MagicMock(configured=False))
    panic = PanicButton(executor, alerts)
    handler = TelegramCommandHandler(
        runtime=runtime,
        executor=executor,
        risk=risk,
        panic=panic,
        telegram=MagicMock(configured=False),
    )

    reply, keyboard = handler.handle("/start")
    assert "GoldenShield" in reply
    assert "USDT" in reply
    assert keyboard is not None
