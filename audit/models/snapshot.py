"""نماذج لقطة حالة السوق."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: float
    score: int
    signal: str
    passed: bool
    halted: bool
    reasons: tuple[str, ...]
    sma: float
    id: str = field(default_factory=lambda: f"snap-{uuid4().hex[:12]}")
    captured_at: datetime = field(default_factory=_utc_now)
