"""حساب حجم العقد — مخاطرة 1% من الرصيد."""

from __future__ import annotations

from config.project_rules import assert_entry_notional, sizing_balance
from config.settings import get_settings
from execution.sl_tp_calculator import calculate_sl_tp
from risk.compound_growth import risk_amount


class LotCalculator:
    def __init__(self, account_balance: float) -> None:
        settings = get_settings()
        self.balance = account_balance
        self.min_balance = settings.min_account_balance

    def calculate(
        self,
        current_price: float,
        *,
        sl_pct: float | None = None,
        rr_ratio: float | None = None,
        risk_pct: float | None = None,
        side: str = "buy",
    ) -> tuple[float, float, float]:
        # الحد الأدنى للرصيد يُفحص في RiskEngine — هنا نحسب الحجم من الرصيد الفعلي فقط
        if current_price <= 0 or self.balance <= 0:
            return 0.0, 0.0, 0.0

        settings = get_settings()
        sl = sl_pct if sl_pct is not None else settings.default_sl_pct
        rr = rr_ratio if rr_ratio is not None else settings.default_rr_ratio
        # طبقة مضافة: رصيد مرجعي 5000 إن كان الحي ضعيفاً جداً
        bal = sizing_balance(float(self.balance))

        stop_loss, take_profit = calculate_sl_tp(
            current_price,
            sl_pct=sl,
            rr_ratio=rr,
            side=side,
        )
        loss_per_unit = current_price * sl
        if loss_per_unit <= 0:
            return 0.0, 0.0, 0.0

        units_to_buy = risk_amount(bal, risk_pct) / loss_per_unit
        amount = round(float(units_to_buy), 8)
        # منع غبار تحت حد المشروع قبل التنفيذ التلقائي
        # (الفتح اليدوي يتجاوز هذا عبر force_open في trade_executor)
        if assert_entry_notional(amount, current_price):
            return 0.0, stop_loss, take_profit
        return amount, stop_loss, take_profit

    def is_rr_acceptable(
        self,
        entry_price: float,
        sl: float,
        tp: float,
        min_ratio: float | None = None,
    ) -> bool:
        settings = get_settings()
        ratio = min_ratio if min_ratio is not None else settings.default_rr_ratio
        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)
        if risk == 0:
            return False
        return (reward / risk) >= ratio
