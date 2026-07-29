"""Poll Telegram for a photo from the configured chat (no SSH)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = str(os.getenv("TELEGRAM_CHAT_ID") or "")
OUT = ROOT / "storage" / "telegram_inbox"
OUT.mkdir(parents=True, exist_ok=True)


def save_photo(msg: dict) -> str | None:
    photos = msg.get("photo") or []
    if not photos:
        return None
    file_id = photos[-1]["file_id"]
    fr = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=30,
    ).json()
    path = (fr.get("result") or {}).get("file_path")
    if not path:
        return None
    content = requests.get(
        f"https://api.telegram.org/file/bot{TOKEN}/{path}",
        timeout=60,
    ).content
    dest = OUT / f"photo_{msg.get('message_id')}.jpg"
    dest.write_bytes(content)
    return str(dest)


def main() -> int:
    if not TOKEN or not CHAT:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return 1

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT,
            "text": "أرسل السكرين الآن — جاهز لقراءته.",
        },
        timeout=20,
    )

    deadline = time.time() + 300
    last_offset: int | None = None
    while time.time() < deadline:
        params: dict = {"timeout": 25, "limit": 50}
        if last_offset is not None:
            params["offset"] = last_offset
        data = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params=params,
            timeout=40,
        ).json()
        for update in data.get("result") or []:
            last_offset = update["update_id"] + 1
            msg = update.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != CHAT:
                continue
            text = msg.get("text") or msg.get("caption") or ""
            if text:
                path = OUT / f"msg_{msg.get('message_id')}.txt"
                path.write_text(text, encoding="utf-8")
                print("TEXT_SAVED", path)
            saved = save_photo(msg)
            if saved:
                print("PHOTO_SAVED", saved)
                return 0
        time.sleep(1)

    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
