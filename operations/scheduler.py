"""جدولة مهام التشغيل — تقرير يومي."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class DailyReportScheduler:
    _last_report_day: date | None = field(default=None, repr=False)

    def should_run_daily_report(self, today: date | None = None) -> bool:
        current = today or date.today()
        if self._last_report_day == current:
            return False
        return True

    def mark_daily_report_sent(self, today: date | None = None) -> None:
        self._last_report_day = today or date.today()
