"""إرسال الملف الحديدي (من الألف للياء) عبر تيليجرام."""

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

DOC = ROOT / "docs" / "IRON_PROTOCOL_A_TO_Z_AR.md"
CODE = ROOT / "risk" / "iron_protocol.py"


def _send(token: str, chat_id: str, path: Path, caption: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with path.open("rb") as fh:
        data = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (path.name, fh, "text/markdown; charset=utf-8")},
            timeout=120,
        ).json()
    print(path.name, "->", chat_id[:12], "ok=", data.get("ok"), data.get("description"))
    return bool(data.get("ok"))


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

    targets: list[str] = []
    for cid in (chat, backup):
        if cid and cid not in targets:
            targets.append(cid)

    caption_doc = (
        "🛡️ الملف الحديدي — GoldenShield AI\n"
        "كل القواعد من الألف للياء بدون استثناء\n"
        "IRON_PROTOCOL_A_TO_Z_AR.md\n\n"
        "يفرضه الكود عبر risk/iron_protocol.py عند التشغيل\n"
        "Live: SL+TP إلزامي | Auto≥95 | R:R≥1:3 | لا تذاكر عارية"
    )
    caption_code = (
        "⚙️ كود الفرض الحديدي\n"
        "risk/iron_protocol.py\n"
        "IRON_PROTOCOL_ENABLED=true"
    )

    ok = True
    for cid in targets:
        ok = _send(token, cid, DOC, caption_doc) and ok
        if CODE.exists():
            ok = _send(token, cid, CODE, caption_code) and ok

    # رسالة نصية مختصرة
    summary = (
        "✅ تم تفعيل البروتوكول الحديدي على المشروع.\n\n"
        "• لا صفقة بلا SL و TP مؤكدين\n"
        "• لا دخول تلقائي دون 95/100\n"
        "• R:R ≥ 1:3\n"
        "• Kill Switch −3% + راحة 24س بعد 3 خسائر\n"
        "• Priority 0 لحماية رأس المال\n\n"
        "اقرأ الملف المرفق بالكامل."
    )
    for cid in targets:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": cid, "text": summary},
            timeout=60,
        ).json()
        print("message", cid[:12], "ok=", r.get("ok"))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
