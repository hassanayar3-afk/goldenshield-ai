"""استعادة قاعدة البيانات من ملف نسخة احتياطية (محمّل من قناة Vault)."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="استعادة goldenshield.db من نسخة احتياطية")
    parser.add_argument("backup_file", help="مسار ملف .db المحمّل من القناة أو من backups/")
    parser.add_argument(
        "--force",
        action="store_true",
        help="استبدال قاعدة البيانات الحالية بدون تأكيد تفاعلي",
    )
    args = parser.parse_args()

    src = Path(args.backup_file)
    if not src.exists():
        print(f"الملف غير موجود: {src}")
        return 1
    if src.suffix.lower() != ".db":
        print("توقع ملف .db")
        return 1

    settings = load_settings(reload=True)
    dest = Path(settings.db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not args.force:
        print(f"قاعدة البيانات الحالية موجودة: {dest}")
        print("أعد التشغيل مع --force بعد إيقاف البوت (main.py).")
        return 2

    if dest.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety = dest.with_name(f"{dest.stem}_pre_restore_{stamp}.db")
        shutil.copy2(dest, safety)
        print(f"نسخة أمان قبل الاستعادة: {safety}")

    shutil.copy2(src, dest)
    print(f"تمت الاستعادة → {dest}")
    print("شغّل البوت من جديد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
