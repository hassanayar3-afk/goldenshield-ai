"""وضع الذعر الكلي (Panic Mode) — إيقاف Long عند ذعر السوق. طبقة مضافة OFF افتراضياً."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanicModeResult:
    allowed: bool
    reason: str
    panic: bool = False


def check_panic_mode(*, side: str = "buy") -> PanicModeResult:
    """في الذعر: يمنع الشراء (Long) فقط — لا يستبدل market_halt الحالي."""
    try:
        settings = get_settings()
        if not bool(getattr(settings, "market_correlation_filter_enabled", False)):
            return PanicModeResult(True, "Panic/Correlation Filter معطّل — تمرير")

        panic = _detect_panic()
        if not panic:
            return PanicModeResult(True, "لا ذعر سوقي ظاهر", False)

        block_long = bool(getattr(settings, "panic_mode_block_long", True))
        side_l = (side or "buy").lower()
        if block_long and side_l in {"buy", "long"}:
            return PanicModeResult(
                False,
                "Panic Mode: ذعر سوقي — إيقاف صفقات الشراء (Long)",
                True,
            )
        return PanicModeResult(True, "Panic Mode نشط لكن الصفقة ليست Long", True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("check_panic_mode فشل: %s", exc)
        return PanicModeResult(True, f"Panic Mode خطأ — تمرير آمن: {exc}")


def _detect_panic() -> bool:
    """يعتمد على الماكرو الموجود دون كسر المنطق الحالي."""
    try:
        from core.market_halt import check_market_halt

        halt = check_market_halt()
        if getattr(halt, "halted", False):
            return True
    except Exception:
        pass

    try:
        from core.macro.vix_monitor import check_vix

        vix = check_vix()
        if not getattr(vix, "is_safe", True):
            return True
    except Exception:
        pass
    return False
