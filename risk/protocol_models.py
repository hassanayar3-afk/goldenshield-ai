"""نماذج بروتوكولات التشغيل المؤسسية."""

from __future__ import annotations

from dataclasses import dataclass

from operations.trade_prefs import TradePrefs

RISK_MODE_STANDARD = "standard"
RISK_MODE_HIGH_CONVICTION = "high_conviction"


@dataclass(frozen=True)
class ProtocolApproval:
    approved: bool
    reason: str
    risk_mode: str = RISK_MODE_STANDARD
    trade_prefs: TradePrefs | None = None
    scaling_add_pending: bool = False

    @classmethod
    def disabled(cls, reason: str) -> ProtocolApproval:
        return cls(approved=False, reason=reason, risk_mode=RISK_MODE_STANDARD)
