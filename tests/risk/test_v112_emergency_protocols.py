"""اختبارات بروتوكولات v1.1.2 — Pre-Execution Gate + Emergency ATR + R:R Lock."""

from __future__ import annotations

from unittest.mock import patch

from audit.execution_events import clear_execution_events, log_execution_event, recent_execution_events
from risk.emergency_protocols import (
    check_open_position_volatility,
    compute_emergency_atr_sl_tp,
    lock_tp_to_rr,
    risk_distance_exceeds_cap,
)
from risk.pre_execution_gate import validate_pre_execution


def test_compute_emergency_atr_sl_buy():
    result = compute_emergency_atr_sl_tp(100.0, "buy", atr_value=2.0, atr_mult=1.5, rr_ratio=3.0)
    assert result.ok
    assert result.stop_loss == 97.0  # 100 - 1.5*2
    assert result.take_profit == 109.0  # 100 + 3*3


def test_compute_emergency_atr_sl_sell():
    result = compute_emergency_atr_sl_tp(100.0, "sell", atr_value=2.0, atr_mult=1.5, rr_ratio=3.0)
    assert result.ok
    assert result.stop_loss == 103.0
    assert result.take_profit == 91.0


def test_compute_emergency_atr_rejects_missing_atr():
    result = compute_emergency_atr_sl_tp(100.0, "buy", atr_value=None)
    assert not result.ok


def test_lock_tp_to_rr():
    tp = lock_tp_to_rr(100.0, 97.0, "buy", rr_ratio=3.0)
    assert tp == 109.0


def test_risk_distance_filter():
    # مسافة كبيرة جداً يجب أن تُرفض عند سقف منخفض
    with patch("risk.emergency_protocols.get_settings") as gs:
        gs.return_value.risk_per_trade_pct = 1.0
        gs.return_value.risk_distance_max_sl_pct = 0.02
        exceeded, reason = risk_distance_exceeds_cap(100.0, 90.0)
        assert exceeded
        assert "Risk-Distance" in reason


def test_zero_sl_denial_without_atr():
    with patch("risk.pre_execution_gate.get_settings") as gs, patch(
        "risk.pre_execution_gate.fetch_live_atr", return_value=None
    ):
        settings = gs.return_value
        settings.pre_execution_gate_enabled = True
        settings.emergency_atr_sl_enabled = True
        settings.sl_rr_lock_enabled = True
        settings.risk_distance_filter_enabled = False
        decision = validate_pre_execution(
            symbol="BTC/USDT",
            entry_price=100.0,
            side="buy",
            stop_loss=0.0,
            take_profit=0.0,
            atr_value=None,
        )
        assert not decision.approved
        assert "Zero-SL Denial" in decision.reason


def test_pre_execution_fills_emergency_atr():
    with patch("risk.pre_execution_gate.get_settings") as gs:
        settings = gs.return_value
        settings.pre_execution_gate_enabled = True
        settings.emergency_atr_sl_enabled = True
        settings.sl_rr_lock_enabled = True
        settings.sl_rr_lock_ratio = 3.0
        settings.risk_distance_filter_enabled = False
        settings.emergency_atr_mult = 1.5
        decision = validate_pre_execution(
            symbol="BTC/USDT",
            entry_price=100.0,
            side="buy",
            stop_loss=0.0,
            take_profit=0.0,
            atr_value=2.0,
        )
        assert decision.approved
        assert decision.used_emergency_atr
        assert decision.stop_loss == 97.0
        assert decision.take_profit == 109.0


def test_pre_execution_rejects_invalid_direction():
    with patch("risk.pre_execution_gate.get_settings") as gs, patch(
        "risk.pre_execution_gate.fetch_live_atr", return_value=None
    ):
        settings = gs.return_value
        settings.pre_execution_gate_enabled = True
        settings.emergency_atr_sl_enabled = False
        settings.sl_rr_lock_enabled = False
        settings.risk_distance_filter_enabled = False
        # SL فوق الدخول لصفقة شراء = غير صالح
        decision = validate_pre_execution(
            symbol="BTC/USDT",
            entry_price=100.0,
            side="buy",
            stop_loss=105.0,
            take_profit=110.0,
        )
        assert not decision.approved


def test_volatility_guard_triggers_close():
    with patch("risk.emergency_protocols.get_settings") as gs:
        gs.return_value.volatility_guard_enabled = True
        gs.return_value.volatility_guard_expand_mult = 1.5
        # SL عند 97 (مسافة 3%)، السعر انخفض 5% → ≥ 1.5×3%
        hit = check_open_position_volatility(
            symbol="BTC/USDT",
            side="buy",
            entry_price=100.0,
            stop_loss=97.0,
            current_price=95.0,
        )
        assert hit.should_close


def test_log_execution_event():
    clear_execution_events()
    rec = log_execution_event("entry_rejected", symbol="ETH/USDT", reason="test")
    assert rec["event_type"] == "entry_rejected"
    assert recent_execution_events(1)[0]["symbol"] == "ETH/USDT"
    clear_execution_events()


def test_v112_settings_defaults_present():
    from config.settings import load_settings

    settings = load_settings(reload=True)
    assert hasattr(settings, "pre_execution_gate_enabled")
    assert hasattr(settings, "emergency_atr_mult")
    assert settings.emergency_atr_mult == 1.5
    assert settings.sl_rr_lock_ratio == 3.0
