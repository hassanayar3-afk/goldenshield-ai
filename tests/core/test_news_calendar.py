from core.fundamental.news_fetcher import fetch_economic_events
from core.fundamental.news_filter import check_news_filter
from datetime import timedelta


def test_fetch_economic_events_loads_calendar():
    events = fetch_economic_events()
    assert len(events) >= 1
    assert all(event.name for event in events)


def test_news_filter_blocks_with_calendar_event():
    events = fetch_economic_events()
    high_impact = next(e for e in events if e.impact.value == "high")
    now = high_impact.scheduled_utc - timedelta(minutes=2)
    result = check_news_filter(now=now, events=events)
    assert result.trading_allowed is False
    assert result.blocking_event is not None
