"""كشف الفخاخ — تبريد زوج بعد سلسلة فشلات ظلّية."""

from __future__ import annotations

import logging

from intelligence.cognitive_config import trap_cooldown_minutes, trap_fail_streak
from intelligence.shadow_store import ShadowStore

logger = logging.getLogger(__name__)


def evaluate_traps_after_fail(
    *,
    symbol: str,
    pattern_key: str,
    store: ShadowStore | None = None,
    alerts=None,
) -> bool:
    """يعيد True إذا فُعّل تبريد على الزوج."""
    try:
        db = store or ShadowStore()
        streak = db.recent_fail_streak(symbol, pattern_key)
        need = trap_fail_streak()
        if streak < need:
            return False
        minutes = trap_cooldown_minutes()
        reason = (
            f"Trap Detection: {streak} فشل ظلّي متتالٍ للنمط {pattern_key} "
            f"— تبريد {minutes} دقيقة"
        )
        until = db.set_cooldown(symbol, minutes=minutes, reason=reason)
        logger.warning("%s until=%s", reason, until)
        if alerts is not None:
            try:
                from operations.alert_dispatcher import AlertLevel

                alerts.dispatch(AlertLevel.WARNING, f"تبريد {symbol}", reason)
            except Exception as exc:  # noqa: BLE001
                logger.debug("trap telegram: %s", exc)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_traps_after_fail: %s", exc)
        return False
