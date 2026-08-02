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
        # طبقة مضافة: نسخة ملف مرتبة بالشهر (لا تكسر الحفظ في DB عند الفشل)
        try:
            from datetime import date as date_cls

            from operations.report_archive import save_daily_report_file

            save_daily_report_file(content, report_date=date_cls.fromisoformat(report_date))
        except Exception:
            pass

    def list_daily_reports(self, start_date: str, end_date: str) -> list[tuple[str, str]]:
        """يعيد [(report_date, content), ...] ضمن الفترة inclusive."""
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT report_date, content
                FROM daily_reports
                WHERE report_date >= ? AND report_date <= ?
                ORDER BY report_date ASC
                """,
                (start_date, end_date),
            ).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]
