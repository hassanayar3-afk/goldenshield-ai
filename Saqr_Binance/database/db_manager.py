"""
SQLite persistence with WAL mode and DAO-level threading locks.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from utils.logger_config import setup_logger

logger = setup_logger("saqr.database")


@dataclass
class PositionRow:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_order_id: Optional[str]
    engine: str
    updated_at: str


class DatabaseManager:
    """Thread-safe DAO over saqr_local.db."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.getenv("DB_PATH", "saqr_local.db")
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def path(self) -> Path:
        return Path(self._db_path)

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._init_schema()
            logger.info("Database ready at %s (WAL enabled)", self.path)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @contextmanager
    def dao(self) -> Iterator[sqlite3.Connection]:
        """Acquire DAO lock for the duration of a write/read transaction."""
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE;")
            try:
                yield self._conn
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise

    def _init_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                stop_order_id TEXT,
                engine TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS balances (
                asset TEXT PRIMARY KEY,
                free REAL NOT NULL,
                locked REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS closed_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                pnl REAL NOT NULL,
                engine TEXT NOT NULL,
                closed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS engine_state (
                engine TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS protection_orders (
                client_order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                stop_price REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    def upsert_position(self, row: PositionRow) -> None:
        with self.dao() as conn:
            conn.execute(
                """
                INSERT INTO positions (symbol, side, quantity, entry_price, stop_order_id, engine, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    side=excluded.side,
                    quantity=excluded.quantity,
                    entry_price=excluded.entry_price,
                    stop_order_id=excluded.stop_order_id,
                    engine=excluded.engine,
                    updated_at=excluded.updated_at
                """,
                (
                    row.symbol,
                    row.side,
                    row.quantity,
                    row.entry_price,
                    row.stop_order_id,
                    row.engine,
                    row.updated_at,
                ),
            )

    def delete_position(self, symbol: str) -> None:
        with self.dao() as conn:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    def list_positions(self) -> List[PositionRow]:
        with self.dao() as conn:
            rows = conn.execute("SELECT * FROM positions ORDER BY symbol").fetchall()
        return [
            PositionRow(
                symbol=r["symbol"],
                side=r["side"],
                quantity=float(r["quantity"]),
                entry_price=float(r["entry_price"]),
                stop_order_id=r["stop_order_id"],
                engine=r["engine"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def upsert_balance(self, asset: str, free: float, locked: float, updated_at: str) -> None:
        with self.dao() as conn:
            conn.execute(
                """
                INSERT INTO balances (asset, free, locked, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    free=excluded.free,
                    locked=excluded.locked,
                    updated_at=excluded.updated_at
                """,
                (asset, free, locked, updated_at),
            )

    def save_engine_state(self, engine: str, payload: Dict[str, Any], updated_at: str) -> None:
        with self.dao() as conn:
            conn.execute(
                """
                INSERT INTO engine_state (engine, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(engine) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (engine, json.dumps(payload), updated_at),
            )

    def record_closed_trade(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        engine: str,
        closed_at: str,
    ) -> None:
        with self.dao() as conn:
            conn.execute(
                """
                INSERT INTO closed_trades
                (symbol, side, quantity, entry_price, exit_price, pnl, engine, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (symbol, side, quantity, entry_price, exit_price, pnl, engine, closed_at),
            )

    def register_protection_order(
        self,
        client_order_id: str,
        symbol: str,
        stop_price: float,
        status: str,
        created_at: str,
    ) -> None:
        with self.dao() as conn:
            conn.execute(
                """
                INSERT INTO protection_orders (client_order_id, symbol, stop_price, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(client_order_id) DO UPDATE SET
                    status=excluded.status
                """,
                (client_order_id, symbol, stop_price, status, created_at),
            )
