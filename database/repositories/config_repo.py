"""مستودع الإعدادات المحفوظة."""

from __future__ import annotations

from datetime import datetime, timezone

from database.connection import DatabaseConnection


class ConfigRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def set(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_config WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return str(row["value"])
