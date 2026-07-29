"""إرسال القانون الحديدي الكامل — ملف واحد فقط عبر تيليجرام."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env", override=True)

DOC = ROOT / "docs" / "GOLDENSHIELD_IRON_LAW_COMPLETE_AR.md"


def main() -> int:
    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    backup = (os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or "").strip()
    if not token or not chat:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID missing")
        return 2
    if not DOC.exists():
        print("missing", DOC)
        return 1

    size = DOC.stat().st_size
    caption = (
        "🛡️ القانون الحديدي الكامل — GoldenShield AI\n"
        "ملف واحد من الألف للياء · بدون تجزئة\n"
        f"الملف: {DOC.name}\n"
        f"الحجم: {size} بايت\n\n"
        "كل القواعد والبروتوكولات والقوانين ملزمة للبوت بدون استثناء."
    )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    targets: list[str] = []
    for cid in (chat, backup):
        if cid and cid not in targets:
            targets.append(cid)

    ok = True
    for cid in targets:
        with DOC.open("rb") as fh:
            data = requests.post(
                url,
                data={"chat_id": cid, "caption": caption},
                files={
                    "document": (
                        DOC.name,
                        fh,
                        "text/markdown; charset=utf-8",
                    )
                },
                timeout=120,
            ).json()
        print("send", cid[:12], "ok=", data.get("ok"), data.get("description"))
        ok = ok and bool(data.get("ok"))

    # رسالة واحدة فقط — لا ملفات إضافية
    summary = (
        "✅ تم إرسال الملف الكامل الوحيد:\n"
        "GOLDENSHIELD_IRON_LAW_COMPLETE_AR.md\n\n"
        "هذا هو القانون الصارم للبوت من الألف للياء — ملف واحد بلا تجزئة."
    )
    for cid in targets:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": cid, "text": summary},
            timeout=60,
        ).json()
        print("msg", cid[:12], "ok=", r.get("ok"))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
