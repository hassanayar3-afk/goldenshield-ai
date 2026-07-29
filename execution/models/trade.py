"""نماذج الصفقات والمراكز."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from execution.models.order import OrderSide


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Position:
    symbol: str
    side: OrderSide
    entry_price: float
    amount: float
    stop_loss: float
    take_profit: float
    id: str = field(default_factory=lambda: f"pos-{uuid4().hex[:12]}")
    opened_at: datetime = field(default_factory=_utc_now)
    breakeven_applied: bool = False
    partial_exit_done: bool = False
    exit_tier: int = 0  # 0=none, 1=TP1@1:1, 2=TP2@1:2
    is_paper: bool = True
    signal_score: int = 0  # قوة الإشارة عند الدخول (0–10)
    risk_mode: str = "standard"  # standard | high_conviction
    # —— Partial Scaling (طبقة مضافة) ——
    scaling_add_pending: bool = False
    scaling_add_amount: float = 0.0
    entry_filters: str = ""

    @property
    def risk_per_unit(self) -> float:
        if self.side == OrderSide.BUY:
            return max(self.entry_price - self.stop_loss, 0.0)
        return max(self.stop_loss - self.entry_price, 0.0)

    @property
    def one_to_one_price(self) -> float:
        if self.side == OrderSide.BUY:
            return self.entry_price + self.risk_per_unit
        return self.entry_price - self.risk_per_unit


@dataclass(frozen=True)
class ExecutionResult:
    executed: bool
    symbol: str
    message: str
    position_id: str | None = None
    rejected: bool = False
    reason: str = ""
