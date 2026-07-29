"""بروفايل تشغيل موحّد — قرار واحد للخلفية / النبض / السيولة بدون حذف المسارات القديمة."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings, get_settings


@dataclass(frozen=True)
class RuntimeProfile:
    """مصدر الحقيقة الواحد لكل دورة تشغيل."""

    execution_backend: str  # mt5 | binance
    execution_mode: str  # paper | live
    uses_mt5: bool
    heartbeat_provider: str  # mt5 | binance
    requires_binance_ping: bool
    label: str


def resolve_runtime_profile(settings: Settings | None = None) -> RuntimeProfile:
    s = settings or get_settings()
    backend = (s.execution_backend or "binance").strip().lower()
    if backend not in {"mt5", "binance"}:
        backend = "binance"

    # EXECUTION_BACKEND=binance صراحةً → مسار Binance فقط (لا يُسحب إلى MT5)
    if backend == "binance":
        uses_mt5 = False
    else:
        uses_mt5 = bool(s.mt5_enabled or backend == "mt5")
        if uses_mt5:
            backend = "mt5"

    heartbeat = "mt5" if uses_mt5 else "binance"
    return RuntimeProfile(
        execution_backend=backend,
        execution_mode=s.execution_mode,
        uses_mt5=uses_mt5,
        heartbeat_provider=heartbeat,
        requires_binance_ping=not uses_mt5,
        label=f"{backend}/{s.execution_mode}",
    )


def get_runtime_profile() -> RuntimeProfile:
    return resolve_runtime_profile()


def is_crypto_symbol(symbol: str) -> bool:
    """هل الرمز يعتمد دفتر أوامر Binance لتحليل السيولة؟"""
    if symbol.startswith("FOREX/") or symbol.startswith("STOCK/"):
        return False
    try:
        from operations.symbol_registry import get_symbol_registry

        spec = get_symbol_registry().get(symbol)
        if spec is not None:
            return bool(spec.is_crypto)
    except Exception:
        pass
    return "/" in symbol and not symbol.startswith(("FOREX/", "STOCK/"))


def uses_binance_orderbook(symbol: str) -> bool:
    return is_crypto_symbol(symbol)
