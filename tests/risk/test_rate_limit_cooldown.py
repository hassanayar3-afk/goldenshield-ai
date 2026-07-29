from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from risk.rate_limiter import check_rate_limit, prune_open_timestamps
from risk.risk_orchestrator import RiskOrchestrator
from risk.state import RiskState
from risk.trade_cooldown import (
    check_post_trade_cooldown,
    compute_post_trade_cooldown_until,
)


def _allow_safety(mock_zones, mock_news):
    from types import SimpleNamespace

    mock_zones.return_value = SimpleNamespace(allowed=True, reason="ok")
    mock_news.return_value = SimpleNamespace(trading_allowed=True, reason="ok")


def test_rate_limit_blocks_after_max_per_hour():
    now = datetime.now(timezone.utc)
    stamps = [now - timedelta(minutes=m) for m in (50, 40, 10)]
    result = check_rate_limit(stamps, max_per_hour=3, now=now)
    assert result.allowed is False
    assert result.trades_last_hour == 3


def test_rate_limit_allows_under_cap():
    now = datetime.now(timezone.utc)
    stamps = [now - timedelta(minutes=20), now - timedelta(minutes=5)]
    result = check_rate_limit(stamps, max_per_hour=3, now=now)
    assert result.allowed is True
    assert result.trades_last_hour == 2


def test_prune_drops_old_timestamps():
    now = datetime.now(timezone.utc)
    stamps = [now - timedelta(hours=2), now - timedelta(minutes=10)]
    cleaned = prune_open_timestamps(stamps, now=now)
    assert len(cleaned) == 1


def test_post_trade_cooldown_active():
    until = compute_post_trade_cooldown_until(minutes=20)
    result = check_post_trade_cooldown(until)
    assert result.in_cooldown is True


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_orchestrator_blocks_rate_limit(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    now = datetime.now(timezone.utc)
    state = RiskState(
        session_start_balance=10000.0,
        current_balance=10000.0,
        trade_open_timestamps=[
            now - timedelta(minutes=40),
            now - timedelta(minutes=20),
            now - timedelta(minutes=5),
        ],
    )
    orch = RiskOrchestrator(state=state)
    approval = orch.evaluate_entry("BTC/USDT", 100.0, 10000.0, signal_score=10)
    assert approval.approved is False
    assert "سقف الساعة" in approval.reason


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_orchestrator_blocks_post_trade_cooldown(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    state = RiskState(
        session_start_balance=10000.0,
        current_balance=10000.0,
        post_trade_cooldown_until=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    orch = RiskOrchestrator(state=state)
    approval = orch.evaluate_entry("ETH/USDT", 50.0, 10000.0, signal_score=10)
    assert approval.approved is False
    assert "تهدئة" in approval.reason


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_record_closed_sets_cooldown(mock_news, mock_zones):
    _allow_safety(mock_zones, mock_news)
    orch = RiskOrchestrator()
    orch.initialize(10000.0)
    orch.record_closed_trade(10.0)
    assert orch.state is not None
    assert orch.state.post_trade_cooldown_until is not None
    assert check_post_trade_cooldown(orch.state.post_trade_cooldown_until).in_cooldown
