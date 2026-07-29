from unittest.mock import patch

from audit.audit_trail import AuditTrail
from audit.models.decision_record import DecisionAction
from core.analyzer import AnalysisResult
from execution.trade_executor import TradeExecutor


@patch("audit.shadow_executor.get_settings")
@patch("audit.shadow_executor.detect_institutional_zones")
@patch("audit.shadow_executor.track_whales")
def test_trade_executor_requires_shadow_consensus(
    mock_whales, mock_institutional, mock_settings
):
    from types import SimpleNamespace

    from core.liquidity.institutional_zones import InstitutionalZonesResult
    from core.liquidity.whale_tracker import WhaleTrackerResult

    # خارج وضع التجربة: رفض بدون سيولة حقيقية
    mock_settings.return_value = SimpleNamespace(trial_mode=False)
    mock_whales.return_value = WhaleTrackerResult((), False, False, "no whales")
    mock_institutional.return_value = InstitutionalZonesResult((), False, False, "no cluster")

    audit = AuditTrail()
    executor = TradeExecutor(audit_trail=audit)
    result = AnalysisResult(
        symbol="BTC/USDT",
        signal="BUY SIGNAL",
        price=100.0,
        sma=99.0,
        score=9,
        passed=True,
        reasons=("مؤهل",),
    )

    exec_result = executor.try_open(result)

    assert exec_result.executed is False
    assert "Shadow" in exec_result.reason
    assert len(audit.decisions.records) == 1
    assert audit.decisions.records[0].action == DecisionAction.REJECT


@patch("audit.shadow_executor.detect_institutional_zones")
@patch("audit.shadow_executor.track_whales")
def test_trade_executor_logs_entry_on_consensus(mock_whales, mock_institutional, monkeypatch):
    from core.liquidity.institutional_zones import InstitutionalZonesResult
    from core.liquidity.whale_tracker import WhaleTrackerResult
    from risk.risk_orchestrator import RiskApproval

    mock_whales.return_value = WhaleTrackerResult((), True, True, "whale support")
    mock_institutional.return_value = InstitutionalZonesResult((), True, True, "bid cluster")

    audit = AuditTrail()
    executor = TradeExecutor(audit_trail=audit)
    monkeypatch.setattr(
        executor.risk,
        "check_control_gates",
        lambda balance: RiskApproval(True, "ok"),
    )
    monkeypatch.setattr(
        "data.orderbook_fetcher.OrderBookFetcher.fetch",
        lambda self, symbol, **kwargs: (_ for _ in ()).throw(RuntimeError("skip book")),
    )
    result = AnalysisResult(
        symbol="BTC/USDT",
        signal="BUY SIGNAL",
        price=100.0,
        sma=99.0,
        score=9,
        passed=True,
        reasons=("مؤهل",),
    )

    exec_result = executor.try_open(result)

    assert exec_result.executed is True
    assert len(audit.snapshots.snapshots) == 1
    assert any(r.action == DecisionAction.ENTRY for r in audit.decisions.records)
