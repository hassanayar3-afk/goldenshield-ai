from datetime import datetime, timezone

from core.fundamental.news_fetcher import EconomicEvent, NewsImpact
from core.fundamental.news_filter import check_news_filter


def test_news_filter_blocks_before_high_impact():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    event = EconomicEvent(
        name="FOMC",
        impact=NewsImpact.HIGH,
        scheduled_utc=datetime(2026, 7, 15, 12, 4, tzinfo=timezone.utc),
    )

    result = check_news_filter(now=now, events=[event])
    assert result.trading_allowed is False
    assert result.blocking_event is not None


def test_news_filter_allows_outside_blackout():
    now = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
    event = EconomicEvent(
        name="FOMC",
        impact=NewsImpact.HIGH,
        scheduled_utc=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    )

    result = check_news_filter(now=now, events=[event])
    assert result.trading_allowed is True


def test_news_filter_ignores_medium_impact():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    event = EconomicEvent(
        name="Minor Data",
        impact=NewsImpact.MEDIUM,
        scheduled_utc=datetime(2026, 7, 15, 12, 1, tzinfo=timezone.utc),
    )

    result = check_news_filter(now=now, events=[event])
    assert result.trading_allowed is True
