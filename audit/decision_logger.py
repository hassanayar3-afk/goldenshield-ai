"""تسجيل قرارات الدخول والخروج والرفض."""

from __future__ import annotations

from typing import TYPE_CHECKING

from audit.models.decision_record import DecisionAction, DecisionRecord

if TYPE_CHECKING:
    from database.repositories.trade_repo import TradeRepository


class DecisionLogger:
    def __init__(self, repository: TradeRepository | None = None) -> None:
        self._records: list[DecisionRecord] = []
        self._repository = repository

    @property
    def records(self) -> list[DecisionRecord]:
        return list(self._records)

    def _persist(self, record: DecisionRecord) -> None:
        if self._repository is not None:
            self._repository.save_decision(record)

    def log_entry(
        self,
        symbol: str,
        *,
        snapshot_id: str,
        position_id: str,
        reason: str,
        shadow_consensus: bool = True,
    ) -> DecisionRecord:
        record = DecisionRecord(
            symbol=symbol,
            action=DecisionAction.ENTRY,
            reason=reason,
            snapshot_id=snapshot_id,
            position_id=position_id,
            shadow_consensus=shadow_consensus,
        )
        self._records.append(record)
        self._persist(record)
        return record

    def log_reject(
        self,
        symbol: str,
        *,
        reason: str,
        snapshot_id: str | None = None,
        shadow_consensus: bool = False,
    ) -> DecisionRecord:
        record = DecisionRecord(
            symbol=symbol,
            action=DecisionAction.REJECT,
            reason=reason,
            snapshot_id=snapshot_id,
            shadow_consensus=shadow_consensus,
        )
        self._records.append(record)
        self._persist(record)
        return record

    def log_exit(
        self,
        symbol: str,
        *,
        reason: str,
        pnl: float,
        position_id: str | None = None,
    ) -> DecisionRecord:
        record = DecisionRecord(
            symbol=symbol,
            action=DecisionAction.EXIT,
            reason=reason,
            position_id=position_id,
            pnl=pnl,
        )
        self._records.append(record)
        self._persist(record)
        return record

    def clear(self) -> None:
        self._records.clear()
