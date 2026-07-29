"""إعداد / اكتشاف وجهة أرشيف النسخ الاحتياطية."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _env() -> tuple[str, str | None, str]:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN") or ""
    channel = os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or None
    personal = os.getenv("TELEGRAM_CHAT_ID") or ""
    return token, channel, personal


def _discover_channel_ids(token: str) -> list[tuple[str, str]]:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url, params={"timeout": 0, "limit": 100}, timeout=30)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "getUpdates failed"))

    found: dict[str, str] = {}
    for update in data.get("result") or []:
        for key in ("channel_post", "my_chat_member", "message"):
            payload = update.get(key)
            if not isinstance(payload, dict):
                continue
            chat = payload.get("chat") or {}
            if chat.get("type") != "channel":
                continue
            cid = str(chat.get("id", ""))
            title = str(chat.get("title") or chat.get("username") or cid)
            if cid:
                found[cid] = title
    return sorted(found.items(), key=lambda x: x[1].lower())


def _patch_env(channel_id: str) -> None:
    env_path = ROOT / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    line = f"TELEGRAM_BACKUP_CHANNEL_ID={channel_id}"
    if re.search(r"^TELEGRAM_BACKUP_CHANNEL_ID=.*$", text, flags=re.M):
        text = re.sub(r"^TELEGRAM_BACKUP_CHANNEL_ID=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    env_path.write_text(text, encoding="utf-8")
    print(f"تم تحديث .env → {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="إعداد أرشيف GoldenShield Vault")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument(
        "--channel-id",
        help="معرّف الوجهة (قناة -100... أو محادثتك الشخصية)",
    )
    parser.add_argument(
        "--personal",
        action="store_true",
        help="اربط الأرشيف بمحادثتك الشخصية (TELEGRAM_CHAT_ID)",
    )
    parser.add_argument("--skip-backup", action="store_true")
    args = parser.parse_args()

    token, channel, personal = _env()
    if not token:
        print("TELEGRAM_TOKEN غير موجود في .env")
        return 1

    if args.discover:
        try:
            channels = _discover_channel_ids(token)
        except Exception as exc:
            print(f"فشل الاكتشاف: {exc}")
            return 1
        if not channels:
            print("لم تُعثر قنوات. يمكنك استخدام --personal بدل إنشاء قناة.")
            return 2
        for cid, title in channels:
            print(f"  {cid}  —  {title}")
        return 0

    if args.personal:
        if not personal:
            print("TELEGRAM_CHAT_ID غير موجود")
            return 1
        channel_id = personal
        _patch_env(channel_id)
    else:
        channel_id = args.channel_id or channel or personal
        if args.channel_id:
            _patch_env(args.channel_id)

    if not channel_id:
        print("ضع TELEGRAM_BACKUP_CHANNEL_ID أو استخدم --personal")
        return 1

    from config.settings import load_settings
    from database.backup_manager import BackupManager
    from database.telegram_backup import send_vault_intro, upload_backup_to_telegram

    settings = load_settings(reload=True)

    intro = send_vault_intro(channel_id=channel_id)
    print(intro.message)
    if not intro.uploaded:
        return 1

    if not args.skip_backup:
        mgr = BackupManager(settings.db_path)
        backup = mgr.create_backup()
        if not backup.success:
            print(backup.message)
            return 1
        upload = upload_backup_to_telegram(backup.path or "", channel_id=channel_id)
        print(upload.message)
        return 0 if upload.uploaded else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
