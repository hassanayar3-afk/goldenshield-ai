"""اختبارات سجل الرموز وصلاحيات الإدارة."""

from __future__ import annotations

import yaml

from operations.bot_admin import can_control_bot
from operations.symbol_registry import SymbolRegistry


def test_add_crypto_and_list(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    map_path = tmp_path / "mt5_symbol_map.yaml"
    map_path.write_text(
        yaml.safe_dump({"crypto": {"DOGE/USDT": "DOGEUSD"}, "forex": {}, "stocks": {}}),
        encoding="utf-8",
    )
    registry_path.write_text(
        yaml.safe_dump({"auto_sync_mt5": True, "admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)
    monkeypatch.setattr("operations.symbol_registry.MAP_PATH", map_path)

    registry = SymbolRegistry()
    registry.load(["BTC/USDT"])
    registry.add_crypto("DOGE/USDT", enabled=True)

    assert "DOGE/USDT" in registry.active_pairs()
    saved = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert any(s["id"] == "DOGE/USDT" for s in saved["symbols"])


def test_add_forex_uses_multi_source(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    map_path = tmp_path / "mt5_symbol_map.yaml"
    map_path.write_text(
        yaml.safe_dump(
            {"crypto": {}, "forex": {"FOREX/EURUSD": "EURUSD"}, "stocks": {}}
        ),
        encoding="utf-8",
    )
    registry_path.write_text(
        yaml.safe_dump({"auto_sync_mt5": True, "admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)
    monkeypatch.setattr("operations.symbol_registry.MAP_PATH", map_path)

    registry = SymbolRegistry()
    registry.load([])
    spec = registry.get("FOREX/EURUSD")
    assert spec is not None
    assert spec.data_source == "forex"
    assert spec.yfinance_ticker == "EURUSD=X"
    assert spec.mt5_symbol == "EURUSD"


def test_commodities_gold_silver_oil_in_registry(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    map_path = tmp_path / "mt5_symbol_map.yaml"
    map_path.write_text(
        yaml.safe_dump(
            {
                "crypto": {},
                "forex": {
                    "FOREX/XAUUSD": "GOLD",
                    "FOREX/XAGUSD": "SILVER",
                    "FOREX/USOIL": "USOIL",
                },
                "stocks": {},
            }
        ),
        encoding="utf-8",
    )
    registry_path.write_text(
        yaml.safe_dump({"auto_sync_mt5": True, "admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)
    monkeypatch.setattr("operations.symbol_registry.MAP_PATH", map_path)

    registry = SymbolRegistry()
    registry.load(["FOREX/XAUUSD", "FOREX/XAGUSD", "FOREX/USOIL"])
    gold = registry.get("FOREX/XAUUSD")
    assert gold is not None
    assert gold.mt5_symbol == "GOLD"
    assert gold.yfinance_ticker == "GC=F"
    silver = registry.get("FOREX/XAGUSD")
    assert silver is not None
    assert silver.mt5_symbol == "SILVER"
    oil = registry.get("FOREX/USOIL")
    assert oil is not None
    assert oil.yfinance_ticker == "CL=F"


def test_add_stock_uses_yfinance_source(tmp_path, monkeypatch):
    registry_path = tmp_path / "symbol_registry.yaml"
    map_path = tmp_path / "mt5_symbol_map.yaml"
    map_path.write_text(yaml.safe_dump({"crypto": {}, "forex": {}, "stocks": {}}), encoding="utf-8")
    registry_path.write_text(
        yaml.safe_dump({"auto_sync_mt5": True, "admin_full_access": True, "symbols": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("operations.symbol_registry.REGISTRY_PATH", registry_path)
    monkeypatch.setattr("operations.symbol_registry.MAP_PATH", map_path)

    registry = SymbolRegistry()
    registry.load([])
    registry.add_stock("AAPL", enabled=True)
    spec = registry.get("STOCK/AAPL")
    assert spec is not None
    assert spec.data_source == "yfinance"
    assert spec.enabled is True


def test_admin_can_control(monkeypatch):
    class S:
        telegram_chat_id = "1066554702"
        bot_admin_full_access = True

    monkeypatch.setattr("operations.bot_admin.get_settings", lambda: S())
    monkeypatch.setattr("operations.bot_admin.os.getenv", lambda k, d="": "1066554702" if k == "TELEGRAM_ADMIN_IDS" else d)
    assert can_control_bot("1066554702") is True
    assert can_control_bot("999") is False
