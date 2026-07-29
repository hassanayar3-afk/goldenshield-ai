"""نماذج سجل القرارات."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionAction(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    REJECT = "reject"


@dataclass(frozen=True)
class DecisionRecord:
    symbol: str
    action: DecisionAction
    reason: str
    snapshot_id: str | None = None
    position_id: str | None = None
    pnl: float | None = None
    shadow_consensus: bool | None = None
    id: str = field(default_factory=lambda: f"dec-{uuid4().hex[:12]}")
    recorded_at: datetime = field(default_factory=_utc_now)
