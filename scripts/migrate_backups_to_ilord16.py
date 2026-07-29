"""رفع كل النسخ المحلية إلى قناة t.me/ilord16 وربطها كوجهة دائمة."""

from __future__ import annotations

import importlib.util
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "@ilord16"


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or CHANNEL
    if not token:
        print("TELEGRAM_TOKEN ناقص")
        return 1

    me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
    bot_id = (me.get("result") or {}).get("id")
    print("bot:", (me.get("result") or {}).get("username"))

    info = requests.get(
        f"https://api.telegram.org/bot{token}/getChat",
        params={"chat_id": chat},
        timeout=15,
    ).json()
    print("chat:", info.get("ok"), (info.get("result") or {}).get("title"))

    if bot_id:
        mem = requests.get(
            f"https://api.telegram.org/bot{token}/getChatMember",
            params={"chat_id": chat, "user_id": bot_id},
            timeout=15,
        ).json()
        status = ((mem.get("result") or {}).get("status"))
        print("bot_status:", status, mem.get("description", ""))
        # بعض القنوات العامة ترفض getChatMember — نجرّب الإرسال مباشرة

    intro = (
        "🛡️ <b>النسخ الاحتياطي</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "<b>قناة أرشيف GoldenShield AI الرسمية</b>\n"
        "https://t.me/ilord16\n\n"
        "📌 كل النسخ الاحتياطية تُحفظ هنا تلقائياً.\n"
        "حمّل أي ملف .db عند الحاجة للاستعادة."
    )
    r1 = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat,
            "text": intro,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    d1 = r1.json()
    print("intro:", d1.get("ok"), d1.get("description", "ok"))
    if not d1.get("ok"):
        return 1

    env = (os.getenv("ENV") or "dev").strip().lower()
    default = {
        "dev": "storage/db/goldenshield_dev.db",
        "staging": "storage/db/goldenshield_staging.db",
        "production": "storage/db/goldenshield.db",
        "prod": "storage/db/goldenshield.db",
    }.get(env, "storage/db/goldenshield_dev.db")
    src = ROOT / (os.getenv("DB_PATH") or default)
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        conn_path = ROOT / "database" / "connection.py"
        spec = importlib.util.spec_from_file_location("gs_db_connection", conn_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_database(str(src))
        print("created db:", src)

    bdir = src.parent / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    latest = bdir / f"{src.stem}_{stamp}.db"
    shutil.copy2(src, latest)

    mode = os.getenv("EXECUTION_MODE", "paper")
    size_kb = latest.stat().st_size / 1024
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    caption = (
        "🛡️ <b>النسخ الاحتياطي</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "📦 <b>نسخة جديدة من GoldenShield</b>\n\n"
        f"📁 <code>{latest.name}</code>\n"
        f"📏 <code>{size_kb:.1f} KB</code>\n"
        f"🌐 <code>{env}</code> · <code>{mode}</code>\n"
        f"🕒 <code>{now}</code>\n\n"
        "♻️ للاستعادة: حمّل الملف وشغّل scripts/restore_backup.py"
    )
    with latest.open("rb") as fh:
        r2 = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
            files={"document": (latest.name, fh)},
            timeout=60,
        )
    d2 = r2.json()
    print("latest:", d2.get("ok"), d2.get("description", "ok"), latest.name)
    if not d2.get("ok"):
        return 1

    for path in sorted(bdir.glob("*.db")):
        if path.name == latest.name:
            continue
        with path.open("rb") as fh:
            rr = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={
                    "chat_id": chat,
                    "caption": f"📦 نسخة سابقة\n<code>{path.name}</code>",
                    "parse_mode": "HTML",
                },
                files={"document": (path.name, fh)},
                timeout=60,
            )
        print("prev:", path.name, rr.json().get("ok"), rr.json().get("description", "ok"))

    print("DONE -> https://t.me/ilord16")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
