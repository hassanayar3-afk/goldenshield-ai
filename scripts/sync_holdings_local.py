"""مزامنة أرصدة Binance → مراكز ثم كتابة تقرير."""

from __future__ import annotations

from pathlib import Path

from config.settings import load_settings
from database.connection import init_database
from database.repositories.trade_repo import TradeRepository
from execution.binance_position_sync import (
    format_holdings_report,
    sync_binance_spot_positions,
)
from execution.trade_executor import TradeExecutor
from operations.alert_dispatcher import AlertDispatcher
from risk.risk_orchestrator import RiskOrchestrator


def main() -> int:
    load_settings(reload=True)
    settings = load_settings()
    db = init_database(settings.db_path)
    executor = TradeExecutor(risk_orchestrator=RiskOrchestrator())
    executor.trade_repo = TradeRepository(db)
    executor.alerts = AlertDispatcher()
    executor.restore_open_positions()
    added = sync_binance_spot_positions(executor)
    report = format_holdings_report(executor)
    out = Path("storage/logs/holdings_report.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report + f"\nSYNCED={added}\n", encoding="utf-8")
    print(report)
    print("SYNCED", added)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
