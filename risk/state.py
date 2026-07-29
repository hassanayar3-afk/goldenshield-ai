"""حالة المخاطر المشتركة."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RiskState:
    session_start_balance: float
    current_balance: float
    daily_trades: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    daily_profit: float = 0.0
    daily_loss: float = 0.0
    cooldown_until: datetime | None = None
    kill_switch_active: bool = False
    hc_daily_trades: int = 0
    hc_consecutive_wins: int = 0
    hc_last_trade_at: datetime | None = None
    # سيطرة: timestamps لفتح الصفقات خلال الساعة + تهدئة بعد الإغلاق
    trade_open_timestamps: list[datetime] = field(default_factory=list)
    post_trade_cooldown_until: datetime | None = None
    last_updated: datetime = field(default_factory=_utc_now)

    @property
    def daily_pnl_pct(self) -> float:
        if self.session_start_balance <= 0:
            return 0.0
        return ((self.current_balance - self.session_start_balance) / self.session_start_balance) * 100

    @property
    def daily_net_pnl(self) -> float:
        return self.daily_profit - self.daily_loss

    def record_trade(self, pnl: float) -> None:
        self.current_balance += pnl
        self.daily_trades += 1
        self.last_updated = _utc_now()

        if pnl >= 0:
            self.daily_profit += pnl
            self.consecutive_losses = 0
            self.consecutive_wins += 1
        else:
            self.daily_loss += abs(pnl)
            self.consecutive_losses += 1
            self.consecutive_wins = 0

    def record_trade_open(self, when: datetime | None = None) -> None:
        ts = when or _utc_now()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self.trade_open_timestamps.append(ts)
        self.last_updated = _utc_now()

    def reset_daily(self, balance: float) -> None:
        self.session_start_balance = balance
        self.current_balance = balance
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.cooldown_until = None
        self.kill_switch_active = False
        self.hc_daily_trades = 0
        self.hc_consecutive_wins = 0
        self.hc_last_trade_at = None
        self.trade_open_timestamps = []
        self.post_trade_cooldown_until = None
        self.last_updated = _utc_now()
