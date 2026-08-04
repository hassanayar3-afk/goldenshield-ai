"""محرك قواعد المشروع المركزي — رأس مال مرجعي 5000 (طبقة مضافة).

لا يستبدل منطق المخاطر الحالي؛ يوحّد الحدود الدنيا ويمنع صفقات الغبار.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config.settings import get_settings
from core.constants import (
    SIGNAL_MIN_PERCENT,
    SIGNAL_NOTIFY_MIN_PERCENT,
    SIGNAL_AUTO_SOFT_MIN,
)
from risk.compound_growth import risk_amount
from execution.sl_tp_calculator import calculate_sl_tp


@dataclass(frozen=True)
class ProjectRules:
    reference_capital: float = 5000.0
    risk_per_trade_pct: float = 1.0
    default_sl_pct: float = 0.03
    default_rr_ratio: float = 3.0
    min_exchange_notional: float = 5.0
    min_trade_notional: float = 25.0  # يمنع الغبار على رأس مال 5000
    notify_min_percent: int = SIGNAL_NOTIFY_MIN_PERCENT
    auto_soft_min_percent: int = SIGNAL_AUTO_SOFT_MIN
    signal_min_percent: int = SIGNAL_MIN_PERCENT


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
    return ProjectRules(
        reference_capital=max(ref, 100.0),
        risk_per_trade_pct=float(getattr(settings, "risk_per_trade_pct", 1.0) or 1.0),
        default_sl_pct=float(getattr(settings, "default_sl_pct", 0.03) or 0.03),
        default_rr_ratio=float(getattr(settings, "default_rr_ratio", 3.0) or 3.0),
        min_exchange_notional=max(min_ex, 5.0),
        min_trade_notional=max(min_trade, min_ex, 5.0),
        notify_min_percent=int(
            getattr(settings, "telegram_signal_min_percent", SIGNAL_NOTIFY_MIN_PERCENT)
            or SIGNAL_NOTIFY_MIN_PERCENT
        ),
        auto_soft_min_percent=int(
            getattr(settings, "auto_entry_min_percent", SIGNAL_AUTO_SOFT_MIN)
            or SIGNAL_AUTO_SOFT_MIN
        ),
        signal_min_percent=SIGNAL_MIN_PERCENT,
    )


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
) -> tuple[float, float, float, str]:
    """(amount, stop_loss, take_profit, reject_reason).

    يرجع amount=0 وسبب الرفض إن كانت الصفقة تحت الحد الأدنى للمشروع.
    """
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
    if notional + 1e-9 < float(rules.min_trade_notional):
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


def assert_entry_notional(amount: float, price: float) -> str:
    """سلسلة فارغة = مسموح، وإلا سبب الرفض."""
    try:
        notional = float(amount or 0.0) * float(price or 0.0)
    except (TypeError, ValueError):
        return "حجم/سعر غير صالح"
    if not min_notional_ok(notional):
        rules = load_project_rules()
        return (
            f"مرفوض: قيمة الصفقة ~{notional:.2f}$ "
            f"(الحد الأدنى للمشروع {rules.min_trade_notional:.0f}$)"
        )
    return ""
