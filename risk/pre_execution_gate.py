"""بوابة ما قبل التنفيذ v1.1.2 — Zero-SL Denial + Emergency ATR + Risk-Distance + R:R Lock."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings
from risk.emergency_protocols import (
    compute_emergency_atr_sl_tp,
    fetch_live_atr,
    lock_tp_to_rr,
    risk_distance_exceeds_cap,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreExecutionDecision:
    approved: bool
    stop_loss: float
    take_profit: float
    reason: str
    used_emergency_atr: bool = False
    atr_value: float | None = None


def _has_valid_sl_tp(entry: float, sl: float, tp: float, side: str) -> bool:
    if entry <= 0 or sl <= 0 or tp <= 0:
        return False
    side_l = (side or "buy").lower()
    if side_l in {"sell", "short"}:
        return sl > entry and tp < entry
    return sl < entry and tp > entry


def validate_pre_execution(
    *,
    symbol: str,
    entry_price: float,
    side: str,
    stop_loss: float,
    take_profit: float,
    atr_value: float | None = None,
) -> PreExecutionDecision:
    """يرفض أي صفقة بلا SL/TP صالحين؛ يملأ Emergency ATR عند الحاجة."""
    try:
        settings = get_settings()
        if not bool(getattr(settings, "pre_execution_gate_enabled", True)):
            return PreExecutionDecision(
                True,
                stop_loss,
                take_profit,
                "Pre-Execution Gate معطّل — تمرير",
            )

        sl = float(stop_loss or 0.0)
        tp = float(take_profit or 0.0)
        used_emergency = False
        live_atr = atr_value

        if not _has_valid_sl_tp(entry_price, sl, tp, side):
            if bool(getattr(settings, "emergency_atr_sl_enabled", True)):
                if live_atr is None:
                    live_atr = fetch_live_atr(symbol)
                emergency = compute_emergency_atr_sl_tp(
                    entry_price, side, live_atr
                )
                if emergency.ok:
                    sl, tp = emergency.stop_loss, emergency.take_profit
                    used_emergency = True
                else:
                    return PreExecutionDecision(
                        False,
                        0.0,
                        0.0,
                        f"Zero-SL Denial: {emergency.reason}",
                        atr_value=live_atr,
                    )
            else:
                return PreExecutionDecision(
                    False,
                    0.0,
                    0.0,
                    "Zero-SL Denial: SL/TP غير معرّفين مسبقاً",
                    atr_value=live_atr,
                )

        if bool(getattr(settings, "sl_rr_lock_enabled", True)):
            locked_tp = lock_tp_to_rr(entry_price, sl, side)
            if locked_tp > 0:
                tp = locked_tp

        if bool(getattr(settings, "risk_distance_filter_enabled", True)):
            exceeded, dist_reason = risk_distance_exceeds_cap(entry_price, sl)
            if exceeded:
                return PreExecutionDecision(
                    False,
                    sl,
                    tp,
                    dist_reason,
                    used_emergency_atr=used_emergency,
                    atr_value=live_atr,
                )

        if not _has_valid_sl_tp(entry_price, sl, tp, side):
            return PreExecutionDecision(
                False,
                sl,
                tp,
                "Zero-SL Denial: فشل التحقق النهائي من SL/TP",
                used_emergency_atr=used_emergency,
                atr_value=live_atr,
            )

        note = "Pre-Execution Gate: SL/TP صالحان"
        if used_emergency:
            note = f"{note} | Emergency ATR مفعّل"
        return PreExecutionDecision(
            True,
            sl,
            tp,
            note,
            used_emergency_atr=used_emergency,
            atr_value=live_atr,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("validate_pre_execution(%s) فشل: %s", symbol, exc)
        # حماية التشغيل: عند خطأ البوابة نرفض الدخول بدلاً من إرسال أمر بلا حماية
        return PreExecutionDecision(
            False,
            float(stop_loss or 0.0),
            float(take_profit or 0.0),
            f"Pre-Execution Gate خطأ داخلي — رفض آمن: {exc}",
        )
