from config.runtime_profile import (
    get_runtime_profile,
    is_crypto_symbol,
    resolve_runtime_profile,
    uses_binance_orderbook,
)
from config.settings import load_settings


def test_runtime_profile_mt5_when_backend_mt5(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EXECUTION_BACKEND", "mt5")
    monkeypatch.setenv("MT5_ENABLED", "false")
    settings = load_settings("dev", reload=True)
    assert settings.mt5_enabled is True
    profile = resolve_runtime_profile(settings)
    assert profile.uses_mt5 is True
    assert profile.heartbeat_provider == "mt5"
    assert profile.requires_binance_ping is False


def test_runtime_profile_binance_default(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("EXECUTION_BACKEND", raising=False)
    monkeypatch.setenv("MT5_ENABLED", "false")
    settings = load_settings("dev", reload=True)
    profile = resolve_runtime_profile(settings)
    assert profile.heartbeat_provider == "binance"
    assert profile.requires_binance_ping is True


def test_forex_does_not_use_binance_orderbook():
    assert uses_binance_orderbook("FOREX/EURUSD") is False
    assert uses_binance_orderbook("STOCK/AAPL") is False
    assert is_crypto_symbol("BTC/USDT") is True


def test_runtime_profile_binance_backend_ignores_mt5_enabled(monkeypatch):
    """EXECUTION_BACKEND=binance يمنع سحب التنفيذ إلى MT5."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EXECUTION_BACKEND", "binance")
    monkeypatch.setenv("MT5_ENABLED", "true")
    settings = load_settings("dev", reload=True)
    profile = resolve_runtime_profile(settings)
    assert profile.uses_mt5 is False
    assert profile.execution_backend == "binance"
    assert profile.heartbeat_provider == "binance"


def test_get_runtime_profile_uses_loaded_settings(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EXECUTION_BACKEND", "binance")
    load_settings("dev", reload=True)
    profile = get_runtime_profile()
    assert profile.execution_backend == "binance"
