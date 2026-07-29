"""One-shot Telegram inbox fetch (no Contabo SSH)."""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = str(os.getenv("TELEGRAM_CHAT_ID") or "")
OUT = ROOT / "storage" / "telegram_inbox"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    if not TOKEN or not CHAT:
        print("Missing TELEGRAM config")
        return 1

    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=20)
    data = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"limit": 100, "timeout": 0},
        timeout=60,
    ).json()
    updates = data.get("result") or []
    print("ok", data.get("ok"), "n", len(updates))
    found = 0
    last = None
    for u in updates:
        last = u["update_id"]
        msg = u.get("message") or u.get("edited_message") or {}
        if str((msg.get("chat") or {}).get("id", "")) != CHAT:
            continue
        mid = msg.get("message_id")
        text = msg.get("text") or msg.get("caption") or ""
        if text:
            path = OUT / f"msg_{mid}.txt"
            path.write_text(text, encoding="utf-8")
            print("TEXT", mid, text[:500])
            found += 1
        photos = msg.get("photo") or []
        if photos:
            file_id = photos[-1]["file_id"]
            fr = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getFile",
                params={"file_id": file_id},
                timeout=30,
            ).json()
            path = (fr.get("result") or {}).get("file_path")
            if path:
                content = requests.get(
                    f"https://api.telegram.org/file/bot{TOKEN}/{path}",
                    timeout=60,
                ).content
                dest = OUT / f"photo_{mid}.jpg"
                dest.write_bytes(content)
                print("PHOTO", dest, len(content))
                found += 1
        doc = msg.get("document")
        if doc:
            name = doc.get("file_name") or f"doc_{mid}"
            print("DOC", mid, name, doc.get("mime_type"))
            found += 1
            file_id = doc.get("file_id")
            mime = str(doc.get("mime_type") or "")
            if file_id and (mime.startswith("image") or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
                fr = requests.get(
                    f"https://api.telegram.org/bot{TOKEN}/getFile",
                    params={"file_id": file_id},
                    timeout=30,
                ).json()
                path = (fr.get("result") or {}).get("file_path")
                if path:
                    content = requests.get(
                        f"https://api.telegram.org/file/bot{TOKEN}/{path}",
                        timeout=60,
                    ).content
                    dest = OUT / f"doc_{mid}_{name}"
                    dest.write_bytes(content)
                    print("DOC_SAVED", dest)

    print("FOUND", found)
    if last is not None:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": last + 1, "timeout": 0},
            timeout=30,
        )
    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
