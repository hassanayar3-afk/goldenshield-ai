"""مستودع الصفقات وسجلات القرارات."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from audit.models.decision_record import DecisionAction, DecisionRecord
from database.connection import DatabaseConnection


@dataclass(frozen=True)
class TradeRow:
    id: str
    symbol: str
    side: str
    entry_price: float
    amount: float
    status: str
    opened_at: str
    exit_price: float | None = None
    pnl: float | None = None
    closed_at: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    is_paper: bool = True
    breakeven_applied: bool = False
    partial_exit_done: bool = False
    signal_score: int = 0
    risk_mode: str = "standard"
    exit_tier: int = 0


class TradeRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def save_decision(self, record: DecisionRecord) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO decision_records (
                    id, symbol, action, reason, snapshot_id, position_id,
                    pnl, shadow_consensus, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.symbol,
                    record.action.value,
                    record.reason,
                    record.snapshot_id,
                    record.position_id,
                    record.pnl,
                    None if record.shadow_consensus is None else int(record.shadow_consensus),
                    record.recorded_at.isoformat(),
                ),
            )

    def save_trade(self, trade: TradeRow) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades (
                    id, symbol, side, entry_price, exit_price, amount,
                    pnl, status, opened_at, closed_at,
                    stop_loss, take_profit, is_paper, breakeven_applied,
                    partial_exit_done, signal_score, risk_mode, exit_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.id,
                    trade.symbol,
                    trade.side,
                    trade.entry_price,
                    trade.exit_price,
                    trade.amount,
                    trade.pnl,
                    trade.status,
                    trade.opened_at,
                    trade.closed_at,
                    trade.stop_loss,
                    trade.take_profit,
                    int(trade.is_paper),
                    int(trade.breakeven_applied),
                    int(trade.partial_exit_done),
                    int(trade.signal_score),
                    str(trade.risk_mode or "standard"),
                    int(getattr(trade, "exit_tier", 0) or 0),
                ),
            )

    def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        pnl: float,
    ) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE trades
                SET exit_price = ?, pnl = ?, status = 'closed', closed_at = ?
                WHERE id = ?
                """,
                (exit_price, pnl, datetime.now(timezone.utc).isoformat(), trade_id),
            )

    def list_open_trades(self) -> list[TradeRow]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM trades
                WHERE status = 'open'
                ORDER BY opened_at ASC
                """
            ).fetchall()
        return [self._row_to_trade(row) for row in rows]

    def _row_to_trade(self, row) -> TradeRow:
        keys = row.keys() if hasattr(row, "keys") else []
        def col(name: str, default=None):
            return row[name] if name in keys else default

        return TradeRow(
            id=row["id"],
            symbol=row["symbol"],
            side=row["side"],
            entry_price=float(row["entry_price"]),
            amount=float(row["amount"]),
            status=row["status"],
            opened_at=row["opened_at"],
            exit_price=None if col("exit_price") is None else float(row["exit_price"]),
            pnl=None if col("pnl") is None else float(row["pnl"]),
            closed_at=col("closed_at"),
            stop_loss=None if col("stop_loss") is None else float(row["stop_loss"]),
            take_profit=None if col("take_profit") is None else float(row["take_profit"]),
            is_paper=bool(col("is_paper", 1)),
            breakeven_applied=bool(col("breakeven_applied", 0)),
            partial_exit_done=bool(col("partial_exit_done", 0)),
            signal_score=int(col("signal_score", 0) or 0),
            risk_mode=str(col("risk_mode", "standard") or "standard"),
            exit_tier=int(col("exit_tier", 0) or 0),
        )

    def list_decisions(self, *, limit: int = 100) -> list[DecisionRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM decision_records
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        records: list[DecisionRecord] = []
        for row in rows:
            records.append(
                DecisionRecord(
                    id=row["id"],
                    symbol=row["symbol"],
                    action=DecisionAction(row["action"]),
                    reason=row["reason"],
                    snapshot_id=row["snapshot_id"],
                    position_id=row["position_id"],
                    pnl=row["pnl"],
                    shadow_consensus=(
                        None if row["shadow_consensus"] is None else bool(row["shadow_consensus"])
                    ),
                    recorded_at=datetime.fromisoformat(row["recorded_at"]),
                )
            )
        return records

    def decision_count(self) -> int:
        with self._db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM decision_records").fetchone()
        return int(row["c"]) if row else 0
