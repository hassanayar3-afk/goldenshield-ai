from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.settings import get_settings
from core.fundamental.news_fetcher import EconomicEvent, NewsImpact, fetch_economic_events


@dataclass(frozen=True)
class NewsFilterResult:
    trading_allowed: bool
    reason: str
    blocking_event: EconomicEvent | None


def check_news_filter(
    *,
    now: datetime | None = None,
    events: list[EconomicEvent] | None = None,
    blackout_minutes: int | None = None,
) -> NewsFilterResult:
    settings = get_settings()

    if not settings.news_filter_enabled:
        return NewsFilterResult(
            trading_allowed=True,
            reason="فلتر الأخبار معطّل",
            blocking_event=None,
        )

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    minutes = (
        blackout_minutes
        if blackout_minutes is not None
        else settings.news_blackout_minutes
    )
    blackout = timedelta(minutes=minutes)
    event_list = events if events is not None else fetch_economic_events()

    for event in event_list:
        if event.impact != NewsImpact.HIGH:
            continue

        window_start = event.scheduled_utc - blackout
        window_end = event.scheduled_utc + blackout

        if window_start <= current_time <= window_end:
            return NewsFilterResult(
                trading_allowed=False,
                reason=(
                    f"خبر High Impact قريب: {event.name} "
                    f"({minutes} دقيقة)"
                ),
                blocking_event=event,
            )

    return NewsFilterResult(
        trading_allowed=True,
        reason="لا أخبار High Impact قريبة",
        blocking_event=None,
    )
