"""اختبارات بروتوكولات التشغيل المؤسسية."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from audit.consensus_gate import ConsensusResult
from audit.shadow_executor import ShadowResult, ShadowVote
from core.analyzer import AnalysisResult
from core.technical.timeframe_aligner import TimeframeAlignment, TrendDirection
from risk.high_conviction_protocol import evaluate_high_conviction_eligibility
from risk.protocol_models import RISK_MODE_HIGH_CONVICTION
from risk.standard_bonus_profile import resolve_trade_prefs
from risk.state import RiskState


def _shadow(approved: bool = True) -> ShadowResult:
    tech = ShadowVote(algorithm="technical", approved=approved, reason="ok")
    liq = ShadowVote(algorithm="liquidity", approved=approved, reason="ok")
    return ShadowResult(symbol="FOREX/XAUUSD", technical=tech, liquidity=liq)


def _result(*, score: int = 10, aligned: bool = True) -> AnalysisResult:
    direction = TrendDirection.BULLISH if aligned else TrendDirection.NEUTRAL
    alignment = TimeframeAlignment(
        aligned=aligned,
        direction=direction,
        per_timeframe={"15m": direction, "1h": direction, "4h": direction},
    )
    from core.hybrid_engine import HybridDecision

    hybrid = HybridDecision(
        allowed=True,
        halted=False,
        final_signal="BUY SIGNAL",
        technical_passed=True,
        sentiment_ok=True,
        macro_ok=True,
        liquidity_ok=True,
        reasons=("ok",),
    )
    return AnalysisResult(
        symbol="FOREX/XAUUSD",
        signal="BUY SIGNAL",
        price=2400.0,
        sma=2390.0,
        score=score,
        passed=True,
        reasons=("test",),
        alignment=alignment,
        hybrid=hybrid,
    )


def test_hc_disabled_by_default():
    result = _result()
    consensus = ConsensusResult(True, "ok", _shadow())
    approval = evaluate_high_conviction_eligibility(
        result, consensus=consensus, risk_state=None, open_positions=0
    )
    assert not approval.approved
    assert "معطّل" in approval.reason


@patch("risk.high_conviction_protocol.get_settings")
@patch("risk.high_conviction_protocol.check_news_filter")
@patch("risk.high_conviction_protocol.track_whales")
@patch("risk.high_conviction_protocol.check_session")
@patch("risk.high_conviction_protocol.check_slippage")
def test_hc_approves_when_enabled_and_gates_pass(
    mock_slip, mock_session, mock_whales, mock_news, mock_settings
):
    from types import SimpleNamespace

    mock_settings.return_value = SimpleNamespace(
        high_conviction_mode=True,
        high_conviction_config={
            "high_conviction": {
                "risk_per_trade_pct": 3.0,
                "scaling_in": {"enabled": True, "initial_risk_pct": 1.0},
                "gates": {
                    "min_signal_percent": 100,
                    "news_blackout_minutes": 30,
                    "max_daily_hc_trades": 2,
                    "allowed_sessions": ["london"],
                },
                "whale": {"require_with_trend": True},
                "sentiment": {"require_sentiment_ok": True},
            }
        },
        default_sl_pct=0.03,
        default_rr_ratio=2.0,
    )
    mock_news.return_value = SimpleNamespace(trading_allowed=True, reason="ok")
    mock_whales.return_value = SimpleNamespace(
        has_whale_support=True, has_whale_resistance=True
    )
    mock_session.return_value = SimpleNamespace(allowed=True, reason="ok")
    mock_slip.return_value = SimpleNamespace(allowed=True, reason="ok")

    state = RiskState(session_start_balance=10000.0, current_balance=10000.0)
    approval = evaluate_high_conviction_eligibility(
        _result(),
        consensus=ConsensusResult(True, "ok", _shadow()),
        risk_state=state,
        open_positions=0,
    )
    assert approval.approved
    assert approval.risk_mode == RISK_MODE_HIGH_CONVICTION
    assert approval.trade_prefs is not None
    assert approval.trade_prefs.risk_pct == 1.0


@patch("risk.standard_bonus_profile.get_settings")
def test_standard_bonus_adjusts_rr(mock_settings):
    from types import SimpleNamespace

    mock_settings.return_value = SimpleNamespace(
        standard_bonus_profile=True,
        standard_bonus_config={"standard_bonus": {"tp_scale_factor": 1.20}},
        risk_per_trade_pct=1.0,
        default_sl_pct=0.03,
        default_rr_ratio=2.0,
    )
    prefs = resolve_trade_prefs(symbol="FOREX/XAUUSD", signal_score=10)
    assert prefs.rr_ratio == pytest.approx(3.6)


@patch("risk.standard_bonus_profile.get_settings")
def test_standard_bonus_off_keeps_defaults(mock_settings):
    from types import SimpleNamespace

    mock_settings.return_value = SimpleNamespace(
        standard_bonus_profile=False,
        standard_bonus_config={},
        risk_per_trade_pct=1.0,
        default_sl_pct=0.03,
        default_rr_ratio=2.0,
    )
    prefs = resolve_trade_prefs()
    assert prefs.rr_ratio == 3.0
