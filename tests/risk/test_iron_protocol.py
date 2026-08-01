"""اختبار البروتوكول الحديدي — فرض الحدود الدنيا."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from risk.iron_protocol import apply_iron_protocol, iron_protocol_enabled


@dataclass(frozen=True)
class _FakeSettings:
    execution_mode: str = "live"
    execution_backend: str = "binance"
    mt5_enabled: bool = False
    pre_execution_gate_enabled: bool = False
    emergency_protocols_enabled: bool = False
    emergency_atr_sl_enabled: bool = False
    risk_distance_filter_enabled: bool = False
    sl_rr_lock_enabled: bool = False
    sl_rr_lock_ratio: float = 2.0
    volatility_guard_enabled: bool = False
    require_sl_on_all_chunks: bool = False
    close_naked_tickets: bool = False
    manage_positions_during_halt: bool = False
    mt5_attach_sl_tp: bool = False
    auto_entry_min_percent: int = 80
    default_rr_ratio: float = 2.0


def test_iron_forces_live_safety():
    with patch.dict("os.environ", {"IRON_PROTOCOL_ENABLED": "true"}):
        out = apply_iron_protocol(_FakeSettings())
    assert out.pre_execution_gate_enabled is True
    assert out.require_sl_on_all_chunks is True
    assert out.close_naked_tickets is True
    assert out.auto_entry_min_percent == 90
    assert out.default_rr_ratio == 3.0
    assert out.sl_rr_lock_ratio == 3.0
    # Binance-only: لا نفرض ربط SL/TP عبر MT5
    assert out.mt5_attach_sl_tp is False


def test_iron_forces_mt5_attach_when_mt5_enabled():
    with patch.dict("os.environ", {"IRON_PROTOCOL_ENABLED": "true"}):
        out = apply_iron_protocol(
            _FakeSettings(execution_backend="mt5", mt5_enabled=True)
        )
    assert out.mt5_attach_sl_tp is True


def test_iron_raises_weak_auto_even_in_paper():
    with patch.dict("os.environ", {"IRON_PROTOCOL_ENABLED": "true"}):
        out = apply_iron_protocol(_FakeSettings(execution_mode="paper", auto_entry_min_percent=70))
    assert out.auto_entry_min_percent == 90
    assert out.default_rr_ratio == 3.0


def test_iron_can_disable():
    with patch.dict("os.environ", {"IRON_PROTOCOL_ENABLED": "false"}):
        assert iron_protocol_enabled() is False
        out = apply_iron_protocol(_FakeSettings())
    assert out.auto_entry_min_percent == 80
