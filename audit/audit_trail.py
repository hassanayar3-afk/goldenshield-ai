"""منسق التدقيق — Snapshot + Shadow + Consensus + Logging."""

from __future__ import annotations

from core.analyzer import AnalysisResult
from audit.consensus_gate import ConsensusResult, check_consensus
from audit.decision_logger import DecisionLogger
from audit.models.decision_record import DecisionRecord
from audit.models.snapshot import MarketSnapshot
from audit.shadow_executor import ShadowResult, evaluate_shadow
from audit.snapshot_recorder import SnapshotRecorder


class AuditTrail:
    def __init__(
        self,
        *,
        snapshot_recorder: SnapshotRecorder | None = None,
        decision_logger: DecisionLogger | None = None,
    ) -> None:
        self.snapshots = snapshot_recorder or SnapshotRecorder()
        self.decisions = decision_logger or DecisionLogger()

    def evaluate_entry(self, result: AnalysisResult) -> tuple[MarketSnapshot, ConsensusResult]:
        snapshot = self.snapshots.record(result)
        shadow = evaluate_shadow(result)
        consensus = check_consensus(shadow)
        return snapshot, consensus

    def log_reject(
        self,
        snapshot: MarketSnapshot,
        reason: str,
        *,
        shadow_consensus: bool = False,
    ) -> DecisionRecord:
        return self.decisions.log_reject(
            snapshot.symbol,
            reason=reason,
            snapshot_id=snapshot.id,
            shadow_consensus=shadow_consensus,
        )

    def log_entry(
        self,
        snapshot: MarketSnapshot,
        *,
        position_id: str,
        reason: str,
    ) -> DecisionRecord:
        return self.decisions.log_entry(
            snapshot.symbol,
            snapshot_id=snapshot.id,
            position_id=position_id,
            reason=reason,
            shadow_consensus=True,
        )

    def log_exit(
        self,
        symbol: str,
        *,
        reason: str,
        pnl: float,
        position_id: str | None = None,
    ) -> DecisionRecord:
        return self.decisions.log_exit(
            symbol,
            reason=reason,
            pnl=pnl,
            position_id=position_id,
        )

    def record_market_check(self, result: AnalysisResult) -> tuple[MarketSnapshot, ConsensusResult]:
        """لقطة + Shadow لكل دورة تحليل — يُستخدم قبل قرار التنفيذ."""
        return self.evaluate_entry(result)

    def log_analysis_outcome(
        self,
        snapshot: MarketSnapshot,
        result: AnalysisResult,
        *,
        consensus: ConsensusResult | None = None,
    ) -> DecisionRecord | None:
        if result.halted:
            return self.log_reject(snapshot, result.reasons[-1] if result.reasons else "market_halt")

        if result.signal == "REJECTED":
            reason = result.reasons[0] if result.reasons else "rejected"
            return self.log_reject(snapshot, reason)

        if result.signal == "WAIT" or not result.passed:
            return self.log_reject(snapshot, f"WAIT — درجة {result.score}/10")

        if consensus is not None and not consensus.approved:
            return self.log_reject(
                snapshot,
                f"Shadow: {consensus.reason}",
                shadow_consensus=False,
            )

        return None
