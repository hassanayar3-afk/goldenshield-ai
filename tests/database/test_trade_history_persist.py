from __future__ import annotations

from database.connection import init_database
from database.repositories.trade_repo import TradeRepository, TradeRow


def test_closed_trades_remain_in_history(tmp_path):
    db_path = tmp_path / "t.db"
    db = init_database(str(db_path))
    repo = TradeRepository(db)
    repo.save_trade(
        TradeRow(
            id="pos-1",
            symbol="BTC/USDT",
            side="buy",
            entry_price=100.0,
            amount=1.0,
            status="open",
            opened_at="2026-08-01T10:00:00+00:00",
        )
    )
    repo.close_trade("pos-1", exit_price=90.0, pnl=-10.0)
    closed = repo.list_closed_trades(limit=10)
    assert len(closed) == 1
    assert closed[0].status == "closed"
    assert closed[0].pnl == -10.0
    summary = repo.trade_history_summary()
    assert summary["closed"] == 1
    assert summary["losses"] == 1
    assert summary["open"] == 0
    # لا يُحذف الصف
    assert repo.list_open_trades() == []
