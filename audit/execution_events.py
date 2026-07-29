"""توثيق أحداث التنفيذ v1.1.2 — صفقات مرفوضة وتدخلات طارئة."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# سجل ذاكرة خفيف للدورة الحالية (لا يستبدل DecisionLogger)
_EXECUTION_EVENTS: list[dict[str, Any]] = []


def log_execution_event(
    event_type: str,
    *,
    symbol: str = "",
    reason: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """تسجيل أي صفقة مرفوضة أو تدخل طارئ مع السبب.

    لا يرمي استثناءات للحلقة الرئيسية.
    """
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "symbol": symbol,
        "reason": reason,
        "details": details or {},
    }
    try:
        _EXECUTION_EVENTS.append(record)
        # سقف الذاكرة
        if len(_EXECUTION_EVENTS) > 500:
            del _EXECUTION_EVENTS[:-400]
        logger.info(
            "execution_event type=%s symbol=%s reason=%s",
            event_type,
            symbol,
            reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_execution_event فشل: %s", exc)
    return record


def recent_execution_events(limit: int = 50) -> list[dict[str, Any]]:
    try:
        return list(_EXECUTION_EVENTS[-max(1, limit) :])
    except Exception:
        return []


def clear_execution_events() -> None:
    try:
        _EXECUTION_EVENTS.clear()
    except Exception:
        pass
