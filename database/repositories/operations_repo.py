"""أرشفة سجلات التشغيل والتقارير اليومية."""

from __future__ import annotations

from datetime import datetime, timezone

from database.connection import DatabaseConnection


class OperationsRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def save_operation_log(self, level: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO operation_logs (level, message, created_at)
                VALUES (?, ?, ?)
                """,
                (level, message, now),
            )

    def save_daily_report(self, report_date: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_reports (report_date, content, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    content = excluded.content,
                    created_at = excluded.created_at
                """,
                (report_date, content, now),
            )
