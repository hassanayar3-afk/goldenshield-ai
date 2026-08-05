from config.runtime_profile import (
    get_runtime_profile,
    is_crypto_symbol,
    resolve_runtime_profile,
    uses_binance_orderbook,
)
from config.settings import load_settings


def test_runtime_profile_ignores_mt5_backend(monkeypatch):
    """حتى لو طُلب MT5 في البيئة — التشغيل يبقى Binance فقط."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EXECUTION_BACKEND", "mt5")
    monkeypatch.setenv("MT5_ENABLED", "true")
    monkeypatch.setenv("BOT_AUTO_SYNC_MT5", "true")
    monkeypatch.setenv("MT5_ATTACH_SL_TP", "true")
    settings = load_settings("dev", reload=True)
    assert settings.execution_backend == "binance"
    assert not hasattr(settings, "mt5_enabled")
    assert not hasattr(settings, "mt5_attach_sl_tp")
    assert not hasattr(settings, "bot_auto_sync_mt5")
    profile = resolve_runtime_profile(settings)
    assert not hasattr(profile, "uses_mt5")
    assert profile.execution_backend == "binance"
    assert profile.heartbeat_provider == "binance"
    assert profile.requires_binance_ping is True
    assert "binance" in profile.label


def test_runtime_profile_binance_default(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("EXECUTION_BACKEND", raising=False)
    settings = load_settings("dev", reload=True)
    profile = resolve_runtime_profile(settings)
    assert profile.execution_backend == "binance"
    assert profile.heartbeat_provider == "binance"
    assert profile.requires_binance_ping is True


def test_forex_does_not_use_binance_orderbook():
    assert uses_binance_orderbook("FOREX/EURUSD") is False
    assert uses_binance_orderbook("STOCK/AAPL") is False
    assert is_crypto_symbol("BTC/USDT") is True
    assert is_crypto_symbol("FOREX/EURUSD") is False


def test_get_runtime_profile_uses_loaded_settings(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("EXECUTION_BACKEND", "binance")
    load_settings("dev", reload=True)
    profile = get_runtime_profile()
    assert profile.execution_backend == "binance"
