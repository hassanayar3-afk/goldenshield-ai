"""اختبارات تقارير الصفقات الخاسرة."""

from __future__ import annotations

from operations.loss_trade_report import (
    build_losing_trade_report,
    classify_loss,
    format_losing_trades_digest,
    save_losing_trade_report,
)


def test_classify_stop_loss() -> None:
    cat, why, factors, lessons = classify_loss(
        side="buy",
        entry_price=100.0,
        exit_price=97.0,
        stop_loss=97.0,
        take_profit=109.0,
        exit_reason="Stop Loss",
        signal_score=6,
    )
    assert cat == "stop_loss"
    assert "وقف" in why or "Stop" in why
    assert factors
    assert lessons


def test_save_and_digest(tmp_path, monkeypatch) -> None:
    import operations.loss_trade_report as mod

    monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(mod, "JSONL_PATH", tmp_path / "losing_trades.jsonl")

    report = build_losing_trade_report(
        symbol="BTC/USDT",
        side="buy",
        entry_price=50000,
        exit_price=49000,
        amount=0.01,
        pnl=-10.0,
        stop_loss=48900,
        take_profit=53000,
        exit_reason="Stop Loss",
        signal_score=8,
    )
    path = save_losing_trade_report(report)
    assert path.exists()
    digest = format_losing_trades_digest([report.__dict__], limit=5)
    assert "BTC/USDT" in digest
