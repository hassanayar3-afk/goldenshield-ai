"""سجل الرموز — أزواج Binance كريبتو فقط."""

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
    enabled: bool = True

    @property
    def is_crypto(self) -> bool:
        return self.category == "crypto" and "/" in self.id


class SymbolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, SymbolSpec] = {}

    def load(self, base_pairs: list[str] | None = None) -> list[str]:
        self._specs.clear()

        for pair in base_pairs or []:
            from data.symbol_routing import is_binance_crypto_pair, normalize_symbol_id

            sid = normalize_symbol_id(pair)
            if not is_binance_crypto_pair(sid):
                logger.info("تجاهل رمز غير Binance: %s", sid)
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
        logger.info("Symbol registry: %s Binance pair(s)", len(active))
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
        from data.symbol_routing import is_binance_crypto_pair, normalize_symbol_id

        symbol_id = normalize_symbol_id(str(item.get("id", "")).strip())
        if not symbol_id or not is_binance_crypto_pair(symbol_id):
            return None
        return SymbolSpec(
            id=symbol_id,
            category="crypto",
            data_source="binance",
            enabled=bool(item.get("enabled", True)),
        )

    def get(self, symbol_id: str) -> SymbolSpec | None:
        return self._specs.get(symbol_id)

    def active_pairs(self) -> list[str]:
        return sorted(spec.id for spec in self._specs.values() if spec.enabled)

    def all_specs(self) -> list[SymbolSpec]:
        return sorted(self._specs.values(), key=lambda s: s.id)

    def add_crypto(self, pair: str, *, enabled: bool = True) -> bool:
        from data.symbol_routing import is_binance_crypto_pair, normalize_symbol_id

        raw = (pair or "").strip().upper().replace("-", "/")
        # لا تُلحق /USDT برموز فوركس/أسهم المعروفة
        candidate = normalize_symbol_id(raw)
        if "/" not in candidate and not candidate.endswith("USDT"):
            candidate = f"{candidate}/USDT"
        if not is_binance_crypto_pair(candidate):
            logger.info("رفض إضافة رمز غير Binance: %s", pair)
            return False
        self._ensure(
            SymbolSpec(
                id=candidate,
                category="crypto",
                data_source="binance",
                enabled=enabled,
            )
        )
        self._persist_extra(candidate)
        return True

    def remove(self, symbol_id: str) -> bool:
        spec = self._specs.get(symbol_id)
        if spec is None:
            return False
        self._specs[symbol_id] = SymbolSpec(
            id=spec.id,
            category="crypto",
            data_source="binance",
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
                    "category": "crypto",
                    "data_source": "binance",
                    "enabled": spec.enabled,
                }
            )
            raw["symbols"] = symbols
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
                    item["category"] = "crypto"
                    item["data_source"] = "binance"
                    updated = True
            if not updated:
                symbols.append(
                    {
                        "id": spec.id,
                        "category": "crypto",
                        "data_source": "binance",
                        "enabled": False,
                    }
                )
            raw["symbols"] = symbols
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
