"""حفظ لقطة حالة السوق لحظة القرار."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.analyzer import AnalysisResult
from audit.models.snapshot import MarketSnapshot

if TYPE_CHECKING:
    from database.repositories.snapshot_repo import SnapshotRepository


class SnapshotRecorder:
    def __init__(self, repository: SnapshotRepository | None = None) -> None:
        self._snapshots: list[MarketSnapshot] = []
        self._repository = repository

    @property
    def snapshots(self) -> list[MarketSnapshot]:
        return list(self._snapshots)

    def record(self, result: AnalysisResult) -> MarketSnapshot:
        snapshot = MarketSnapshot(
            symbol=result.symbol,
            price=result.price,
            score=result.score,
            signal=result.signal,
            passed=result.passed,
            halted=result.halted,
            reasons=result.reasons,
            sma=result.sma,
        )
        self._snapshots.append(snapshot)
        if self._repository is not None:
            self._repository.save(snapshot)
        return snapshot

    def get(self, snapshot_id: str) -> MarketSnapshot | None:
        for snapshot in self._snapshots:
            if snapshot.id == snapshot_id:
                return snapshot
        return None

    def clear(self) -> None:
        self._snapshots.clear()
