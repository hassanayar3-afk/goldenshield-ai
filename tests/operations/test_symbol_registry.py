"""اختبارات سجل الرموز — Binance كريبتو فقط."""

from __future__ import annotations

import yaml

from operations.bot_admin import can_control_bot
from operations.symbol_registry import SymbolRegistry


def test_add_crypto_and_list(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)

    registry = SymbolRegistry()
    registry.load(["BTC/USDT"])
    assert registry.add_crypto("DOGE/USDT", enabled=True) is True

    assert "DOGE/USDT" in registry.active_pairs()
    doge = registry.get("DOGE/USDT")
    assert doge is not None
    assert doge.data_source == "binance"
    assert doge.category == "crypto"
    saved = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert any(s["id"] == "DOGE/USDT" for s in saved["symbols"])
    assert all(s.get("data_source") == "binance" for s in saved["symbols"])


def test_rejects_forex_and_stock(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)

    registry = SymbolRegistry()
    registry.load(["FOREX/EURUSD", "BTC/USDT", "STOCK/AAPL", "XAUUSD"])
    assert registry.get("FOREX/EURUSD") is None
    assert registry.get("STOCK/AAPL") is None
    assert registry.get("XAUUSD") is None
    assert "BTC/USDT" in registry.active_pairs()
    assert registry.add_crypto("EURUSD") is False
    assert registry.add_crypto("AAPL") is False


def test_admin_can_control(monkeypatch):
    class S:
        telegram_chat_id = "1066554702"
        bot_admin_full_access = True

    monkeypatch.setattr("operations.bot_admin.get_settings", lambda: S())
    monkeypatch.setattr(
        "operations.bot_admin.os.getenv",
        lambda k, d="": "1066554702" if k == "TELEGRAM_ADMIN_IDS" else d,
    )
    assert can_control_bot("1066554702") is True
    assert can_control_bot("999") is False
