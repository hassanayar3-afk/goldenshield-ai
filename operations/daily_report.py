"""تقرير يومي — PnL، صفقات، مخاطر."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from operations.message_templates import (
    format_daily_report_plain,
    format_daily_report_telegram,
)

if TYPE_CHECKING:
    from audit.audit_trail import AuditTrail
    from execution.trade_executor import TradeExecutor
    from risk.risk_orchestrator import RiskOrchestrator


def format_daily_report(
    *,
    risk: RiskOrchestrator,
    executor: TradeExecutor,
    audit: AuditTrail | None = None,
    report_date: date | None = None,
) -> str:
    return format_daily_report_plain(
        risk=risk,
        executor=executor,
        audit=audit,
        report_date=report_date,
    )


__all__ = ["format_daily_report", "format_daily_report_telegram"]
