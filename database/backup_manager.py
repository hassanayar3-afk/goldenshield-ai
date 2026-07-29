"""نسخ احتياطي دوري لقاعدة البيانات."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupResult:
    success: bool
    path: str | None
    message: str


class BackupManager:
    def __init__(self, db_path: str, backup_dir: str | None = None) -> None:
        self.db_path = Path(db_path)
        root = self.db_path.parent
        self.backup_dir = Path(backup_dir or root / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> BackupResult:
        if not self.db_path.exists():
            return BackupResult(False, None, "ملف قاعدة البيانات غير موجود")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"{self.db_path.stem}_{stamp}.db"
        shutil.copy2(self.db_path, target)
        return BackupResult(True, str(target), f"نسخة احتياطية: {target.name}")

    def latest_backup(self) -> Path | None:
        files = sorted(self.backup_dir.glob(f"{self.db_path.stem}_*.db"))
        return files[-1] if files else None


@dataclass
class BackupScheduler:
    _last_backup_day: date | None = None

    def should_run_backup(self, today: date | None = None) -> bool:
        current = today or date.today()
        return self._last_backup_day != current

    def mark_backup_done(self, today: date | None = None) -> None:
        self._last_backup_day = today or date.today()
