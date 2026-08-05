# -*- coding: utf-8 -*-
"""GoldenShield AI — Autonomous Enterprise Trading Architecture
Project Rules & Global Constants (v2026.08_ENTERPRISE_HYBRID)

هجين دائم:
  - تلقائي: درجة 9–10 فقط (90–100) + حد أدنى صفقة ~25$
  - يدوي/بث: درجة 7–8 (70–75) → تيليجرام للاختيار اليدوي
  - الفتح اليدوي: غير مقيّد بحد 25$ الصارم (حرية Demo)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config.settings import get_settings
from core.constants import score_to_percent
from risk.compound_growth import risk_amount
from execution.sl_tp_calculator import calculate_sl_tp

# —— هوية المؤسسة ——
PROJECT_NAME: str = "GoldenShield AI"
ARCHITECTURE_MODE: str = "Autonomous Enterprise Trading Architecture"
PROJECT_RULES_VERSION: str = "v2026.08_ENTERPRISE_HYBRID"

# —— رأس المال والحدود ——
PROJECT_REFERENCE_CAPITAL: float = 5000.0
PROJECT_MIN_TRADE_NOTIONAL: float = 25.0
PROJECT_MIN_EXCHANGE_NOTIONAL: float = 5.0

# —— النظام الهجين (مرجع دائم للمشروع) ——
HYBRID_SIGNAL_MODE: bool = True
HYBRID_AUTO_MIN_SCORE: int = 9
HYBRID_AUTO_MIN_PERCENT: int = 90
AUTO_ENTRY_MIN_PERCENT: int = 90
HYBRID_MANUAL_MIN_SCORE: int = 7
HYBRID_MANUAL_MIN_PERCENT: int = 70
TELEGRAM_SIGNAL_MIN_PERCENT: int = 70
HYBRID_MANUAL_MAX_SCORE_EXCLUSIVE: int = 9  # 7–8 يدوي
# عتبة يدوي موحّدة مع بث التيليجرام والتنفيذ اليدوي (لا تعارض مع ≥70)
ENTERPRISE_MANUAL_PREFERRED_PERCENT: int = HYBRID_MANUAL_MIN_PERCENT  # 70
MANUAL_ENTRY_REQUIRED: bool = False

# —— أعلام تشغيل مؤسسية ——
BOT_FORCE_ACTIVE: bool = True
SSOT_SYNC_ENABLED: bool = True
POST_MORTEM_ENGINE_ACTIVE: bool = True
CIRCUIT_BREAKER_MAX_LOSSES: int = 3
ENTERPRISE_PIPELINE_ENABLED: bool = True

# أطر المؤسسة: اتجاه 4H / نطاق 1H / دخول 15m·5m / انزلاق 1m
ENTERPRISE_TIMEFRAMES: tuple[str, ...] = ("4h", "1h", "15m", "5m", "1m")
# —— وضع النبض السريع / No Sleep (24/7) ——
NO_SLEEP_MODE: bool = True
PULSE_LOOP_INTERVAL_SECONDS: int = 4  # هدف 3–5 ثوانٍ
PULSE_LIVE_SIGNALS_SECONDS: int = 4
PULSE_LIVE_POSITIONS_SECONDS: int = 3


@dataclass(frozen=True)
class ProjectRules:
    reference_capital: float = PROJECT_REFERENCE_CAPITAL
    risk_per_trade_pct: float = 1.0
    default_sl_pct: float = 0.03
    default_rr_ratio: float = 3.0
    min_exchange_notional: float = PROJECT_MIN_EXCHANGE_NOTIONAL
    min_trade_notional: float = PROJECT_MIN_TRADE_NOTIONAL
    notify_min_percent: int = HYBRID_MANUAL_MIN_PERCENT
    auto_soft_min_percent: int = HYBRID_AUTO_MIN_PERCENT
    signal_min_percent: int = HYBRID_MANUAL_MIN_PERCENT
    hybrid_mode: bool = True
    hybrid_auto_min_score: int = HYBRID_AUTO_MIN_SCORE
    hybrid_manual_min_score: int = HYBRID_MANUAL_MIN_SCORE
    circuit_breaker_max_losses: int = CIRCUIT_BREAKER_MAX_LOSSES
    ssot_sync_enabled: bool = True
    post_mortem_active: bool = True
    enterprise_pipeline: bool = True
    architecture_mode: str = ARCHITECTURE_MODE


def load_project_rules() -> ProjectRules:
    """قراءة آمنة مع defaults — لا تكسر البوت إن غاب مفتاح."""
    settings = get_settings()
    try:
        ref = float(os.getenv("PROJECT_REFERENCE_CAPITAL", "5000") or 5000)
    except (TypeError, ValueError):
        ref = 5000.0
    try:
        min_trade = float(os.getenv("PROJECT_MIN_TRADE_NOTIONAL", "25") or 25)
    except (TypeError, ValueError):
        min_trade = 25.0
    try:
        min_ex = float(os.getenv("PROJECT_MIN_EXCHANGE_NOTIONAL", "5") or 5)
    except (TypeError, ValueError):
        min_ex = 5.0
    hybrid_raw = (os.getenv("HYBRID_SIGNAL_MODE", "true") or "true").strip().lower()
    hybrid = hybrid_raw in {"1", "true", "yes", "on"}
    try:
        notify = int(
            os.getenv(
                "TELEGRAM_SIGNAL_MIN_PERCENT",
                str(HYBRID_MANUAL_MIN_PERCENT),
            )
            or HYBRID_MANUAL_MIN_PERCENT
        )
    except (TypeError, ValueError):
        notify = HYBRID_MANUAL_MIN_PERCENT
    if hybrid:
        # الهجين: بث من درجة 7 (70/100) — لا ترفع العتبة فوق ذلك
        notify = HYBRID_MANUAL_MIN_PERCENT
    auto_min = int(
        getattr(settings, "auto_entry_min_percent", HYBRID_AUTO_MIN_PERCENT)
        or HYBRID_AUTO_MIN_PERCENT
    )
    if hybrid:
        auto_min = max(auto_min, HYBRID_AUTO_MIN_PERCENT)
    def _flag(key: str, default: bool = True) -> bool:
        raw = (os.getenv(key, "true" if default else "false") or ("true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    try:
        cb_max = int(os.getenv("CIRCUIT_BREAKER_MAX_LOSSES", str(CIRCUIT_BREAKER_MAX_LOSSES)) or CIRCUIT_BREAKER_MAX_LOSSES)
    except (TypeError, ValueError):
        cb_max = CIRCUIT_BREAKER_MAX_LOSSES

    return ProjectRules(
        reference_capital=max(ref, 100.0),
        risk_per_trade_pct=float(getattr(settings, "risk_per_trade_pct", 1.0) or 1.0),
        default_sl_pct=float(getattr(settings, "default_sl_pct", 0.03) or 0.03),
        default_rr_ratio=float(getattr(settings, "default_rr_ratio", 3.0) or 3.0),
        min_exchange_notional=max(min_ex, 5.0),
        min_trade_notional=max(min_trade, min_ex, 5.0),
        notify_min_percent=int(notify),
        auto_soft_min_percent=int(auto_min),
        signal_min_percent=int(
            os.getenv("SIGNAL_MIN_PERCENT", str(HYBRID_MANUAL_MIN_PERCENT))
            or HYBRID_MANUAL_MIN_PERCENT
        ),
        hybrid_mode=hybrid,
        hybrid_auto_min_score=HYBRID_AUTO_MIN_SCORE,
        hybrid_manual_min_score=HYBRID_MANUAL_MIN_SCORE,
        circuit_breaker_max_losses=max(1, cb_max),
        ssot_sync_enabled=_flag("SSOT_SYNC_ENABLED", True),
        post_mortem_active=_flag("POST_MORTEM_ENGINE_ACTIVE", True),
        enterprise_pipeline=_flag("ENTERPRISE_PIPELINE_ENABLED", True),
        architecture_mode=ARCHITECTURE_MODE,
    )


def score_int(score: int | float) -> int:
    try:
        return int(round(float(score or 0)))
    except (TypeError, ValueError):
        return 0


def is_hybrid_auto_score(score: int | float) -> bool:
    """تلقائي فقط عند 9 أو 10."""
    return score_int(score) >= HYBRID_AUTO_MIN_SCORE


def is_hybrid_manual_broadcast_score(score: int | float) -> bool:
    """بث يدوي: 7 أو 8 (أقل من عتبة التلقائي)."""
    s = score_int(score)
    return HYBRID_MANUAL_MIN_SCORE <= s < HYBRID_MANUAL_MAX_SCORE_EXCLUSIVE


def is_hybrid_notifiable_score(score: int | float) -> bool:
    """أي درجة تُرسل لتيليجرام في الهجين: ≥7."""
    return score_int(score) >= HYBRID_MANUAL_MIN_SCORE


def hybrid_entry_label(score: int | float) -> str:
    pct = score_to_percent(score)
    s = score_int(score)
    if s >= 10:
        return f"ذهبي تلقائي ⚡ ({s}/10 · {pct}/100)"
    if is_hybrid_auto_score(score):
        return f"تلقائي ⚡ ({s}/10 · {pct}/100)"
    if is_hybrid_manual_broadcast_score(score):
        return f"يدوي 🖐 ({s}/10 · {pct}/100)"
    return f"مراقبة ({s}/10 · {pct}/100)"


def sizing_balance(live_balance: float, rules: ProjectRules | None = None) -> float:
    """للعرض/الحساب: استخدم الرصيد الحي إن وُجد، وإلا المرجع 5000."""
    rules = rules or load_project_rules()
    bal = float(live_balance or 0.0)
    if bal >= 50.0:
        return bal
    return float(rules.reference_capital)


def compute_position_size(
    *,
    price: float,
    live_balance: float,
    side: str = "buy",
    sl_pct: float | None = None,
    rr_ratio: float | None = None,
    risk_pct: float | None = None,
    enforce_project_min: bool = True,
) -> tuple[float, float, float, str]:
    """(amount, stop_loss, take_profit, reject_reason)."""
    rules = load_project_rules()
    if price <= 0:
        return 0.0, 0.0, 0.0, "سعر غير صالح"
    bal = sizing_balance(live_balance, rules)
    sl = float(sl_pct if sl_pct is not None else rules.default_sl_pct)
    rr = float(rr_ratio if rr_ratio is not None else rules.default_rr_ratio)
    risk = float(risk_pct if risk_pct is not None else rules.risk_per_trade_pct)
    stop_loss, take_profit = calculate_sl_tp(price, sl_pct=sl, rr_ratio=rr, side=side)
    loss_per_unit = price * sl
    if loss_per_unit <= 0:
        return 0.0, 0.0, 0.0, "مسافة وقف غير صالحة"
    amount = risk_amount(bal, risk) / loss_per_unit
    amount = round(float(amount), 8)
    notional = amount * price
    if enforce_project_min and notional + 1e-9 < float(rules.min_trade_notional):
        return (
            0.0,
            stop_loss,
            take_profit,
            (
                f"حجم الصفقة (~{notional:.2f}$) أقل من حد المشروع "
                f"{rules.min_trade_notional:.0f}$ لرأس مال مرجعي {rules.reference_capital:.0f}"
            ),
        )
    if notional + 1e-9 < float(rules.min_exchange_notional):
        return (
            0.0,
            stop_loss,
            take_profit,
            f"حجم الصفقة تحت حد المنصة ({rules.min_exchange_notional:.0f}$)",
        )
    return amount, stop_loss, take_profit, ""


def min_notional_ok(notional: float, rules: ProjectRules | None = None) -> bool:
    rules = rules or load_project_rules()
    try:
        return float(notional or 0.0) + 1e-9 >= float(rules.min_trade_notional)
    except (TypeError, ValueError):
        return False


def assert_entry_notional(
    amount: float,
    price: float,
    *,
    force_open: bool = False,
) -> str:
    """سلسلة فارغة = مسموح.

    force_open=True (يدوي): يتجاوز حد المشروع 25$ — يبقى حد المنصة ~5$ فقط.
    """
    try:
        notional = float(amount or 0.0) * float(price or 0.0)
    except (TypeError, ValueError):
        return "حجم/سعر غير صالح"
    rules = load_project_rules()
    if force_open:
        if notional + 1e-9 < float(rules.min_exchange_notional):
            return (
                f"مرفوض يدوياً: قيمة ~{notional:.2f}$ "
                f"تحت حد المنصة ({rules.min_exchange_notional:.0f}$)"
            )
        return ""
    if not min_notional_ok(notional, rules):
        return (
            f"مرفوض: قيمة الصفقة ~{notional:.2f}$ "
            f"(الحد الأدنى للتلقائي {rules.min_trade_notional:.0f}$)"
        )
    return ""
