"""فترة تهدئة عامة بعد كل صفقة — لإعادة التقييم."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class TradeCooldownResult:
    in_cooldown: bool
    reason: str
    cooldown_until: datetime | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def check_post_trade_cooldown(
    cooldown_until: datetime | None,
    *,
    now: datetime | None = None,
) -> TradeCooldownResult:
    if cooldown_until is None:
        return TradeCooldownResult(False, "لا توجد فترة تهدئة نشطة")

    current = now or _utc_now()
    until = cooldown_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    if current < until:
        return TradeCooldownResult(
            True,
            f"تهدئة بعد صفقة حتى {until.isoformat()}",
            until,
        )
    return TradeCooldownResult(False, "انتهت فترة التهدئة")


def compute_post_trade_cooldown_until(
    *,
    minutes: int,
    now: datetime | None = None,
) -> datetime:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current + timedelta(minutes=max(0, int(minutes)))
