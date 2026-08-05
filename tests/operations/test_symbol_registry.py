"""اختبارات سجل الرموز وصلاحيات الإدارة — Binance كريبتو فقط."""

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
    registry.add_crypto("DOGE/USDT", enabled=True)

    assert "DOGE/USDT" in registry.active_pairs()
    assert "BTC/USDT" in registry.active_pairs()
    doge = registry.get("DOGE/USDT")
    assert doge is not None
    assert doge.category == "crypto"
    assert doge.data_source == "binance"
    assert not hasattr(doge, "mt5_symbol")
    saved = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert any(s["id"] == "DOGE/USDT" for s in saved["symbols"])
    assert "auto_sync_mt5" not in saved


def test_forex_load_is_noop(tmp_path, monkeypatch):
    """FOREX يُتجاهل عند التحميل — السجل Binance-only."""
    registry_path = tmp_path / "symbol_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)

    registry = SymbolRegistry()
    registry.load(["FOREX/EURUSD", "BTC/USDT"])
    assert registry.get("FOREX/EURUSD") is None
    assert "FOREX/EURUSD" not in registry.active_pairs()
    assert "BTC/USDT" in registry.active_pairs()
    assert registry.add_forex("EURUSD") is False


def test_commodities_forex_ignored(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)

    registry = SymbolRegistry()
    registry.load(["FOREX/XAUUSD", "FOREX/XAGUSD", "FOREX/USOIL"])
    assert registry.active_pairs() == []
    assert registry.get("FOREX/XAUUSD") is None


def test_add_stock_is_noop(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)

    registry = SymbolRegistry()
    registry.load([])
    assert registry.add_stock("AAPL", enabled=True) is False
    assert registry.get("STOCK/AAPL") is None
    assert registry.active_pairs() == []


def test_admin_can_control(monkeypatch):
    class S:
        telegram_chat_id = "1066554702"
        bot_admin_full_access = True

    monkeypatch.setattr("operations.bot_admin.get_settings", lambda: S())
    monkeypatch.setattr("operations.bot_admin.os.getenv", lambda k, d="": "1066554702" if k == "TELEGRAM_ADMIN_IDS" else d)
    assert can_control_bot("1066554702") is True
    assert can_control_bot("999") is False
