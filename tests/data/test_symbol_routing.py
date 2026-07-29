from data.symbol_routing import (
    display_symbol,
    format_price,
    infer_data_source,
    normalize_symbol_id,
)


def test_forex_never_routes_to_binance():
    assert infer_data_source("FOREX/EURUSD") == "forex"
    assert infer_data_source("EURUSD") == "forex"
    assert infer_data_source("BTC/USDT") == "binance"
    assert infer_data_source("STOCK/AAPL") == "yfinance"


def test_display_symbol_not_forex_usdt():
    assert display_symbol("FOREX/EURUSD") == "EURUSD"
    assert display_symbol("BTC/USDT") == "BTC"
    assert display_symbol("STOCK/AAPL") == "AAPL"


def test_normalize_bare_forex():
    assert normalize_symbol_id("EURUSD") == "FOREX/EURUSD"


def test_normalize_commodities():
    assert normalize_symbol_id("XAUUSD") == "FOREX/XAUUSD"
    assert normalize_symbol_id("GOLD") == "FOREX/XAUUSD"
    assert normalize_symbol_id("SILVER") == "FOREX/XAGUSD"
    assert normalize_symbol_id("USOIL") == "FOREX/USOIL"
    assert infer_data_source("FOREX/XAUUSD") == "forex"
    assert display_symbol("FOREX/XAUUSD") == "XAUUSD"
    assert format_price("FOREX/XAUUSD", 2345.67) == "2,345.67"


def test_format_price_jpy():
    assert format_price("FOREX/USDJPY", 150.123) == "150.123"
