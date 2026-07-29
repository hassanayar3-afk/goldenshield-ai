from datetime import datetime, timezone

from audit.models.decision_record import DecisionAction, DecisionRecord
from audit.models.snapshot import MarketSnapshot
from database.connection import init_database
from database.repositories.snapshot_repo import SnapshotRepository
from database.repositories.trade_repo import TradeRepository, TradeRow


def test_trade_repo_persists_decisions_and_trades(tmp_path):
    db_path = tmp_path / "test.db"
    db = init_database(str(db_path))
    trade_repo = TradeRepository(db)
    snapshot_repo = SnapshotRepository(db)

    snapshot = MarketSnapshot(
        symbol="BTC/USDT",
        price=50000.0,
        score=9,
        signal="BUY SIGNAL",
        passed=True,
        halted=False,
        reasons=("ok",),
        sma=49000.0,
        id="snap-test-1",
        captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    snapshot_repo.save(snapshot)

    decision = DecisionRecord(
        id="dec-test-1",
        symbol="BTC/USDT",
        action=DecisionAction.ENTRY,
        reason="test entry",
        snapshot_id=snapshot.id,
        position_id="pos-1",
        shadow_consensus=True,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    trade_repo.save_decision(decision)

    trade_repo.save_trade(
        TradeRow(
            id="trade-1",
            symbol="BTC/USDT",
            side="buy",
            entry_price=50000.0,
            amount=0.01,
            status="open",
            opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        )
    )

    loaded = snapshot_repo.get("snap-test-1")
    assert loaded is not None
    assert loaded.symbol == "BTC/USDT"

    decisions = trade_repo.list_decisions()
    assert len(decisions) == 1
    assert decisions[0].action == DecisionAction.ENTRY
    assert trade_repo.decision_count() == 1


def test_migrations_are_idempotent(tmp_path):
    db_path = tmp_path / "idem.db"
    init_database(str(db_path))
    db2 = init_database(str(db_path))
    assert db2.run_migrations() == []
