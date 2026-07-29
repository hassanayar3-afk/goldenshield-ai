"""مستودع Snapshots."""

from __future__ import annotations

import json
from datetime import datetime

from audit.models.snapshot import MarketSnapshot
from database.connection import DatabaseConnection


class SnapshotRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def save(self, snapshot: MarketSnapshot) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO market_snapshots (
                    id, symbol, price, score, signal, passed, halted,
                    reasons, sma, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.symbol,
                    snapshot.price,
                    snapshot.score,
                    snapshot.signal,
                    int(snapshot.passed),
                    int(snapshot.halted),
                    json.dumps(list(snapshot.reasons), ensure_ascii=False),
                    snapshot.sma,
                    snapshot.captured_at.isoformat(),
                ),
            )

    def get(self, snapshot_id: str) -> MarketSnapshot | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        return MarketSnapshot(
            id=row["id"],
            symbol=row["symbol"],
            price=row["price"],
            score=row["score"],
            signal=row["signal"],
            passed=bool(row["passed"]),
            halted=bool(row["halted"]),
            reasons=tuple(json.loads(row["reasons"])),
            sma=row["sma"],
            captured_at=datetime.fromisoformat(row["captured_at"]),
        )

    def count(self) -> int:
        with self._db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM market_snapshots").fetchone()
        return int(row["c"]) if row else 0
