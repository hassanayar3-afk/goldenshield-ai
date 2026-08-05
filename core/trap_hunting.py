# -*- coding: utf-8 -*-
"""اصطياد فخاخ الحيتان — طبقة مضافة فوق manipulation_guard / shadow traps."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrapHuntResult:
    approved: bool
    reason: str
    trap_type: str = "none"


_TRAP_KEYWORDS = (
    "stop hunt",
    "stoploss hunt",
    "false break",
    "fake break",
    "liquidity grab",
    "فخ",
    "اصطياد وقف",
    "اختراق كاذب",
    "manipulation",
    "spoof",
)


def evaluate_trap_hunt(
    *,
    symbol: str,
    signal: str,
    reasons: tuple[str, ...] | list[str] | None = None,
) -> TrapHuntResult:
    """يرفض الدخول إن دلّت الأسباب أو محرّك الظل على فخ حيتان نشط."""
    try:
        text_blob = " | ".join(str(r) for r in (reasons or ()))
        low = text_blob.lower()
        for kw in _TRAP_KEYWORDS:
            if kw in low:
                return TrapHuntResult(
                    False,
                    f"Veto فخ حيتان ({kw}) على {symbol}",
                    trap_type=kw,
                )

        # تبريد ظلّي إن وُجد
        try:
            from intelligence.shadow_stress_engine import symbol_is_cooled

            cooled, cool_reason = symbol_is_cooled(symbol)
            if cooled and signal in {"BUY SIGNAL", "SELL SIGNAL"}:
                return TrapHuntResult(False, cool_reason or "تبريد فخ ظلّي", "shadow_cool")
        except Exception:  # noqa: BLE001
            pass

        # طبقة manipulation_guard اختيارية إن توفرت دالة عامة
        try:
            from core.technical import manipulation_guard as mg

            detector = getattr(mg, "is_trap_environment", None) or getattr(
                mg, "detect_stop_hunt", None
            )
            if callable(detector):
                hit = detector(symbol) if detector.__code__.co_argcount >= 1 else detector()
                if hit:
                    return TrapHuntResult(False, f"manipulation_guard: {hit}", "manipulation")
        except Exception:  # noqa: BLE001
            pass

        return TrapHuntResult(True, "لا فخ حيتان مفعّل", "none")
    except Exception as exc:  # noqa: BLE001
        logger.warning("evaluate_trap_hunt: %s", exc)
        return TrapHuntResult(True, f"تخطي آمن لاصطياد الفخاخ: {exc}", "bypass")
