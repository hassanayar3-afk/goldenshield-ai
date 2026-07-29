"""بروتوكول التنفيذ عالي الخطورة — وضع High Conviction (3% Risk)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from config.settings import get_settings
from core.constants import score_to_percent
from core.fundamental.news_filter import check_news_filter
from core.liquidity.whale_tracker import track_whales
from core.technical.session_filter import check_session
from core.technical.timeframe_aligner import TrendDirection
from data.symbol_routing import display_symbol
from execution.slippage_guard import check_slippage
from operations.trade_prefs import TradePrefs
from risk.protocol_models import (
    RISK_MODE_HIGH_CONVICTION,
    ProtocolApproval,
)

if TYPE_CHECKING:
    from audit.consensus_gate import ConsensusResult
    from core.analyzer import AnalysisResult
    from risk.state import RiskState


def _hc_cfg() -> dict:
    return get_settings().high_conviction_config.get("high_conviction", {})


def _gates() -> dict:
    return _hc_cfg().get("gates", {})


def _scaling() -> dict:
    return _hc_cfg().get("scaling_in", {})


def evaluate_high_conviction_eligibility(
    result: AnalysisResult,
    *,
    consensus: ConsensusResult | None,
    risk_state: RiskState | None,
    open_positions: int,
    available_price: float | None = None,
) -> ProtocolApproval:
    """يفحص شروط HC — لا يُفعّل إلا إذا HIGH_CONVICTION_MODE=true."""
    settings = get_settings()
    if not settings.high_conviction_mode:
        return ProtocolApproval.disabled("وضع High Conviction معطّل")

    cfg = _hc_cfg()
    gates = _gates()
    pct = score_to_percent(result.score)
    min_pct = int(gates.get("min_signal_percent", 100))
    if pct < min_pct:
        return ProtocolApproval.disabled(
            f"HC يتطلب {min_pct}/100 — الحالي {pct}/100"
        )

    if gates.get("require_mtf_alignment", True):
        if result.alignment is None or not result.alignment.aligned:
            return ProtocolApproval.disabled("HC: لا توافق كامل M15/H1/H4")

    if gates.get("block_sideways_regime", True) and result.alignment is not None:
        if result.alignment.direction == TrendDirection.NEUTRAL:
            return ProtocolApproval.disabled("HC: سوق عرضي/محايد")

    news_minutes = int(gates.get("news_blackout_minutes", 30))
    news = check_news_filter(blackout_minutes=news_minutes)
    if not news.trading_allowed:
        return ProtocolApproval.disabled(
            f"HC: {news.reason}"
        )

    if consensus is not None and not consensus.approved:
        return ProtocolApproval.disabled(f"HC: لا إجماع Shadow — {consensus.reason}")

    if result.hybrid is not None and _hc_cfg().get("sentiment", {}).get(
        "require_sentiment_ok", True
    ):
        if not result.hybrid.sentiment_ok:
            return ProtocolApproval.disabled("HC: المشاعر لا تدعم القرار")

    side_buy = result.signal == "BUY SIGNAL"
    if _hc_cfg().get("whale", {}).get("require_with_trend", True):
        whales = track_whales(result.symbol)
        if side_buy and not whales.has_whale_support:
            return ProtocolApproval.disabled("HC: لا دعم حيتان للشراء")
        if not side_buy and not whales.has_whale_resistance:
            return ProtocolApproval.disabled("HC: لا مقاومة حيتان للبيع")

    if risk_state is not None:
        if gates.get("block_after_any_loss", True) and risk_state.consecutive_losses >= 1:
            return ProtocolApproval.disabled("HC: خسارة سابقة — البقاء أولاً")

        max_daily = int(gates.get("max_daily_hc_trades", 2))
        if risk_state.hc_daily_trades >= max_daily:
            return ProtocolApproval.disabled(
                f"HC: الحد اليومي {max_daily} صفقة"
            )

        max_wins = int(gates.get("max_hc_consecutive_wins", 2))
        if risk_state.hc_consecutive_wins >= max_wins:
            return ProtocolApproval.disabled(
                "HC: حماية من الإفراط في الثقة بعد ربحين متتاليين"
            )

        cooldown_h = int(gates.get("cooldown_hours_after_hc", 4))
        if risk_state.hc_last_trade_at is not None:
            until = risk_state.hc_last_trade_at + timedelta(hours=cooldown_h)
            if datetime.now(timezone.utc) < until:
                return ProtocolApproval.disabled(
                    f"HC: فترة تبريد حتى {until.isoformat()}"
                )

    allowed_symbols = list(gates.get("allowed_symbols") or [])
    if allowed_symbols:
        sym = display_symbol(result.symbol).upper()
        allowed = {s.upper() for s in allowed_symbols}
        if sym not in allowed and result.symbol.upper() not in allowed:
            return ProtocolApproval.disabled(
                f"HC: الرمز {sym} غير ضمن القائمة المسموحة"
            )

    sessions = tuple(gates.get("allowed_sessions") or ("london", "london_ny_overlap"))
    session = check_session(allowed_sessions=sessions)
    if not session.allowed:
        return ProtocolApproval.disabled(session.reason)

    slip_max = float(gates.get("max_slippage_points", 0.5))
    slip_price = available_price if available_price is not None else result.price
    slip = check_slippage(
        requested_price=result.price,
        available_price=slip_price,
        max_slippage_points=slip_max,
    )
    if not slip.allowed:
        return ProtocolApproval.disabled(slip.reason)

    scaling = _scaling()
    if scaling.get("enabled", True):
        risk_pct = float(scaling.get("initial_risk_pct", 1.0))
        scaling_pending = True
    else:
        risk_pct = float(cfg.get("risk_per_trade_pct", 3.0))
        scaling_pending = False

    prefs = TradePrefs(
        risk_pct=risk_pct,
        sl_pct=settings.default_sl_pct,
        rr_ratio=settings.default_rr_ratio,
    )

    return ProtocolApproval(
        approved=True,
        reason=f"HC مؤهل — مخاطرة أولية {risk_pct:.1f}%",
        risk_mode=RISK_MODE_HIGH_CONVICTION,
        trade_prefs=prefs,
        scaling_add_pending=scaling_pending,
    )
