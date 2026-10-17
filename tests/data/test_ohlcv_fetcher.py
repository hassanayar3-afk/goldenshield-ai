import time
from unittest.mock import patch

import pytest

from core.constants import ANALYSIS_TIMEFRAMES, TIMEFRAMES
from data.cache_manager import CacheManager, reset_cache_manager
from data.connection_monitor import ConnectionMonitor
from data.exchange_client import reset_exchange
from data.ohlcv_fetcher import OHLCVFetcher
from data.volume_profile import calculate_volume_profile, point_of_control
from data.models.candle import Candle


@pytest.fixture(autouse=True)
def reset_data_layer():
    reset_exchange()
    reset_cache_manager()
    yield
    reset_exchange()
    reset_cache_manager()


@pytest.mark.integration
def test_fetch_ohlcv_m15_h1_h4():
    fetcher = OHLCVFetcher()
    symbol = "BTC/USDT"

    for timeframe in TIMEFRAMES:
        candles = fetcher.fetch(symbol, timeframe, limit=10, use_cache=False)
        assert len(candles) >= 5
        assert all(isinstance(c, Candle) for c in candles)
        assert candles[-1].close > 0


@pytest.mark.integration
def test_fetch_ohlcv_multi():
    fetcher = OHLCVFetcher()
    result = fetcher.fetch_multi("ETH/USDT", limit=5, use_cache=False)

    assert set(result.keys()) == set(ANALYSIS_TIMEFRAMES)
    for timeframe, candles in result.items():
        assert len(candles) >= 1, timeframe
        assert candles[0].open > 0


@pytest.mark.integration
def test_ohlcv_cache_reduces_duplicate_reads():
    fetcher = OHLCVFetcher(cache_ttl_seconds=60)
    symbol = "BNB/USDT"

    first = fetcher.fetch(symbol, "1h", limit=5, use_cache=True)
    second = fetcher.fetch(symbol, "1h", limit=5, use_cache=True)

    assert first is second


def test_volume_profile_calculation():
    candles = [
        Candle(timestamp=1, open=100, high=110, low=90, close=105, volume=1000),
        Candle(timestamp=2, open=105, high=115, low=100, close=110, volume=2000),
        Candle(timestamp=3, open=110, high=120, low=105, close=115, volume=1500),
    ]

    profile = calculate_volume_profile(candles, num_bins=5)
    assert len(profile) >= 1

    poc = point_of_control(profile)
    assert poc is not None
    assert poc[1] > 0


def test_connection_monitor_success_and_disconnect():
    monitor = ConnectionMonitor(timeout_seconds=30)

    with patch("data.connection_monitor.ping_exchange", return_value=1234567890):
        assert monitor.heartbeat() is True
        assert monitor.is_connected() is True

    with patch("data.connection_monitor.time.monotonic", return_value=1000.0):
        monitor.record_success()

    with patch("data.connection_monitor.time.monotonic", return_value=1030.0):
        assert monitor.is_connected() is True

    with patch("data.connection_monitor.time.monotonic", return_value=1031.0):
        assert monitor.is_disconnected() is True


def test_connection_monitor_heartbeat_failure():
    monitor = ConnectionMonitor(timeout_seconds=30)

    with patch(
        "data.connection_monitor.ping_exchange",
        side_effect=Exception("network down"),
    ):
        assert monitor.heartbeat() is False
        assert monitor.last_error == "network down"


def test_cache_manager_ttl_expiry():
    cache = CacheManager(default_ttl_seconds=1)
    cache.set("key", "value")

    assert cache.get("key") == "value"

    time.sleep(1.1)
    assert cache.get("key") is None
