"""اختبارات Kill Zones وفلتر الأخبار الموحد."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from core.technical.session_filter import check_kill_zones, detect_session
from risk.risk_orchestrator import RiskOrchestrator
from risk.state import RiskState


def test_detect_london_session():
    now = datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc)
    assert detect_session(now) == "london"


def test_detect_overlap_session():
    now = datetime(2026, 7, 16, 14, 0, tzinfo=timezone.utc)
    assert detect_session(now) == "london_ny_overlap"


def test_kill_zones_block_off_hours():
    now = datetime(2026, 7, 16, 3, 0, tzinfo=timezone.utc)  # خارج الجلسات
    result = check_kill_zones(enabled=True, now=now)
    assert result.allowed is False
    assert "Kill Zones" in result.reason


def test_kill_zones_allow_when_disabled():
    now = datetime(2026, 7, 16, 3, 0, tzinfo=timezone.utc)
    result = check_kill_zones(enabled=False, now=now)
    assert result.allowed is True


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_orchestrator_blocks_kill_zones(mock_news, mock_zones):
    from types import SimpleNamespace

    mock_zones.return_value = SimpleNamespace(
        allowed=False, reason="خارج Kill Zones — الجلسة الحالية: off_hours"
    )
    mock_news.return_value = SimpleNamespace(trading_allowed=True, reason="ok")
    orch = RiskOrchestrator(
        state=RiskState(session_start_balance=10000.0, current_balance=10000.0)
    )
    approval = orch.evaluate_entry("BTC/USDT", 100.0, 10000.0, signal_score=10)
    assert approval.approved is False
    assert "Kill Zones" in approval.reason


@patch("risk.risk_orchestrator.check_kill_zones")
@patch("risk.risk_orchestrator.check_news_filter")
def test_orchestrator_blocks_news(mock_news, mock_zones):
    from types import SimpleNamespace

    mock_zones.return_value = SimpleNamespace(allowed=True, reason="ok")
    mock_news.return_value = SimpleNamespace(
        trading_allowed=False, reason="خبر High Impact قريب: FOMC (15 دقيقة)"
    )
    orch = RiskOrchestrator(
        state=RiskState(session_start_balance=10000.0, current_balance=10000.0)
    )
    approval = orch.evaluate_entry("BTC/USDT", 100.0, 10000.0, signal_score=10)
    assert approval.approved is False
    assert "أخبار" in approval.reason or "FOMC" in approval.reason
