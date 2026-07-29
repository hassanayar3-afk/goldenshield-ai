"""سجل الرموز — عملات، أسهم، فوركس مع صلاحيات إدارية كاملة."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from config.settings import BASE_DIR, CONFIG_DIR

logger = logging.getLogger(__name__)

REGISTRY_PATH = CONFIG_DIR / "symbol_registry.yaml"
MAP_PATH = CONFIG_DIR / "mt5_symbol_map.yaml"


@dataclass(frozen=True)
class SymbolSpec:
    id: str
    category: str
    data_source: str
    mt5_symbol: str | None = None
    yfinance_ticker: str | None = None
    enabled: bool = True

    @property
    def is_crypto(self) -> bool:
        return self.category == "crypto" or "/" in self.id and not self.id.startswith(("STOCK/", "FOREX/"))


class SymbolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, SymbolSpec] = {}
        self._mt5_map: dict[str, str] = {}
        self._reload_maps()

    @staticmethod
    def _forex_yfinance_ticker(pair: str) -> str:
        clean = pair.upper().replace("FOREX/", "").replace("/", "").replace("-", "")
        from data.symbol_routing import _COMMODITY_CANONICAL

        clean = _COMMODITY_CANONICAL.get(clean, clean)
        commodity_yf = {
            "XAUUSD": "GC=F",
            "XAGUSD": "SI=F",
            "USOIL": "CL=F",
            "UKOIL": "BZ=F",
        }
        if clean in commodity_yf:
            return commodity_yf[clean]
        return f"{clean}=X"

    def _reload_maps(self) -> None:
        if MAP_PATH.exists():
            raw = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8")) or {}
            for pair, mt5 in (raw.get("crypto") or {}).items():
                self._mt5_map[str(pair)] = str(mt5)
            for pair, mt5 in (raw.get("forex") or {}).items():
                self._mt5_map[str(pair)] = str(mt5)
            for pair, ticker in (raw.get("stocks") or {}).items():
                self._mt5_map[str(pair)] = str(ticker)

    def load(self, base_pairs: list[str] | None = None) -> list[str]:
        self._specs.clear()
        self._reload_maps()

        for pair in base_pairs or []:
            from data.symbol_routing import infer_data_source, normalize_symbol_id

            sid = normalize_symbol_id(pair)
            source = infer_data_source(sid)
            if source == "forex" or sid.startswith("FOREX/"):
                self._specs[sid] = SymbolSpec(
                    id=sid,
                    category="forex",
                    data_source="forex",
                    mt5_symbol=self._mt5_map.get(sid) or sid.split("/", 1)[-1],
                    yfinance_ticker=self._forex_yfinance_ticker(sid),
                    enabled=True,
                )
            elif source == "yfinance" or sid.startswith("STOCK/"):
                ticker = sid.split("/", 1)[-1]
                self._specs[sid] = SymbolSpec(
                    id=sid,
                    category="stock",
                    data_source="yfinance",
                    yfinance_ticker=ticker,
                    mt5_symbol=self._guess_mt5_stock(ticker),
                    enabled=True,
                )
            else:
                self._specs[sid] = SymbolSpec(
                    id=sid,
                    category="crypto",
                    data_source="binance",
                    mt5_symbol=self._mt5_map.get(sid),
                    enabled=True,
                )

        for pair, mt5 in self._mt5_map.items():
            # لا تحقن فوركس/أسهم تلقائياً إلا إذا كان MT5 مفعّلاً
            from config.settings import get_settings

            if not bool(getattr(get_settings(), "mt5_enabled", False)):
                break
            if pair.startswith("FOREX/"):
                self._ensure(
                    SymbolSpec(
                        id=pair,
                        category="forex",
                        data_source="forex",
                        mt5_symbol=mt5,
                        yfinance_ticker=self._forex_yfinance_ticker(pair),
                        enabled=True,
                    )
                )
            elif pair.startswith("STOCK/"):
                ticker = mt5
                enable_stocks = get_settings().bot_admin_full_access
                self._ensure(
                    SymbolSpec(
                        id=pair,
                        category="stock",
                        data_source="yfinance",
                        yfinance_ticker=ticker,
                        mt5_symbol=self._guess_mt5_stock(ticker),
                        enabled=enable_stocks,
                    )
                )

        if REGISTRY_PATH.exists():
            raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
            for item in raw.get("symbols") or []:
                spec = self._spec_from_dict(item)
                if spec is not None:
                    self._ensure(spec)

        active = self.active_pairs()
        logger.info("Symbol registry: %s active symbol(s)", len(active))
        return active

    def _ensure(self, spec: SymbolSpec) -> None:
        existing = self._specs.get(spec.id)
        if existing is None:
            self._specs[spec.id] = spec
            return
        if existing.enabled and not spec.enabled:
            return
        self._specs[spec.id] = spec

    def _spec_from_dict(self, item: dict[str, Any]) -> SymbolSpec | None:
        symbol_id = str(item.get("id", "")).strip()
        if not symbol_id:
            return None
        category = str(item.get("category", "crypto"))
        data_source = str(item.get("data_source", "binance"))
        yfinance_ticker = item.get("yfinance_ticker")
        if category == "forex":
            data_source = "forex"
            if not yfinance_ticker:
                yfinance_ticker = self._forex_yfinance_ticker(symbol_id)
        return SymbolSpec(
            id=symbol_id,
            category=category,
            data_source=data_source,
            mt5_symbol=item.get("mt5_symbol"),
            yfinance_ticker=yfinance_ticker,
            enabled=bool(item.get("enabled", True)),
        )

    def get(self, symbol_id: str) -> SymbolSpec | None:
        return self._specs.get(symbol_id)

    def active_pairs(self) -> list[str]:
        return sorted(spec.id for spec in self._specs.values() if spec.enabled)

    def all_specs(self) -> list[SymbolSpec]:
        return sorted(self._specs.values(), key=lambda s: s.id)

    def mt5_symbol_for(self, symbol_id: str) -> str:
        spec = self._specs.get(symbol_id)
        if spec and spec.mt5_symbol:
            return spec.mt5_symbol
        return self._mt5_map.get(symbol_id, symbol_id.replace("/", ""))

    def add_crypto(self, pair: str, *, mt5_symbol: str | None = None, enabled: bool = True) -> bool:
        pair = pair.upper().replace("-", "/")
        if "/" not in pair:
            pair = f"{pair}/USDT"
        mt5 = mt5_symbol or self._mt5_map.get(pair) or pair.replace("/", "")
        self._ensure(
            SymbolSpec(
                id=pair,
                category="crypto",
                data_source="binance",
                mt5_symbol=mt5,
                enabled=enabled,
            )
        )
        self._mt5_map[pair] = mt5
        self._persist_extra(pair)
        return True

    def add_forex(self, pair: str, *, mt5_symbol: str | None = None, enabled: bool = True) -> bool:
        from data.symbol_routing import _COMMODITY_CANONICAL, normalize_symbol_id

        clean = pair.upper().replace("FOREX/", "").replace("/", "").replace("-", "")
        clean = _COMMODITY_CANONICAL.get(clean, clean)
        symbol_id = normalize_symbol_id(f"FOREX/{clean}")
        default_mt5 = {
            "XAUUSD": "GOLD",
            "XAGUSD": "SILVER",
            "USOIL": "USOIL",
            "UKOIL": "UKOIL",
        }.get(clean, clean)
        mt5 = mt5_symbol or self._mt5_map.get(symbol_id) or default_mt5
        self._ensure(
            SymbolSpec(
                id=symbol_id,
                category="forex",
                data_source="forex",
                mt5_symbol=mt5,
                yfinance_ticker=self._forex_yfinance_ticker(symbol_id),
                enabled=enabled,
            )
        )
        self._mt5_map[symbol_id] = mt5
        self._persist_extra(symbol_id)
        return True

    def add_stock(self, ticker: str, *, mt5_symbol: str | None = None, enabled: bool = True) -> bool:
        ticker = ticker.upper().strip().lstrip("#")
        symbol_id = f"STOCK/{ticker}"
        mt5 = mt5_symbol or self._guess_mt5_stock(ticker)
        self._ensure(
            SymbolSpec(
                id=symbol_id,
                category="stock",
                data_source="yfinance",
                yfinance_ticker=ticker,
                mt5_symbol=mt5,
                enabled=enabled,
            )
        )
        self._mt5_map[symbol_id] = mt5
        self._persist_extra(symbol_id)
        return True

    def remove(self, symbol_id: str) -> bool:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return False
        self._specs[symbol_id] = SymbolSpec(
            id=spec.id,
            category=spec.category,
            data_source=spec.data_source,
            mt5_symbol=spec.mt5_symbol,
            yfinance_ticker=spec.yfinance_ticker,
            enabled=False,
        )
        self._persist_disable(symbol_id)
        return True

    def sync_from_mt5(self) -> list[str]:
        try:
            from execution.mt5_bridge import get_mt5_bridge

            bridge = get_mt5_bridge()
            discovered = bridge.discover_tradeable_symbols()
        except Exception:
            logger.exception("فشل مزامنة MT5")
            return []

        added: list[str] = []
        for item in discovered:
            kind = item["kind"]
            symbol_id = item["id"]
            if symbol_id in self._specs and self._specs[symbol_id].enabled:
                continue
            if kind == "crypto":
                self.add_crypto(symbol_id, mt5_symbol=item["mt5"], enabled=True)
                added.append(symbol_id)
            elif kind == "forex":
                self.add_forex(symbol_id.replace("FOREX/", ""), mt5_symbol=item["mt5"], enabled=True)
                added.append(symbol_id)
        if added:
            logger.info("MT5 sync added: %s", ", ".join(added))
        return added

    def _guess_mt5_stock(self, ticker: str) -> str:
        return f"#{ticker}"

    def _persist_extra(self, symbol_id: str) -> None:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return
        raw = self._read_registry_file()
        symbols: list[dict[str, Any]] = list(raw.get("symbols") or [])
        symbols = [s for s in symbols if str(s.get("id")) != symbol_id]
        symbols.append(
            {
                "id": spec.id,
                "category": spec.category,
                "data_source": spec.data_source,
                "mt5_symbol": spec.mt5_symbol,
                "yfinance_ticker": spec.yfinance_ticker,
                "enabled": spec.enabled,
            }
        )
        raw["symbols"] = symbols
        self._write_registry_file(raw)

    def _persist_disable(self, symbol_id: str) -> None:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return
        raw = self._read_registry_file()
        symbols: list[dict[str, Any]] = list(raw.get("symbols") or [])
        updated = False
        for item in symbols:
            if str(item.get("id")) == symbol_id:
                item["enabled"] = False
                updated = True
        if not updated:
            symbols.append(
                {
                    "id": spec.id,
                    "category": spec.category,
                    "data_source": spec.data_source,
                    "mt5_symbol": spec.mt5_symbol,
                    "yfinance_ticker": spec.yfinance_ticker,
                    "enabled": False,
                }
            )
        raw["symbols"] = symbols
        self._write_registry_file(raw)

    def _read_registry_file(self) -> dict[str, Any]:
        if not REGISTRY_PATH.exists():
            return {"auto_sync_mt5": True, "admin_full_access": True, "symbols": []}
        return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}

    def _write_registry_file(self, raw: dict[str, Any]) -> None:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


_registry: SymbolRegistry | None = None


def get_symbol_registry() -> SymbolRegistry:
    global _registry
    if _registry is None:
        _registry = SymbolRegistry()
    return _registry


def reset_symbol_registry() -> None:
    global _registry
    _registry = None
