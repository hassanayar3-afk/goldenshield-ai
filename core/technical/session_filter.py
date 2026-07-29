"""فلتر جلسات السيولة — Kill Zones (لندن / نيويورك / التداخل)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SessionFilterResult:
    allowed: bool
    session: str
    reason: str


# جلسات السيولة العالية (UTC تقريبي)
DEFAULT_KILL_ZONE_SESSIONS: tuple[str, ...] = (
    "london",
    "london_ny_overlap",
    "new_york",
)


def _hour_utc(now: datetime) -> int:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).hour


def detect_session(now: datetime | None = None) -> str:
    """
    تقويم تقريبي UTC:
    - لندن: 07–16
    - تداخل لندن/نيويورك: 12–16
    - نيويورك: 13–21
    """
    hour = _hour_utc(now or datetime.now(timezone.utc))
    if 12 <= hour < 16:
        return "london_ny_overlap"
    if 7 <= hour < 16:
        return "london"
    if 13 <= hour < 21:
        return "new_york"
    return "off_hours"


def check_session(
    *,
    allowed_sessions: tuple[str, ...] | None = None,
    now: datetime | None = None,
) -> SessionFilterResult:
    sessions = allowed_sessions or DEFAULT_KILL_ZONE_SESSIONS
    session = detect_session(now)
    if session in sessions:
        return SessionFilterResult(True, session, f"جلسة سيولة مسموحة: {session}")
    return SessionFilterResult(
        False,
        session,
        f"خارج Kill Zones — الجلسة الحالية: {session}",
    )


def check_kill_zones(
    *,
    enabled: bool = True,
    allowed_sessions: tuple[str, ...] | None = None,
    now: datetime | None = None,
) -> SessionFilterResult:
    """بوابة Kill Zones العامة لكل الدخول (عند التفعيل)."""
    if not enabled:
        return SessionFilterResult(
            True,
            detect_session(now),
            "Kill Zones معطّلة",
        )
    return check_session(allowed_sessions=allowed_sessions, now=now)
