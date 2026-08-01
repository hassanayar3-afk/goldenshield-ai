"""اختبارات ركائز Shadow Stress / Cognitive."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from database.connection import init_database
from intelligence.black_box_logger import record_losing_trade_blackbox
from intelligence.shadow_store import ShadowStore
from intelligence.shadow_stress_engine import (
    maybe_register_shadow_hypothesis,
    resolve_due_shadow_hypotheses,
    symbol_is_cooled,
)
from intelligence.trap_detector import evaluate_traps_after_fail
from risk.risk_committee import evaluate_risk_committee


def test_shadow_register_and_resolve(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHADOW_STRESS_ENABLED", "true")
    monkeypatch.setenv("SHADOW_MIN_PERCENT", "90")
    monkeypatch.setenv("SHADOW_WATCH_MINUTES", "15")

    db = init_database(str(tmp_path / "t.db"))
    store = ShadowStore(db)

    hyp_id = maybe_register_shadow_hypothesis(
        symbol="ADA/USDT",
        signal="BUY SIGNAL",
        score=9,
        price=0.17,
        store=store,
    )
    assert hyp_id is not None

    with store.db.connect() as conn:
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        conn.execute(
            "UPDATE shadow_hypotheses SET resolve_after = ? WHERE id = ?",
            (past, hyp_id),
        )

    resolved = resolve_due_shadow_hypotheses({"ADA/USDT": 0.18}, store=store)
    assert resolved
    assert resolved[0]["outcome"] == "pass"


def test_trap_cooldown_after_three_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHADOW_STRESS_ENABLED", "true")
    monkeypatch.setenv("TRAP_FAIL_STREAK", "3")
    monkeypatch.setenv("TRAP_COOLDOWN_MINUTES", "60")

    db = init_database(str(tmp_path / "trap.db"))
    store = ShadowStore(db)
    pattern = "buy:auto90"
    for i in range(3):
        hid = store.insert_hypothesis(
            symbol="BTC/USDT",
            side="buy",
            score=9,
            entry_price=100.0 + i,
            pattern_key=pattern,
            watch_minutes=1,
        )
        store.resolve_hypothesis(hid, outcome="fail", exit_price=99.0)

    cooled = evaluate_traps_after_fail(
        symbol="BTC/USDT",
        pattern_key=pattern,
        store=store,
    )
    assert cooled is True
    is_cool, reason = symbol_is_cooled("BTC/USDT", store=store)
    assert is_cool is True
    assert "Trap" in reason or "فشل" in reason


def test_blackbox_records_loss_and_alerts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ADAPTIVE_WEIGHTS_ENABLED", "true")
    db = init_database(str(tmp_path / "bb.db"))

    monkeypatch.setattr(
        "intelligence.black_box_logger.ShadowStore",
        lambda: ShadowStore(db),
    )
    monkeypatch.setattr(
        "intelligence.adaptive_weights.ShadowStore",
        lambda: ShadowStore(db),
    )

    alerts = MagicMock()
    snap_id = record_losing_trade_blackbox(
        symbol="SOL/USDT",
        side="buy",
        entry_price=100.0,
        exit_price=95.0,
        pnl=-5.0,
        reason="Stop Loss",
        alerts=alerts,
    )
    assert snap_id is not None
    alerts.dispatch.assert_called_once()
    title = alerts.dispatch.call_args[0][1]
    assert "صندوق أسود" in title


def test_risk_committee_blocks_cooled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RISK_COMMITTEE_ENABLED", "true")
    monkeypatch.setenv("ORDERBOOK_IMBALANCE_GATE_ENABLED", "false")
    monkeypatch.setenv("SHADOW_STRESS_ENABLED", "true")

    db = init_database(str(tmp_path / "comm.db"))
    store = ShadowStore(db)
    store.set_cooldown("ETH/USDT", minutes=60, reason="test cool")

    import risk.risk_committee as rc

    monkeypatch.setattr(
        rc,
        "symbol_is_cooled",
        lambda symbol: ShadowStore(db).is_cooled(symbol),
    )

    decision = evaluate_risk_committee(
        symbol="ETH/USDT",
        side="buy",
        score=9,
        signal="BUY SIGNAL",
    )
    assert decision.approved is False
    assert "مبرَّد" in decision.reason or "cool" in decision.reason.lower()


def test_committee_off_passes(monkeypatch) -> None:
    monkeypatch.setenv("RISK_COMMITTEE_ENABLED", "false")
    d = evaluate_risk_committee(
        symbol="XRP/USDT",
        side="buy",
        score=8,
        signal="BUY SIGNAL",
    )
    assert d.approved is True
    assert d.source == "off"
