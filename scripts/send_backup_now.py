"""إنشاء نسخة احتياطية فورية ورفعها إلى محادثتك الشخصية / قناة الأرشيف."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _resolve_db_path() -> Path:
    env = (os.getenv("ENV") or "dev").strip().lower()
    default_name = {
        "dev": "storage/db/goldenshield_dev.db",
        "staging": "storage/db/goldenshield_staging.db",
        "production": "storage/db/goldenshield.db",
        "prod": "storage/db/goldenshield.db",
    }.get(env, "storage/db/goldenshield_dev.db")
    return ROOT / (os.getenv("DB_PATH") or default_name)


def _ensure_db(src: Path) -> None:
    if src.exists():
        return
    src.parent.mkdir(parents=True, exist_ok=True)
    conn_path = ROOT / "database" / "connection.py"
    spec = importlib.util.spec_from_file_location("gs_db_connection", conn_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("تعذر تحميل database/connection.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.init_database(str(src))


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("TELEGRAM_BACKUP_CHANNEL_ID / TELEGRAM_CHAT_ID غير مُعدّ")
        return 1

    src = _resolve_db_path()
    _ensure_db(src)

    bdir = src.parent / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = bdir / f"{src.stem}_{stamp}.db"
    shutil.copy2(src, dst)

    env = os.getenv("ENV", "dev")
    mode = os.getenv("EXECUTION_MODE", "paper")
    size_kb = dst.stat().st_size / 1024
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    caption = (
        "🛡️ <b>النسخ الاحتياطي</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "📦 <b>نسخة جديدة من GoldenShield</b>\n\n"
        f"📁 <code>{dst.name}</code>\n"
        f"📏 <code>{size_kb:.1f} KB</code>\n"
        f"🌐 <code>{env}</code> · <code>{mode}</code>\n"
        f"🕒 <code>{now}</code>\n\n"
        "♻️ للاستعادة: حمّل الملف وشغّل scripts/restore_backup.py"
    )
    with dst.open("rb") as fh:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
            files={"document": (dst.name, fh)},
            timeout=60,
        )
    data = response.json()
    if not data.get("ok"):
        print("فشل الرفع:", data.get("description"))
        return 1
    print(f"رُفعت النسخة إلى محادثتك: {dst.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
