"""دروع مؤسسية v1.3 — طبقات فوق المخاطر الأساسية دون كسر 1% / Kill Switch."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings


def _cfg() -> dict[str, Any]:
    settings = get_settings()
    raw = getattr(settings, "institutional_v13", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _flag(key: str, default: bool = False) -> bool:
    cfg = _cfg()
    if key in cfg:
        return bool(cfg[key])
    return bool(getattr(get_settings(), key, default))


def _num(key: str, default: float) -> float:
    cfg = _cfg()
    if key in cfg:
        try:
            return float(cfg[key])
        except (TypeError, ValueError):
            return default
    return float(getattr(get_settings(), key, default))


# —— 6) Compound streak risk scaling ——


@dataclass(frozen=True)
class StreakRiskResult:
    risk_pct: float
    reason: str


def streak_adjusted_risk_pct(
    base_pct: float,
    *,
    consecutive_wins: int = 0,
    consecutive_losses: int = 0,
) -> StreakRiskResult:
    if not _flag("compound_streak_scaling_enabled", True):
        return StreakRiskResult(base_pct, "compound streak معطّل — مخاطرة أساسية")

    win_trigger = int(_num("compound_win_streak_trigger", 2))
    loss_trigger = int(_num("compound_loss_streak_trigger", 1))
    win_pct = _num("compound_win_risk_pct", 1.2)
    loss_pct = _num("compound_loss_risk_pct", 0.5)

    if consecutive_losses >= loss_trigger:
        return StreakRiskResult(
            loss_pct,
            f"سلسلة خسائر {consecutive_losses} — مخاطرة {loss_pct}%",
        )
    if consecutive_wins >= win_trigger:
        return StreakRiskResult(
            win_pct,
            f"سلسلة أرباح {consecutive_wins} — مخاطرة {win_pct}%",
        )
    return StreakRiskResult(base_pct, f"مخاطرة أساسية {base_pct}%")


# —— 5) Network outage shield ——


@dataclass(frozen=True)
class NetworkOutageResult:
    block_new_entries: bool
    reason: str


def check_network_outage_shield(
    *,
    seconds_since_success: float | None,
    is_disconnected: bool,
) -> NetworkOutageResult:
    if not _flag("network_outage_shield_enabled", True):
        return NetworkOutageResult(False, "درع الانقطاع معطّل")

    threshold = _num("network_outage_seconds", 10.0)
    if is_disconnected:
        return NetworkOutageResult(
            True,
            f"انقطاع اتصال — إيقاف إشارات جديدة (عتبة {threshold:.0f}s)",
        )
    if seconds_since_success is not None and seconds_since_success > threshold:
        return NetworkOutageResult(
            True,
            f"لا نبضة ناجحة منذ {seconds_since_success:.0f}s > {threshold:.0f}s",
        )
    return NetworkOutageResult(False, "الاتصال ضمن العتبة")


# —— 8) Flash crash circuit breaker ——


@dataclass
class FlashCrashTracker:
    """تتبع عوائد قصيرة لسلة مرجع (BTC/ETH)."""

    window_seconds: float = 60.0
    _samples: dict[str, list[tuple[float, float]]] = field(default_factory=dict)

    def record(self, symbol: str, price: float, now: float | None = None) -> None:
        if price <= 0:
            return
        ts = time.monotonic() if now is None else now
        bucket = self._samples.setdefault(symbol, [])
        bucket.append((ts, price))
        cutoff = ts - max(self.window_seconds * 3, 180.0)
        self._samples[symbol] = [(t, p) for t, p in bucket if t >= cutoff]

    def move_pct(self, symbol: str, now: float | None = None) -> float | None:
        ts = time.monotonic() if now is None else now
        bucket = self._samples.get(symbol) or []
        if len(bucket) < 2:
            return None
        oldest = None
        newest = bucket[-1][1]
        for t, p in bucket:
            if ts - t <= self.window_seconds:
                oldest = p
                break
        if oldest is None or oldest <= 0:
            oldest = bucket[0][1]
        if oldest <= 0:
            return None
        return ((newest - oldest) / oldest) * 100.0


_flash_tracker = FlashCrashTracker()


def get_flash_crash_tracker() -> FlashCrashTracker:
    return _flash_tracker


@dataclass(frozen=True)
class FlashCrashResult:
    triggered: bool
    reason: str
    basket_move_pct: float = 0.0


def evaluate_flash_crash(
    prices: dict[str, float],
    *,
    adverse_for_longs: bool = True,
) -> FlashCrashResult:
    """تحرّك سلة مرجع > عتبة خلال النافذة → قاطع دائرة."""
    if not _flag("flash_crash_enabled", True):
        return FlashCrashResult(False, "Flash Crash معطّل")

    threshold = abs(_num("flash_crash_pct", 5.0))
    window = _num("flash_crash_window_seconds", 60.0)
    tracker = get_flash_crash_tracker()
    tracker.window_seconds = window

    refs = [
        s
        for s in (
            "BTC/USDT",
            "ETH/USDT",
            "BTCUSDT",
            "ETHUSDT",
        )
        if s in prices
    ]
    # أي مفتاح يحتوي BTC أو ETH
    if not refs:
        refs = [s for s in prices if "BTC" in s.upper() or "ETH" in s.upper()]

    moves: list[float] = []
    for symbol in refs[:4]:
        tracker.record(symbol, float(prices[symbol]))
        mv = tracker.move_pct(symbol)
        if mv is not None:
            moves.append(mv)

    if not moves:
        return FlashCrashResult(False, "لا بيانات سلة كافية")

    avg = sum(moves) / len(moves)
    # انهيار عام = حركة هابطة حادة (adverse للشراء)
    crash = avg <= -threshold
    melt_up = avg >= threshold and not adverse_for_longs
    if crash or melt_up:
        return FlashCrashResult(
            True,
            f"Flash Crash: سلة المرجع {avg:+.2f}% خلال ~{window:.0f}s (عتبة {threshold}%)",
            basket_move_pct=avg,
        )
    return FlashCrashResult(False, f"سلة مستقرة {avg:+.2f}%", basket_move_pct=avg)


# —— 10) Vol-based risk scaling (Spot-safe) ——


@dataclass(frozen=True)
class VolRiskResult:
    risk_pct: float
    reason: str


def vol_adjusted_risk_pct(
    base_pct: float,
    *,
    atr: float | None,
    price: float,
) -> VolRiskResult:
    if not _flag("vol_based_risk_scaling_enabled", False):
        return VolRiskResult(base_pct, "vol risk scaling معطّل")
    if atr is None or price <= 0:
        return VolRiskResult(base_pct, "ATR غير متاح — مخاطرة أساسية")

    atr_pct = (atr / price) * 100.0
    high = _num("vol_atr_high_pct", 2.5)
    extreme = _num("vol_atr_extreme_pct", 4.0)
    mid_mult = _num("vol_risk_mid_mult", 0.7)
    low_mult = _num("vol_risk_low_mult", 0.5)

    if atr_pct >= extreme:
        pct = round(base_pct * low_mult, 4)
        return VolRiskResult(pct, f"تقلب شديد ATR={atr_pct:.2f}% → مخاطرة {pct}%")
    if atr_pct >= high:
        pct = round(base_pct * mid_mult, 4)
        return VolRiskResult(pct, f"تقلب مرتفع ATR={atr_pct:.2f}% → مخاطرة {pct}%")
    return VolRiskResult(base_pct, f"تقلب طبيعي ATR={atr_pct:.2f}%")


# —— 9) Emergency de-risk (not reverse hedge) ——


@dataclass(frozen=True)
class DeRiskAction:
    should_reduce: bool
    close_fraction: float
    reason: str


def evaluate_emergency_derisk(
    *,
    unrealized_r: float,
    pressure_r_threshold: float | None = None,
) -> DeRiskAction:
    """عند ضغط عنيف قبل SL: إغلاق جزئي سريع وليس تحوطاً عكسياً."""
    if not _flag("emergency_derisk_enabled", False):
        return DeRiskAction(False, 0.0, "emergency derisk معطّل")

    thr = pressure_r_threshold
    if thr is None:
        thr = _num("emergency_derisk_r_threshold", -0.7)
    frac = _num("emergency_derisk_close_fraction", 0.5)
    if unrealized_r <= thr:
        return DeRiskAction(
            True,
            max(0.1, min(1.0, frac)),
            f"ضغط {unrealized_r:.2f}R ≤ {thr:.2f}R — تقليص {frac:.0%}",
        )
    return DeRiskAction(False, 0.0, "لا ضغط يستدعي التقليص")


# —— 7) Pre-trade slippage from book ——


@dataclass(frozen=True)
class BookSlippageResult:
    allowed: bool
    slippage_pct: float
    reason: str


def check_book_slippage_pct(
    *,
    mid_or_ref: float,
    ask_or_bid: float,
    max_pct: float | None = None,
) -> BookSlippageResult:
    limit = max_pct if max_pct is not None else _num("max_slippage_pct", 0.1)
    # إن وُجد في settings الرئيسي
    try:
        limit = float(getattr(get_settings(), "max_slippage_pct", limit))
    except Exception:
        pass
    if mid_or_ref <= 0 or ask_or_bid <= 0:
        return BookSlippageResult(True, 0.0, "لا أسعار دفتر — تمرير")
    slip_pct = abs(ask_or_bid - mid_or_ref) / mid_or_ref * 100.0
    if slip_pct <= limit:
        return BookSlippageResult(
            True,
            slip_pct,
            f"انزلاق دفتر {slip_pct:.4f}% ≤ {limit}%",
        )
    return BookSlippageResult(
        False,
        slip_pct,
        f"انزلاق دفتر {slip_pct:.4f}% > {limit}%",
    )
