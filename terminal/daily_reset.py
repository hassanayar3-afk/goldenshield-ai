"""Clean-Slate Daily Reset — تصفير مؤشرات اليوم."""

from __future__ import annotations

import logging
from datetime import date

from terminal.module_breaker import daily_clean_slate_reset

logger = logging.getLogger(__name__)

_last_day: date | None = None


def maybe_run_daily_reset() -> bool:
    global _last_day
    today = date.today()
    if _last_day == today:
        return False
    _last_day = today
    try:
        daily_clean_slate_reset()
        logger.info("Daily clean-slate reset executed for %s", today.isoformat())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily reset failed: %s", exc)
        return False
