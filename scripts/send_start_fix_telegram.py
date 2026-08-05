"""إرسال ملفات START المصلحة عبر تيليجرام (حزمة صغيرة)."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "00_START.bat",
    "00_START_KEEP_OPEN.bat",
    "00_START_VISIBLE.vbs",
    "00_STOP.bat",
    "فحص_المجلد_CHECK.bat",
]

README = """إصلاح ملف START — GoldenShield Binance Demo
===========================================
المشكلة القديمة:
- النافذة تُغلق وحدها
- أو البوت يخرج فوراً بسبب user_stopped.flag
- أو Python من متجر Microsoft لا يعمل
- لذلك لا تظهر إشارات على تيليجرام

الحل:
1) انسخ هذه الملفات داخل مجلد البوت (مثال C:\\GoldenShield_Binance)
   واستبدل الملفات القديمة
2) انقر مرتين على: 00_START_VISIBLE.vbs
   (هذا الأفضل — النافذة تبقى مفتوحة)
   أو: 00_START_KEEP_OPEN.bat
   أو: 00_START.bat
3) اترك النافذة السوداء مفتوحة
4) خلال دقيقة تظهر الإشارات/البث الحي على تيليجرام

إذا ظهرت رسالة Python not found:
ثبّت Python من python.org مع خيار Add to PATH ثم أعد التشغيل.
"""


def main() -> int:
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("missing telegram env")
        return 1

    out = ROOT / "storage" / "GOLDENSHIELD_START_FIX.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            path = ROOT / name
            if not path.is_file():
                print("missing", name)
                return 1
            zf.write(path, name)
        zf.writestr("README_START_FIX_AR.txt", README)

    # Sync into build_binance START strings by rewriting package sources from disk files
    size_mb = out.stat().st_size / (1024 * 1024)
    caption = (
        "🛠️ إصلاح ملف START — لا يغلق نفسه\n"
        f"الملف: GOLDENSHIELD_START_FIX.zip ({size_mb:.2f} MB)\n\n"
        "1) فك الضغط داخل مجلد البوت\n"
        "2) شغّل الأفضل: 00_START_VISIBLE.vbs\n"
        "3) اترك النافذة مفتوحة\n"
        "4) الإشارات تظهر على تيليجرام خلال دقيقة\n\n"
        "Binance Demo فقط"
    )

    targets: list[str] = []
    for cid in (chat, os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or ""):
        if cid and cid not in targets:
            targets.append(cid)

    for cid in targets:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": cid,
                "text": (
                    "🔧 سبب خروج START لوحده غالباً:\n"
                    "• علامة إيقاف قديمة user_stopped.flag\n"
                    "• أو Python غير مثبت/متجر ويندوز\n"
                    "• أو تشغيل الملف من مجلد ناقص\n\n"
                    "أرسلت لك ملفات START مصلحة الآن."
                ),
            },
            timeout=60,
        )
        with out.open("rb") as fh:
            data = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": cid, "caption": caption},
                files={"document": ("GOLDENSHIELD_START_FIX.zip", fh, "application/zip")},
                timeout=180,
            ).json()
        print(str(cid)[:12], data.get("ok"), data.get("description", "ok"))
        if not data.get("ok"):
            return 1

    print("SENT", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
