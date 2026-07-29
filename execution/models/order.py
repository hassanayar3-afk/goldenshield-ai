"""نماذج الأوامر."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Order:
    symbol: str
    side: OrderSide
    amount: float
    order_type: OrderType = OrderType.MARKET
    price: float | None = None
    id: str = field(default_factory=lambda: f"ord-{uuid4().hex[:12]}")
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=_utc_now)
    filled_at: datetime | None = None
    fill_price: float | None = None
    is_paper: bool = True
    # —— طبقة حماية v1.1.2+ (اختيارية، لا تكسر النماذج القديمة) ——
    protective_sl: float | None = None
    protective_tp: float | None = None
    stops_confirmed: bool = False

    @property
    def is_active(self) -> bool:
        return self.status in {OrderStatus.PENDING, OrderStatus.OPEN}

    def mark_filled(self, fill_price: float) -> None:
        self.status = OrderStatus.FILLED
        self.fill_price = fill_price
        self.filled_at = _utc_now()

    def mark_cancelled(self) -> None:
        self.status = OrderStatus.CANCELLED

    def mark_rejected(self) -> None:
        self.status = OrderStatus.REJECTED
