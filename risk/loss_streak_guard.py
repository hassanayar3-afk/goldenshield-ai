"""راحة إجبارية 24 ساعة بعد 3 خسائر متتالية."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.settings import get_settings


@dataclass(frozen=True)
class LossStreakResult:
    in_cooldown: bool
    reason: str
    cooldown_until: datetime | None


def check_loss_streak(
    consecutive_losses: int,
    cooldown_until: datetime | None,
    *,
    now: datetime | None = None,
) -> LossStreakResult:
    settings = get_settings()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    if cooldown_until is not None:
        if current < cooldown_until:
            return LossStreakResult(
                in_cooldown=True,
                reason=f"راحة إجبارية حتى {cooldown_until.isoformat()}",
                cooldown_until=cooldown_until,
            )
        return LossStreakResult(
            in_cooldown=False,
            reason="انتهت فترة الراحة",
            cooldown_until=None,
        )

    if consecutive_losses >= settings.loss_streak_limit:
        until = current + timedelta(hours=settings.cooldown_hours)
        return LossStreakResult(
            in_cooldown=True,
            reason=(
                f"{consecutive_losses} خسائر متتالية — راحة {settings.cooldown_hours}h"
            ),
            cooldown_until=until,
        )

    return LossStreakResult(
        in_cooldown=False,
        reason="لا راحة إجبارية",
        cooldown_until=None,
    )
