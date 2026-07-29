"""أداة مساعدة — الحصول على TELEGRAM_CHAT_ID بعد مراسلة @GoldenShield_2026_bot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv(BASE / ".env")

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
BOT_USER = os.getenv("TELEGRAM_BOT_USERNAME", "GoldenShield_2026_bot").strip()
ENV_FILE = BASE / ".env"


def _bot_id(token: str) -> str | None:
    return token.split(":", 1)[0].strip() if ":" in token else None


def _valid_chat(token: str, chat_id: str) -> bool:
    bid = _bot_id(token)
    return not (bid and str(chat_id) == bid)


def _save_chat_id(chat_id: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("TELEGRAM_CHAT_ID="):
            out.append(f"TELEGRAM_CHAT_ID={chat_id}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"TELEGRAM_CHAT_ID={chat_id}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    if not TOKEN:
        print("❌ ضع TELEGRAM_TOKEN في ملف .env أولاً")
        return 1

    me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15).json()
    if not me.get("ok"):
        print(f"❌ فشل التحقق من البوت: {me.get('description', 'خطأ')}")
        return 1

    username = me["result"].get("username", "")
    print(f"✅ البوت: @{username}")

    bid = _bot_id(TOKEN)
    if bid:
        print(f"ℹ️ Bot ID (ليس Chat ID): {bid}")

    updates = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        timeout=15,
    ).json()
    if not updates.get("ok"):
        print(f"❌ فشل getUpdates: {updates.get('description', 'خطأ')}")
        return 1

    chats: dict[str, str] = {}
    for item in updates.get("result", []):
        msg = item.get("message") or item.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        label = chat.get("username") or chat.get("first_name") or str(chat_id)
        chats[str(chat_id)] = label

    if not chats:
        print(f"\n📱 على هاتفك فقط:")
        print(f"   1) افتح Telegram")
        print(f"   2) ابحث: @{username or BOT_USER}")
        print(f"   3) اضغط Start أو أرسل: /start")
        print(f"   4) ارجع هنا وقل: تم")
        return 1

    valid = [(cid, label) for cid, label in chats.items() if _valid_chat(TOKEN, cid)]
    if not valid:
        print("❌ لا يوجد Chat ID صالح — أرسل /start من هاتفك")
        return 1

    chat_id, label = valid[0]
    _save_chat_id(chat_id)
    print(f"\n✅ تم حفظ TELEGRAM_CHAT_ID={chat_id} ({label}) في .env")

    test = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        params={"chat_id": chat_id, "text": "GoldenShield: الاتصال يعمل ✅"},
        timeout=15,
    ).json()
    if test.get("ok"):
        print("✅ رسالة اختبار أُرسلت — تحقق من هاتفك")
    else:
        print(f"⚠️ لم تُرسل الرسالة: {test.get('description', 'خطأ')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
