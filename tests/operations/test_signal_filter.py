from types import SimpleNamespace

from core.constants import SIGNAL_MIN_PERCENT, meets_signal_minimum
from operations.signal_filter import (
    is_notifiable_entry,
    is_notifiable_trade_signal,
    is_premium_trade_signal,
)
from risk.risk_orchestrator import RiskApproval


def _result(**kwargs):
    return SimpleNamespace(**kwargs)


def test_premium_requires_buy_score_shadow_risk():
    result = _result(
        halted=False,
        signal="BUY SIGNAL",
        passed=True,
        score=8,
    )
    consensus = SimpleNamespace(approved=True)
    risk = RiskApproval(approved=True, reason="ok", amount=0.1, stop_loss=1.0, take_profit=2.0)
    assert is_premium_trade_signal(result, consensus=consensus, risk_approval=risk) is True


def test_wait_is_not_premium():
    result = _result(halted=False, signal="WAIT", passed=False, score=5)
    assert is_premium_trade_signal(result) is False


def test_buy_low_score_not_premium():
    result = _result(halted=False, signal="BUY SIGNAL", passed=False, score=6)
    assert is_premium_trade_signal(result) is False


def test_buy_score_eight_is_premium():
    result = _result(halted=False, signal="BUY SIGNAL", passed=True, score=8)
    consensus = SimpleNamespace(approved=True)
    risk = RiskApproval(approved=True, reason="ok", amount=0.1, stop_loss=1.0, take_profit=2.0)
    assert is_premium_trade_signal(result, consensus=consensus, risk_approval=risk) is True


def test_buy_score_seven_not_premium():
    result = _result(halted=False, signal="BUY SIGNAL", passed=True, score=7)
    assert is_premium_trade_signal(result) is False


def test_buy_without_risk_approval_not_premium():
    result = _result(halted=False, signal="BUY SIGNAL", passed=True, score=9)
    risk = RiskApproval(approved=False, reason="kill switch")
    assert is_premium_trade_signal(result, risk_approval=risk) is False


def test_notify_buy_sell_from_75_only():
    assert is_notifiable_trade_signal(
        _result(halted=False, signal="BUY SIGNAL", passed=True, score=8)
    )
    assert is_notifiable_trade_signal(
        _result(halted=False, signal="SELL SIGNAL", passed=True, score=9)
    )
    assert not is_notifiable_trade_signal(
        _result(halted=False, signal="WAIT", passed=True, score=9)
    )
    assert not is_notifiable_trade_signal(
        _result(halted=False, signal="BUY SIGNAL", passed=True, score=7)
    )
    assert SIGNAL_MIN_PERCENT == 75
    assert meets_signal_minimum(8)


def test_entry_action_auto_vs_manual(monkeypatch):
    from operations.signal_filter import entry_action_label
    from types import SimpleNamespace

    # Iron Protocol: دخول تلقائي من 95/100 فقط
    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(auto_entry_min_percent=95, manual_entry_required=False),
    )

    assert "يدوي" in entry_action_label(9, open_positions=0)  # 90 < 95
    assert "ذهبي" in entry_action_label(10, open_positions=0) or "تلقائي" in entry_action_label(
        10, open_positions=0
    )
    assert "يدوي" in entry_action_label(8, open_positions=0)


def test_annotate_drops_wait(monkeypatch):
    from operations.signal_filter import annotate_entry_actions
    from types import SimpleNamespace

    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(auto_entry_min_percent=95, manual_entry_required=False),
    )

    rows = annotate_entry_actions(
        [
            {"symbol": "A", "signal": "WAIT", "score": 10, "passed": True},
            {"symbol": "B", "signal": "BUY SIGNAL", "score": 9, "passed": True},
            {"symbol": "C", "signal": "BUY SIGNAL", "score": 10, "passed": True},
        ],
        open_positions=0,
    )
    assert len(rows) == 2
    by_symbol = {r["symbol"]: r for r in rows}
    assert "A" not in by_symbol
    assert "يدوي" in by_symbol["B"]["entry_action"]
    assert "تلقائي" in by_symbol["C"]["entry_action"] or "ذهبي" in by_symbol["C"]["entry_action"]


def test_qualified_signals_list_dedupes_same_fingerprint(monkeypatch):
    from unittest.mock import MagicMock

    from operations.alert_dispatcher import AlertDispatcher
    from operations.runtime_state import OperationsRuntime
    from operations.telegram_commands import TelegramCommandHandler
    from execution.trade_executor import TradeExecutor
    from operations.panic_button import PanicButton
    from risk.risk_orchestrator import RiskOrchestrator

    monkeypatch.setattr(
        "operations.telegram_commands.should_block_signals",
        lambda: False,
    )

    sent: list[str] = []

    class FakeTg:
        def send_message(self, text, reply_markup=None):
            sent.append(text)
            return 1

    executor = TradeExecutor()
    alerts = AlertDispatcher(telegram=MagicMock(configured=False))
    handler = TelegramCommandHandler(
        runtime=OperationsRuntime(),
        executor=executor,
        risk=RiskOrchestrator(),
        panic=PanicButton(executor, alerts),
        telegram=FakeTg(),
    )
    handler._enabled = True
    entries = [
        {
            "symbol": "XAU/USD",
            "score": 8,
            "signal": "BUY SIGNAL",
            "price": 2300.0,
            "passed": True,
        },
        {
            "symbol": "BTC/USDT",
            "score": 9,
            "signal": "SELL SIGNAL",
            "price": 100.0,
            "passed": True,
        },
    ]
    assert handler.send_qualified_signals_list(entries) is True
    assert len(sent) == 1
    assert "صفقات جاهزة للدخول" in sent[0]
    assert handler.send_qualified_signals_list(entries) is False
    assert len(sent) == 1
    entries[0]["score"] = 10
    assert handler.send_qualified_signals_list(entries) is True
    assert len(sent) == 2
