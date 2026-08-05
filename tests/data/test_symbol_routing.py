from data.symbol_routing import (
    display_symbol,
    format_price,
    infer_data_source,
    is_binance_crypto_pair,
    normalize_symbol_id,
)


def test_binance_pairs_only():
    assert infer_data_source("BTC/USDT") == "binance"
    assert infer_data_source("ETH/USDT") == "binance"
    assert is_binance_crypto_pair("BTC/USDT") is True


def test_non_binance_rejected():
    assert infer_data_source("FOREX/EURUSD") == "unsupported"
    assert infer_data_source("EURUSD") == "unsupported"
    assert infer_data_source("STOCK/AAPL") == "unsupported"
    assert infer_data_source("XAUUSD") == "unsupported"
    assert infer_data_source("GOLD") == "unsupported"
    assert is_binance_crypto_pair("FOREX/EURUSD") is False
    assert is_binance_crypto_pair("AAPL") is False


def test_display_and_normalize_crypto():
    assert display_symbol("BTC/USDT") == "BTC"
    assert normalize_symbol_id("btcusdt") == "BTC/USDT"
    assert format_price("BTC/USDT", 65000.5) == "65,000.50"
