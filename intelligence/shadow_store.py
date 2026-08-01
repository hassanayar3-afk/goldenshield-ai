"""تخزين SQLite لركائز الظل/الفخاخ/الصندوق الأسود/الأوزان."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import get_settings
from database.connection import DatabaseConnection, init_database

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


class ShadowStore:
    def __init__(self, db: DatabaseConnection | None = None) -> None:
        if db is not None:
            self.db = db
        else:
            try:
                self.db = init_database(get_settings().db_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ShadowStore init_database: %s", exc)
                self.db = DatabaseConnection(get_settings().db_path)

    def insert_hypothesis(
        self,
        *,
        symbol: str,
        side: str,
        score: int,
        entry_price: float,
        pattern_key: str,
        watch_minutes: int,
        notes: str = "",
    ) -> int:
        now = _utc_now()
        resolve_after = now + timedelta(minutes=max(1, watch_minutes))
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO shadow_hypotheses
                (symbol, side, score, entry_price, pattern_key, status, created_at, resolve_after, notes)
                VALUES (?, ?, ?, ?, ?, 'watching', ?, ?, ?)
                """,
                (
                    symbol,
                    side,
                    int(score),
                    float(entry_price),
                    pattern_key,
                    _iso(now),
                    _iso(resolve_after),
                    notes,
                ),
            )
            return int(cur.lastrowid)

    def due_hypotheses(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        stamp = _iso(now or _utc_now())
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM shadow_hypotheses
                WHERE status = 'watching' AND resolve_after <= ?
                ORDER BY id ASC
                """,
                (stamp,),
            ).fetchall()
        return [dict(r) for r in rows]

    def resolve_hypothesis(
        self,
        hyp_id: int,
        *,
        outcome: str,
        exit_price: float,
        notes: str = "",
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE shadow_hypotheses
                SET status = 'resolved', outcome = ?, exit_price = ?, resolved_at = ?, notes = ?
                WHERE id = ?
                """,
                (outcome, float(exit_price), _iso(_utc_now()), notes, int(hyp_id)),
            )

    def recent_fail_streak(self, symbol: str, pattern_key: str, *, limit: int = 10) -> int:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT outcome FROM shadow_hypotheses
                WHERE symbol = ? AND pattern_key = ? AND status = 'resolved'
                ORDER BY id DESC LIMIT ?
                """,
                (symbol, pattern_key, int(limit)),
            ).fetchall()
        streak = 0
        for row in rows:
            if str(row["outcome"] or "") == "fail":
                streak += 1
            else:
                break
        return streak

    def set_cooldown(
        self,
        symbol: str,
        *,
        minutes: int,
        reason: str,
        pattern_key: str = "",
        fail_streak: int = 0,
    ) -> str:
        until = _utc_now() + timedelta(minutes=max(1, minutes))
        until_s = _iso(until)
        now_s = _iso(_utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO symbol_cooldowns (symbol, cooldown_until, reason, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    cooldown_until = excluded.cooldown_until,
                    reason = excluded.reason,
                    updated_at = excluded.updated_at
                """,
                (symbol, until_s, reason, now_s),
            )
            conn.execute(
                """
                INSERT INTO trap_events (symbol, pattern_key, fail_streak, cooldown_until, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (symbol, pattern_key, int(fail_streak), until_s, now_s, reason),
            )
        return until_s

    def is_cooled(self, symbol: str) -> tuple[bool, str]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT cooldown_until, reason FROM symbol_cooldowns WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        if row is None:
            return False, ""
        until = _parse(str(row["cooldown_until"]))
        if _utc_now() < until:
            return True, str(row["reason"] or "cooldown")
        return False, ""

    def insert_blackbox(
        self,
        *,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        reason: str,
        indicators: dict,
        orderbook: dict,
        weight_adjust: dict,
    ) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO blackbox_snapshots
                (symbol, side, entry_price, exit_price, pnl, reason,
                 indicators_json, orderbook_json, weight_adjust_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    side,
                    float(entry_price),
                    float(exit_price),
                    float(pnl),
                    reason,
                    json.dumps(indicators, ensure_ascii=False),
                    json.dumps(orderbook, ensure_ascii=False),
                    json.dumps(weight_adjust, ensure_ascii=False),
                    _iso(_utc_now()),
                ),
            )
            return int(cur.lastrowid)

    def get_weights(self) -> dict[str, float]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT component, weight FROM adaptive_weights").fetchall()
        return {str(r["component"]): float(r["weight"]) for r in rows}

    def set_weight(self, component: str, weight: float) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO adaptive_weights (component, weight, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(component) DO UPDATE SET
                    weight = excluded.weight,
                    updated_at = excluded.updated_at
                """,
                (component, float(weight), _iso(_utc_now())),
            )

    def count_recent_outcomes(self, *, hours: int = 24) -> dict[str, int]:
        cutoff = _iso(_utc_now() - timedelta(hours=max(1, hours)))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT outcome, COUNT(*) AS n FROM shadow_hypotheses
                WHERE status = 'resolved' AND resolved_at >= ?
                GROUP BY outcome
                """,
                (cutoff,),
            ).fetchall()
        return {str(r["outcome"] or "unknown"): int(r["n"]) for r in rows}
