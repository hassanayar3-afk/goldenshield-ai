"""Poll Telegram for text, photo, or document."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = str(os.getenv("TELEGRAM_CHAT_ID") or "")
OUT = ROOT / "storage" / "telegram_inbox"
OUT.mkdir(parents=True, exist_ok=True)
PROMPT = "جاهز — أرسل الملف أو الرسالة أو السكرين الآن وسأقرأه."


def download_file(file_id: str, dest: Path) -> Path | None:
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
        timeout=120,
    ).content
    dest.write_bytes(content)
    return dest


def save_photo(msg: dict) -> str | None:
    photos = msg.get("photo") or []
    if not photos:
        return None
    dest = OUT / f"photo_{msg.get('message_id')}.jpg"
    saved = download_file(photos[-1]["file_id"], dest)
    return str(saved) if saved else None


def save_document(msg: dict) -> str | None:
    doc = msg.get("document") or {}
    if not doc.get("file_id"):
        return None
    name = doc.get("file_name") or f"doc_{msg.get('message_id')}"
    # keep extension from original name
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    dest = OUT / f"file_{msg.get('message_id')}_{safe}"
    saved = download_file(doc["file_id"], dest)
    return str(saved) if saved else None


def main() -> int:
    if not TOKEN or not CHAT:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID", flush=True)
        return 1

    print("start", flush=True)
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=20)
    r0 = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"timeout": 0, "limit": 100},
        timeout=30,
    ).json()
    ups = r0.get("result") or []
    offset = ups[-1]["update_id"] + 1 if ups else None

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT, "text": PROMPT},
        timeout=20,
    )
    print("WAITING", "offset", offset, flush=True)

    deadline = time.time() + 300
    while time.time() < deadline:
        params: dict = {"timeout": 25, "limit": 50}
        if offset is not None:
            params["offset"] = offset
        try:
            data = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params=params,
                timeout=40,
            ).json()
        except Exception as exc:
            print("RETRY", type(exc).__name__, flush=True)
            time.sleep(2)
            continue

        for update in data.get("result") or []:
            offset = update["update_id"] + 1
            msg = update.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != CHAT:
                continue
            text = msg.get("text") or msg.get("caption") or ""
            got = False
            if text and text != PROMPT and not text.startswith("جاهز"):
                path = OUT / f"msg_{msg.get('message_id')}.txt"
                path.write_text(text, encoding="utf-8")
                print("TEXT_SAVED", path, flush=True)
                try:
                    print("TEXT:", text[:2500], flush=True)
                except UnicodeEncodeError:
                    print("TEXT_SAVED_OK", path.name, flush=True)
                got = True
            photo = save_photo(msg)
            if photo:
                print("PHOTO_SAVED", photo, flush=True)
                got = True
            doc = save_document(msg)
            if doc:
                print("FILE_SAVED", doc, flush=True)
                got = True
            if got:
                return 0
        time.sleep(1)

    print("TIMEOUT", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
