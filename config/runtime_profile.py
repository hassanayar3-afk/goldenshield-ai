"""بروفايل تشغيل موحّد — Binance فقط (مسار MetaTrader ملغى)."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings, get_settings


@dataclass(frozen=True)
class RuntimeProfile:
    """مصدر الحقيقة الواحد لكل دورة تشغيل."""

    execution_backend: str  # binance
    execution_mode: str  # paper | live
    uses_mt5: bool
    heartbeat_provider: str  # binance
    requires_binance_ping: bool
    label: str


def resolve_runtime_profile(settings: Settings | None = None) -> RuntimeProfile:
    s = settings or get_settings()
    # MetaTrader ملغى بالكامل — التنفيذ عبر Binance فقط
    backend = "binance"
    return RuntimeProfile(
        execution_backend=backend,
        execution_mode=s.execution_mode,
        uses_mt5=False,
        heartbeat_provider="binance",
        requires_binance_ping=True,
        label=f"{backend}/{s.execution_mode}",
    )


def get_runtime_profile() -> RuntimeProfile:
    return resolve_runtime_profile()


def active_runtime_label() -> str:
    return resolve_runtime_profile().label


def is_crypto_symbol(symbol: str) -> bool:
    s = (symbol or "").strip().upper()
    if not s or s.startswith("FOREX/") or s.startswith("STOCK/"):
        return False
    return "/" in s


def uses_binance_orderbook(symbol: str) -> bool:
    """Order book من Binance للكريبتو فقط."""
    return is_crypto_symbol(symbol)
