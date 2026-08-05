"""سجل الرموز — أزواج Binance كريبتو."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yaml

from config.settings import CONFIG_DIR

logger = logging.getLogger(__name__)

REGISTRY_PATH = CONFIG_DIR / "symbol_registry.yaml"


@dataclass(frozen=True)
class SymbolSpec:
    id: str
    category: str
    data_source: str
    yfinance_ticker: str | None = None
    enabled: bool = True

    @property
    def is_crypto(self) -> bool:
        return self.category == "crypto" or (
            "/" in self.id and not self.id.startswith(("STOCK/", "FOREX/"))
        )


class SymbolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, SymbolSpec] = {}

    def load(self, base_pairs: list[str] | None = None) -> list[str]:
        self._specs.clear()

        for pair in base_pairs or []:
            from data.symbol_routing import normalize_symbol_id

            sid = normalize_symbol_id(pair)
            if sid.startswith(("FOREX/", "STOCK/")):
                logger.info("تجاهل رمز غير كريبتو في السجل: %s", sid)
                continue
            self._specs[sid] = SymbolSpec(
                id=sid,
                category="crypto",
                data_source="binance",
                enabled=True,
            )

        if REGISTRY_PATH.exists():
            try:
                raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
                for item in raw.get("symbols") or []:
                    spec = self._spec_from_dict(item)
                    if spec is not None:
                        self._ensure(spec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("فشل قراءة symbol_registry.yaml: %s", exc)

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
        if symbol_id.startswith(("FOREX/", "STOCK/")):
            return None
        category = str(item.get("category", "crypto"))
        if category in {"forex", "stock"}:
            return None
        data_source = str(item.get("data_source", "binance") or "binance")
        if data_source in {"forex", "yfinance", "mt5", "stock"}:
            data_source = "binance"
        return SymbolSpec(
            id=symbol_id,
            category="crypto",
            data_source=data_source if data_source else "binance",
            yfinance_ticker=None,
            enabled=bool(item.get("enabled", True)),
        )

    def get(self, symbol_id: str) -> SymbolSpec | None:
        return self._specs.get(symbol_id)

    def active_pairs(self) -> list[str]:
        return sorted(spec.id for spec in self._specs.values() if spec.enabled)

    def all_specs(self) -> list[SymbolSpec]:
        return sorted(self._specs.values(), key=lambda s: s.id)

    def add_crypto(self, pair: str, *, enabled: bool = True) -> bool:
        pair = pair.upper().replace("-", "/")
        if "/" not in pair:
            pair = f"{pair}/USDT"
        self._ensure(
            SymbolSpec(
                id=pair,
                category="crypto",
                data_source="binance",
                enabled=enabled,
            )
        )
        self._persist_extra(pair)
        return True

    def add_forex(self, pair: str, *, enabled: bool = True) -> bool:
        """ملغى — Binance كريبتو فقط."""
        logger.info("add_forex ignored (%s) — Binance-only registry", pair)
        return False

    def add_stock(self, ticker: str, *, enabled: bool = True) -> bool:
        """ملغى — Binance كريبتو فقط."""
        logger.info("add_stock ignored (%s) — Binance-only registry", ticker)
        return False

    def remove(self, symbol_id: str) -> bool:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return False
        self._specs[symbol_id] = SymbolSpec(
            id=spec.id,
            category=spec.category,
            data_source=spec.data_source,
            yfinance_ticker=spec.yfinance_ticker,
            enabled=False,
        )
        self._persist_disable(symbol_id)
        return True

    def _persist_extra(self, symbol_id: str) -> None:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return
        try:
            raw = self._read_registry_file()
            symbols: list[dict[str, Any]] = list(raw.get("symbols") or [])
            symbols = [s for s in symbols if str(s.get("id")) != symbol_id]
            symbols.append(
                {
                    "id": spec.id,
                    "category": spec.category,
                    "data_source": spec.data_source,
                    "enabled": spec.enabled,
                }
            )
            raw["symbols"] = symbols
            raw.pop("auto_sync_mt5", None)
            self._write_registry_file(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل حفظ الرمز %s: %s", symbol_id, exc)

    def _persist_disable(self, symbol_id: str) -> None:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return
        try:
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
                        "enabled": False,
                    }
                )
            raw["symbols"] = symbols
            raw.pop("auto_sync_mt5", None)
            self._write_registry_file(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل تعطيل الرمز %s: %s", symbol_id, exc)

    def _read_registry_file(self) -> dict[str, Any]:
        if not REGISTRY_PATH.exists():
            return {"admin_full_access": True, "symbols": []}
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
