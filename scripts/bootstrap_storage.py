"""تهيئة قاعدة البيانات والمجلدات قبل تشغيل البوت."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import load_settings
from database.connection import init_database


def bootstrap(*, reload_settings: bool = False) -> str:
    settings = load_settings(reload=reload_settings)
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    (db_path.parent / "backups").mkdir(parents=True, exist_ok=True)
    Path("storage/logs").mkdir(parents=True, exist_ok=True)
    Path("storage/runtime").mkdir(parents=True, exist_ok=True)

    db = init_database(settings.db_path)
    applied = db.run_migrations()
    return settings.db_path


def main() -> int:
    try:
        path = bootstrap(reload_settings=True)
        print(f"database_ready:{path}")
        return 0
    except Exception as exc:
        print(f"database_error:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
