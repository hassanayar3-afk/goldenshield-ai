from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from risk.loss_streak_guard import check_loss_streak
from risk.risk_orchestrator import RiskOrchestrator
from risk.state import RiskState


def _allow_safety(mock_zones, mock_news):
    from types import SimpleNamespace

    mock_zones.return_value = SimpleNamespace(allowed=True, reason="ok")
    mock_news.return_value = SimpleNamespace(trading_allowed=True, reason="ok")


def test_loss_streak_triggers_cooldown_after_3_losses():
    result = check_loss_streak(3, None)
    assert result.in_cooldown is True
    assert result.cooldown_until is not None


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_risk_orchestrator_rejects_kill_switch(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    orchestrator = RiskOrchestrator()
    orchestrator.initialize(10000.0)
    orchestrator.state.current_balance = 9600.0  # -4%

    approval = orchestrator.evaluate_entry("BTC/USDT", 100.0, 9600.0, signal_score=9)
    assert approval.approved is False
    assert "Kill Switch" in approval.reason


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_risk_orchestrator_approves_valid_entry(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    orchestrator = RiskOrchestrator()
    approval = orchestrator.evaluate_entry("BTC/USDT", 100.0, 10000.0, signal_score=9)
    assert approval.approved is True
    assert approval.amount > 0
    assert approval.stop_loss > 0
    assert approval.take_profit > 0


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_risk_orchestrator_respects_cooldown(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    orchestrator = RiskOrchestrator(
        state=RiskState(
            session_start_balance=10000.0,
            current_balance=9900.0,
            consecutive_losses=3,
            cooldown_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    approval = orchestrator.evaluate_entry("ETH/USDT", 50.0, 9900.0, signal_score=10)
    assert approval.approved is False
    assert "راحة" in approval.reason
