"""بروتوكولات الطوارئ v1.1.2 — مراقب مستقل لحماية رأس المال.

مرجع وحيد لـ Emergency ATR SL عند تعذّر التحليل الفني.
لا يستبدل emergency_flat ولا calculate_sl_tp — طبقة مضافة فقط.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings
from core.constants import ATR_PERIOD
from core.technical.indicators import atr

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmergencySlResult:
    ok: bool
    stop_loss: float
    take_profit: float
    atr_value: float | None
    reason: str


@dataclass(frozen=True)
class VolatilityGuardHit:
    symbol: str
    reason: str
    should_close: bool


def fetch_live_atr(
    symbol: str,
    *,
    timeframe: str | None = None,
    period: int | None = None,
    limit: int = 80,
) -> float | None:
    """جلب ATR لحظي من طبقة data/ — فشل آمن يعيد None."""
    try:
        settings = get_settings()
        tf = timeframe or str(
            getattr(settings, "emergency_atr_timeframe", None) or "15m"
        )
        atr_period = int(period or getattr(settings, "emergency_atr_period", ATR_PERIOD) or ATR_PERIOD)
        from data.ohlcv_fetcher import OHLCVFetcher

        candles = OHLCVFetcher().fetch(symbol, tf, limit=max(limit, atr_period + 5))
        if not candles:
            return None
        return atr(candles, period=atr_period)
    except Exception as exc:  # noqa: BLE001 — حماية حلقة التشغيل
        logger.warning("fetch_live_atr(%s) فشل: %s", symbol, exc)
        return None


def compute_emergency_atr_sl_tp(
    entry_price: float,
    side: str,
    atr_value: float | None,
    *,
    atr_mult: float | None = None,
    rr_ratio: float | None = None,
) -> EmergencySlResult:
    """حساب SL/TP الطوارئ: SL = 1.5 * ATR · TP = Entry ± (SL_dist * RR)."""
    try:
        settings = get_settings()
        if entry_price <= 0:
            return EmergencySlResult(False, 0.0, 0.0, atr_value, "سعر دخول غير صالح")

        if atr_value is None or atr_value <= 0:
            return EmergencySlResult(
                False, 0.0, 0.0, atr_value, "ATR غير متوفر لحساب Emergency SL"
            )

        mult = float(
            atr_mult
            if atr_mult is not None
            else getattr(settings, "emergency_atr_mult", 1.5)
        )
        rr = float(
            rr_ratio
            if rr_ratio is not None
            else getattr(settings, "sl_rr_lock_ratio", 3.0)
        )
        sl_distance = atr_value * mult
        if sl_distance <= 0 or sl_distance >= entry_price:
            return EmergencySlResult(
                False, 0.0, 0.0, atr_value, "مسافة Emergency ATR غير صالحة"
            )

        side_l = (side or "buy").lower()
        if side_l in {"sell", "short"}:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - (sl_distance * rr)
        else:
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + (sl_distance * rr)

        return EmergencySlResult(
            True,
            round(stop_loss, 8),
            round(take_profit, 8),
            atr_value,
            f"Emergency ATR SL ({mult:.2f}×ATR={atr_value:.8f})",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("compute_emergency_atr_sl_tp فشل: %s", exc)
        return EmergencySlResult(False, 0.0, 0.0, atr_value, f"خطأ Emergency ATR: {exc}")


def lock_tp_to_rr(
    entry_price: float,
    stop_loss: float,
    side: str,
    *,
    rr_ratio: float | None = None,
) -> float:
    """تثبيت TP = Entry ± (SL_Distance * RR) — R:R Ratio Lock."""
    try:
        settings = get_settings()
        rr = float(
            rr_ratio
            if rr_ratio is not None
            else getattr(settings, "sl_rr_lock_ratio", 3.0)
        )
        dist = abs(entry_price - stop_loss)
        if dist <= 0 or entry_price <= 0:
            return 0.0
        side_l = (side or "buy").lower()
        if side_l in {"sell", "short"}:
            return round(entry_price - dist * rr, 8)
        return round(entry_price + dist * rr, 8)
    except Exception as exc:  # noqa: BLE001
        logger.warning("lock_tp_to_rr فشل: %s", exc)
        return 0.0


def risk_distance_exceeds_cap(
    entry_price: float,
    stop_loss: float,
    *,
    max_risk_pct: float | None = None,
) -> tuple[bool, str]:
    """فلتر المسافة: إذا مسافة SL تتطلب مخاطرة > السقف → رفض."""
    try:
        settings = get_settings()
        cap = float(
            max_risk_pct
            if max_risk_pct is not None
            else getattr(settings, "risk_distance_max_pct", None)
            or settings.risk_per_trade_pct
        )
        # risk_per_trade_pct مخزّن كنسبة مئوية (1.0 = 1%)
        cap_frac = cap / 100.0 if cap > 1.0 else cap
        if entry_price <= 0 or stop_loss <= 0:
            return True, "أسعار غير صالحة لفحص Risk-Distance"
        dist_pct = abs(entry_price - stop_loss) / entry_price
        # نقارن مسافة السعر كنسبة؛ السقف الافتراضي أوسع قليلاً من مخاطرة اللوت
        max_sl_pct = float(
            getattr(settings, "risk_distance_max_sl_pct", None) or max(cap_frac * 3.0, 0.03)
        )
        if dist_pct > max_sl_pct:
            return (
                True,
                f"Risk-Distance: مسافة SL {dist_pct:.2%} تتجاوز السقف {max_sl_pct:.2%}",
            )
        return False, "ضمن نطاق المسافة المسموح"
    except Exception as exc:  # noqa: BLE001
        logger.warning("risk_distance_exceeds_cap فشل: %s", exc)
        return False, f"تجاوز فحص المسافة بسبب خطأ: {exc}"


def check_open_position_volatility(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    current_price: float,
) -> VolatilityGuardHit:
    """مراقبة لحظية: فجوة/انزلاق وسّع مسافة SL بعد الفتح → إغلاق."""
    try:
        settings = get_settings()
        if not bool(getattr(settings, "volatility_guard_enabled", True)):
            return VolatilityGuardHit(symbol, "Volatility Guard معطّل", False)

        if entry_price <= 0 or stop_loss <= 0 or current_price <= 0:
            return VolatilityGuardHit(symbol, "بيانات ناقصة", False)

        planned = abs(entry_price - stop_loss) / entry_price
        side_l = (side or "buy").lower()
        if side_l in {"sell", "short"}:
            adverse = max(0.0, current_price - entry_price) / entry_price
        else:
            adverse = max(0.0, entry_price - current_price) / entry_price

        expand_mult = float(getattr(settings, "volatility_guard_expand_mult", 1.5))
        # إذا تحرك السعر ضد الصفقة بأكثر من مضاعف مسافة SL المخططة دون إغلاق
        if planned > 0 and adverse >= planned * expand_mult:
            return VolatilityGuardHit(
                symbol,
                f"Volatility Guard: حركة معاكسة {adverse:.2%} ≥ {expand_mult:.1f}× مسافة SL",
                True,
            )
        return VolatilityGuardHit(symbol, "سيولة ضمن الحد", False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("check_open_position_volatility(%s) فشل: %s", symbol, exc)
        return VolatilityGuardHit(symbol, f"خطأ الحارس: {exc}", False)


def run_capital_protection_watchdog(
    positions: list,
    prices: dict[str, float],
) -> list[VolatilityGuardHit]:
    """مراقب مستقل (Priority 0) — يفحص المراكز المفتوحة دون كسر المنطق الأصلي."""
    hits: list[VolatilityGuardHit] = []
    try:
        settings = get_settings()
        if not bool(getattr(settings, "emergency_protocols_enabled", True)):
            return hits
        for pos in positions:
            try:
                symbol = getattr(pos, "symbol", "") or ""
                price = float(prices.get(symbol) or 0.0)
                if not symbol or price <= 0:
                    continue
                side = "sell" if getattr(pos, "side", None) and str(pos.side).lower() in {"sell", "short"} else "buy"
                # Position.side قد يكون Enum
                raw_side = getattr(pos, "side", "buy")
                side = "sell" if "sell" in str(raw_side).lower() else "buy"
                hit = check_open_position_volatility(
                    symbol=symbol,
                    side=side,
                    entry_price=float(getattr(pos, "entry_price", 0.0) or 0.0),
                    stop_loss=float(getattr(pos, "stop_loss", 0.0) or 0.0),
                    current_price=price,
                )
                if hit.should_close:
                    hits.append(hit)
            except Exception as exc:  # noqa: BLE001
                logger.warning("watchdog position فشل: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("run_capital_protection_watchdog فشل: %s", exc)
    return hits
