"""بروفايل تشغيل موحّد — Binance فقط."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings, get_settings


@dataclass(frozen=True)
class RuntimeProfile:
    """مصدر الحقيقة الواحد لكل دورة تشغيل."""

    execution_backend: str  # binance
    execution_mode: str  # paper | live
    heartbeat_provider: str  # binance
    requires_binance_ping: bool
    label: str


def resolve_runtime_profile(settings: Settings | None = None) -> RuntimeProfile:
    s = settings or get_settings()
    backend = "binance"
    return RuntimeProfile(
        execution_backend=backend,
        execution_mode=s.execution_mode,
        heartbeat_provider="binance",
        requires_binance_ping=True,
        label=f"{backend}/{s.execution_mode}",
    )


def get_runtime_profile() -> RuntimeProfile:
    return resolve_runtime_profile()


def active_runtime_label() -> str:
    return resolve_runtime_profile().label


def is_crypto_symbol(symbol: str) -> bool:
    from data.symbol_routing import is_binance_crypto_pair

    return is_binance_crypto_pair(symbol)


def uses_binance_orderbook(symbol: str) -> bool:
    """Order book من Binance للكريبتو فقط."""
    return is_crypto_symbol(symbol)
