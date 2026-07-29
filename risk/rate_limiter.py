"""سقف العمليات — حد أقصى لعدد الصفقات في الساعة."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class RateLimiterResult:
    allowed: bool
    reason: str
    trades_last_hour: int
    max_per_hour: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def prune_open_timestamps(
    timestamps: list[datetime],
    *,
    window_hours: float = 1.0,
    now: datetime | None = None,
) -> list[datetime]:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(hours=window_hours)
    cleaned: list[datetime] = []
    for ts in timestamps:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            cleaned.append(ts)
    return cleaned


def check_rate_limit(
    open_timestamps: list[datetime],
    *,
    max_per_hour: int,
    now: datetime | None = None,
) -> RateLimiterResult:
    current = now or _utc_now()
    recent = prune_open_timestamps(open_timestamps, window_hours=1.0, now=current)
    count = len(recent)
    if count >= max_per_hour:
        return RateLimiterResult(
            allowed=False,
            reason=f"سقف الساعة: {count}/{max_per_hour} صفقات",
            trades_last_hour=count,
            max_per_hour=max_per_hour,
        )
    return RateLimiterResult(
        allowed=True,
        reason=f"صفقات الساعة: {count}/{max_per_hour}",
        trades_last_hour=count,
        max_per_hour=max_per_hour,
    )
