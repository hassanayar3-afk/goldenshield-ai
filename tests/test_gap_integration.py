from datetime import date

from audit.audit_trail import AuditTrail
from audit.decision_logger import DecisionLogger
from audit.snapshot_recorder import SnapshotRecorder
from core.analyzer import AnalysisResult
from database.connection import init_database
from database.repositories.operations_repo import OperationsRepository
from database.repositories.snapshot_repo import SnapshotRepository
from database.repositories.trade_repo import TradeRepository
from execution.models.order import OrderSide
from execution.trade_executor import TradeExecutor
from execution.models.trade import Position
from risk.risk_orchestrator import RiskOrchestrator
from unittest.mock import MagicMock


def _analysis_result(**kwargs) -> AnalysisResult:
    defaults = {
        "symbol": "BTC/USDT",
        "price": 100.0,
        "score": 6,
        "signal": "WAIT",
        "passed": False,
        "halted": False,
        "reasons": ("wait",),
        "sma": 99.0,
    }
    defaults.update(kwargs)
    return AnalysisResult(**defaults)


def test_audit_logs_wait_decision(tmp_path):
    db = init_database(str(tmp_path / "audit.db"))
    audit = AuditTrail(
        snapshot_recorder=SnapshotRecorder(repository=SnapshotRepository(db)),
        decision_logger=DecisionLogger(repository=TradeRepository(db)),
    )
    result = _analysis_result()
    snapshot, consensus = audit.record_market_check(result)
    logged = audit.log_analysis_outcome(snapshot, result, consensus=consensus)
    assert logged is not None
    assert TradeRepository(db).decision_count() == 1


def test_trade_executor_persists_open_and_close(tmp_path):
    db = init_database(str(tmp_path / "trades.db"))
    trade_repo = TradeRepository(db)
    risk = RiskOrchestrator()
    risk.initialize(10000.0)
    alerts = MagicMock()
    audit = AuditTrail(decision_logger=DecisionLogger(repository=trade_repo))
    executor = TradeExecutor(
        risk_orchestrator=risk,
        trade_repository=trade_repo,
        alert_dispatcher=alerts,
        audit_trail=audit,
    )
    position = Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=100.0,
        amount=1.0,
        stop_loss=95.0,
        take_profit=110.0,
        id="pos-test-1",
    )
    executor.position_manager.add(position)
    executor._persist_open_trade(position)
    executor._close_position(position, 105.0, "Take Profit")

    assert alerts.trade_closed.called
    decisions = trade_repo.list_decisions(limit=5)
    assert any(d.action.value == "exit" for d in decisions)


def test_operations_repo_archives_report(tmp_path):
    db = init_database(str(tmp_path / "ops.db"))
    repo = OperationsRepository(db)
    repo.save_daily_report(date.today().isoformat(), "test report")
    repo.save_operation_log("INFO", "startup ok")
    with db.connect() as conn:
        reports = conn.execute("SELECT COUNT(*) AS c FROM daily_reports").fetchone()
        logs = conn.execute("SELECT COUNT(*) AS c FROM operation_logs").fetchone()
    assert reports["c"] == 1
    assert logs["c"] == 1
