"""اختبارات دروع v1.3 المؤسسية."""

from __future__ import annotations

from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.smart_exits import evaluate_multi_tier_tp
from risk.advanced_shields import (
    FlashCrashTracker,
    check_book_slippage_pct,
    check_network_outage_shield,
    evaluate_emergency_derisk,
    streak_adjusted_risk_pct,
    vol_adjusted_risk_pct,
)
from data.api_failover import is_rate_limit_error
from core.market_filters_extra import (
    check_funding_guard,
    check_weekend_flat_policy,
    detect_spoofing,
)


def test_rate_limit_detection():
    assert is_rate_limit_error(Exception("binance 429 too many requests"))
    assert is_rate_limit_error(Exception("418 I'm a teapot banned"))
    assert not is_rate_limit_error(Exception("timeout"))


def test_streak_risk_scaling(monkeypatch):
    monkeypatch.setattr(
        "risk.advanced_shields.get_settings",
        lambda: type(
            "S",
            (),
            {
                "institutional_v13": {
                    "compound_streak_scaling_enabled": True,
                    "compound_win_streak_trigger": 2,
                    "compound_loss_streak_trigger": 1,
                    "compound_win_risk_pct": 1.2,
                    "compound_loss_risk_pct": 0.5,
                }
            },
        )(),
    )
    assert streak_adjusted_risk_pct(1.0, consecutive_wins=2).risk_pct == 1.2
    assert streak_adjusted_risk_pct(1.0, consecutive_losses=1).risk_pct == 0.5
    assert streak_adjusted_risk_pct(1.0, consecutive_wins=0).risk_pct == 1.0


def test_network_outage_10s(monkeypatch):
    monkeypatch.setattr(
        "risk.advanced_shields.get_settings",
        lambda: type(
            "S",
            (),
            {"institutional_v13": {"network_outage_shield_enabled": True, "network_outage_seconds": 10}},
        )(),
    )
    blocked = check_network_outage_shield(seconds_since_success=12.0, is_disconnected=False)
    assert blocked.block_new_entries
    ok = check_network_outage_shield(seconds_since_success=3.0, is_disconnected=False)
    assert not ok.block_new_entries


def test_book_slippage_pct(monkeypatch):
    monkeypatch.setattr(
        "risk.advanced_shields.get_settings",
        lambda: type("S", (), {"max_slippage_pct": 0.1, "institutional_v13": {}})(),
    )
    ok = check_book_slippage_pct(mid_or_ref=100.0, ask_or_bid=100.05)
    assert ok.allowed
    bad = check_book_slippage_pct(mid_or_ref=100.0, ask_or_bid=100.2)
    assert not bad.allowed


def test_flash_tracker_move():
    tracker = FlashCrashTracker(window_seconds=60)
    tracker.record("BTC/USDT", 100.0, now=0.0)
    tracker.record("BTC/USDT", 94.0, now=30.0)
    mv = tracker.move_pct("BTC/USDT", now=30.0)
    assert mv is not None
    assert mv <= -5.0


def test_multi_tier_tp(monkeypatch):
    monkeypatch.setattr(
        "execution.smart_exits.get_settings",
        lambda: type(
            "S",
            (),
            {
                "breakeven_enabled": True,
                "trailing_stop_enabled": True,
                "trailing_stop_factor": 0.5,
                "institutional_v13": {
                    "multi_tier_tp_enabled": True,
                    "multi_tier_tp1_pct": 0.4,
                    "multi_tier_tp2_pct": 0.4,
                },
            },
        )(),
    )
    pos = Position(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=100.0,
        amount=1.0,
        stop_loss=97.0,
        take_profit=109.0,
    )
    # 1R = +3 → price 103
    a1 = evaluate_multi_tier_tp(pos, 103.0)
    assert a1.partial_exit_amount > 0
    assert a1.next_exit_tier == 1
    pos.exit_tier = 1
    pos.amount = 0.6
    a2 = evaluate_multi_tier_tp(pos, 106.0)
    assert a2.next_exit_tier == 2


def test_spoofing_detector(monkeypatch):
    monkeypatch.setattr(
        "core.market_filters_extra.get_settings",
        lambda: type("S", (), {"institutional_v13": {"spoofing_detector_enabled": True}})(),
    )
    bids = [(100.0, 1000.0)] + [(99.0 - i, 10.0) for i in range(9)]
    asks = [(100.1, 10.0) for _ in range(10)]
    result = detect_spoofing(bids, asks, wall_mult=5.0)
    assert not result.allowed


def test_funding_skipped_on_spot(monkeypatch):
    monkeypatch.setattr(
        "core.market_filters_extra.get_settings",
        lambda: type("S", (), {"institutional_v13": {"funding_guard_enabled": True}})(),
    )
    assert check_funding_guard(is_futures=False).allowed


def test_weekend_flat_off_by_default(monkeypatch):
    monkeypatch.setattr(
        "core.market_filters_extra.get_settings",
        lambda: type("S", (), {"institutional_v13": {"weekend_flat_enabled": False}})(),
    )
    assert check_weekend_flat_policy().allowed


def test_vol_risk_and_derisk(monkeypatch):
    monkeypatch.setattr(
        "risk.advanced_shields.get_settings",
        lambda: type(
            "S",
            (),
            {
                "institutional_v13": {
                    "vol_based_risk_scaling_enabled": True,
                    "vol_atr_high_pct": 2.5,
                    "vol_atr_extreme_pct": 4.0,
                    "vol_risk_mid_mult": 0.7,
                    "vol_risk_low_mult": 0.5,
                    "emergency_derisk_enabled": True,
                    "emergency_derisk_r_threshold": -0.7,
                    "emergency_derisk_close_fraction": 0.5,
                }
            },
        )(),
    )
    # ATR 3% of price → mid mult
    vol = vol_adjusted_risk_pct(1.0, atr=3.0, price=100.0)
    assert vol.risk_pct == 0.7
    derisk = evaluate_emergency_derisk(unrealized_r=-0.8)
    assert derisk.should_reduce
