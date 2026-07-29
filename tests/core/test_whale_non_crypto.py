from unittest.mock import MagicMock, patch

from core.liquidity.whale_tracker import track_whales


def test_track_whales_skips_orderbook_for_forex():
    with patch("data.orderbook_fetcher.OrderBookFetcher.fetch") as fetch:
        result = track_whales("FOREX/EURUSD")
        fetch.assert_not_called()
        assert result.has_whale_support is True
        assert result.has_whale_resistance is True
        assert "فوركس" in result.reason or "أسهم" in result.reason


def test_track_whales_skips_orderbook_for_stock():
    with patch("data.orderbook_fetcher.OrderBookFetcher.fetch") as fetch:
        result = track_whales("STOCK/AAPL")
        fetch.assert_not_called()
        assert result.has_whale_support is True
        assert result.has_whale_resistance is True
