"""ملحق تشغيل حسابات Standard/Bonus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.settings import get_settings
from core.constants import score_to_percent
from core.technical.spread_filter import check_spread
from execution.execution_cost_filter import check_execution_cost
from execution.sl_tp_calculator import calculate_sl_tp
from operations.trade_prefs import TradePrefs

if TYPE_CHECKING:
    from core.analyzer import AnalysisResult
    from data.models.ticker import Ticker


def _bonus_cfg() -> dict:
    return get_settings().standard_bonus_config.get("standard_bonus", {})


def resolve_trade_prefs(
    *,
    symbol: str = "",
    signal_score: int = 0,
) -> TradePrefs:
    """تفضيلات الصفقة — تُعدّل فقط عند تفعيل STANDARD_BONUS_PROFILE."""
    settings = get_settings()
    base = TradePrefs.defaults()
    if not settings.standard_bonus_profile:
        return base

    cfg = _bonus_cfg()
    tp_scale = float(cfg.get("tp_scale_factor", 1.20))
    return TradePrefs(
        risk_pct=base.risk_pct,
        sl_pct=base.sl_pct,
        rr_ratio=round(base.rr_ratio * tp_scale, 4),
    )


def check_bonus_entry_allowed(
    result: AnalysisResult,
    *,
    ticker: Ticker | None = None,
) -> tuple[bool, str]:
    """فلاتر إضافية لحساب Standard/Bonus قبل الدخول."""
    settings = get_settings()
    if not settings.standard_bonus_profile:
        return True, "ملحق Standard/Bonus معطّل"

    cfg = _bonus_cfg()
    pct = score_to_percent(result.score)
    min_pct = int(cfg.get("min_signal_percent", 90))
    if pct < min_pct:
        return False, f"Standard: يتطلب {min_pct}/100 — الحالي {pct}/100"

    max_spread = float(cfg.get("max_spread_pct", 0.10))
    if ticker is not None:
        spread = check_spread(ticker, max_spread_pct=max_spread)
        if not spread.passed:
            return False, f"Standard: {spread.reason}"

    side = "sell" if result.signal == "SELL SIGNAL" else "buy"
    sl, tp = calculate_sl_tp(result.price, side=side)
    max_cost = float(cfg.get("max_cost_to_expected_profit_pct", 10.0))
    spread_pct = ticker.spread_pct if ticker is not None else None
    cost = check_execution_cost(
        entry_price=result.price,
        take_profit=tp,
        spread_pct=spread_pct,
        max_cost_to_profit_pct=max_cost,
    )
    if not cost.allowed:
        return False, f"Standard: {cost.reason}"

    return True, "Standard/Bonus: الشروط مستوفاة"
