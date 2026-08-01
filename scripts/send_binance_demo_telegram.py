"""بناء حزمة Binance Demo نظيفة وإرسالها عبر تيليجرام."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_binance_demo_package import (  # noqa: E402
    README,
    START_BINANCE,
    STOP_BINANCE,
    build_zip,
    load_local_env,
)
from scripts.windows_package import CHECK_BAT  # noqa: E402

ZIP_NAME = "GOLDENSHIELD_BINANCE_DEMO.zip"


def send_zip(zip_path: Path, *, token: str, chat_ids: list[str]) -> bool:
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    if size_mb >= 49.5:
        print(f"ZIP too large for Telegram bot API: {size_mb:.1f} MB")
        return False

    caption = (
        "🛡️ GoldenShield — حزمة نظيفة Binance Demo فقط\n"
        f"الملف: {ZIP_NAME} ({size_mb:.1f} MB)\n\n"
        "✅ مرتبطة بـ Binance Demo فقط\n"
        "❌ ليست MetaTrader / ليست فوركس / ليست حساب حقيقي\n\n"
        "الإعدادات:\n"
        "• EXECUTION_BACKEND=binance\n"
        "• BINANCE_DEMO_TRADING=true\n"
        "• MT5_ENABLED=false\n"
        "• إشارات تيليجرام من 85/100\n"
        "• دخول تلقائي من 90/100\n"
        "• بث حي كل 15 ثانية\n\n"
        "التثبيت:\n"
        "1) احذف الحزم القديمة\n"
        "2) Extract All إلى C:\\GoldenShield_Binance\n"
        "3) فحص_المجلد_CHECK.bat\n"
        "4) 00_START.bat\n"
        "5) في تيليجرام: /start\n\n"
        "اقرأ README_BINANCE_AR.txt داخل الحزمة"
    )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    ok_all = True
    for cid in chat_ids:
        with zip_path.open("rb") as fh:
            data = requests.post(
                url,
                data={"chat_id": cid, "caption": caption},
                files={"document": (ZIP_NAME, fh, "application/zip")},
                timeout=300,
            ).json()
        print(
            "send",
            str(cid)[:12],
            "ok",
            data.get("ok"),
            data.get("description", "ok"),
            f"{size_mb:.1f}MB",
        )
        ok_all = ok_all and bool(data.get("ok"))
    return ok_all


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return 1

    local = load_local_env()
    zip_path = build_zip(local)
    print("ZIP=", zip_path, f"({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # مزامنة ملفات البدء المحلية مع الحزمة
    (ROOT / "00_START.bat").write_text(START_BINANCE, encoding="utf-8")
    (ROOT / "00_STOP.bat").write_text(STOP_BINANCE, encoding="utf-8")
    (ROOT / "فحص_المجلد_CHECK.bat").write_text(CHECK_BAT, encoding="utf-8")
    (ROOT / "README_BINANCE_AR.txt").write_text(README, encoding="utf-8")

    targets: list[str] = []
    for cid in (chat, os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or ""):
        if cid and cid not in targets:
            targets.append(cid)

    # رسالة تمهيدية قصيرة
    for cid in targets:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": cid,
                "text": (
                    "📦 جارٍ إرسال حزمة GoldenShield النظيفة\n"
                    "Binance Demo فقط — بدون MetaTrader وبدون حساب حقيقي"
                ),
            },
            timeout=60,
        )

    if not send_zip(zip_path, token=token, chat_ids=targets):
        return 1
    print("TELEGRAM_SEND_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
