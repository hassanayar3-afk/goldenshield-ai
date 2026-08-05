"""أنشئ حزمة مشروع كاملة وأرسلها إلى تيليجرام."""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_FILES = {
    "storage/db/goldenshield.db",
}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_str = str(rel).replace("\\", "/")
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if rel_str in EXCLUDE_FILES:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if "storage" in rel.parts and path.suffix.lower() in {".db", ".zip"}:
        return False
    return True


def build_zip() -> Path:
    out_dir = ROOT / "storage"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "goldenshield_full_project_package.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if not should_include(path):
                continue
            rel = path.relative_to(ROOT)
            zf.write(path, str(rel).replace("\\", "/"))
        zf.writestr(
            "INSTALL_FULL_README.txt",
            (
                "GoldenShield full project package\n\n"
                "1. Extract all files into C:\\GoldenShield_Binance\\\n"
                "2. Install requirements with: pip install -r requirements.txt\n"
                "3. Keep the included .env if you want the same current configuration.\n"
                "4. Start with START_BOT.bat\n"
                "5. Restart with REST_BOT.bat\n"
                "6. Stop with STOP_BOT.bat\n"
                "7. Watch live signals with BOT_WINDOW.bat\n"
            ),
        )
    return zip_path


def send_telegram(zip_path: Path) -> None:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError("Telegram config missing")

    caption = (
        "حزمة GoldenShield كاملة\n"
        "تشمل ملفات التشغيل + الكود + قواعد المشروع الحالية.\n"
        "فكّها داخل C:\\GoldenShield_Binance ثم ثبّت المتطلبات وشغّل START_BOT.bat."
    )
    with zip_path.open("rb") as fh:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption},
            files={"document": (zip_path.name, fh, "application/zip")},
            timeout=300,
        )
    data = response.json()
    print("TELEGRAM_SEND", response.status_code, data.get("ok"), data.get("description", "ok"))
    if not data.get("ok"):
        raise RuntimeError("Telegram send failed")


def main() -> int:
    try:
        zip_path = build_zip()
        print("PACKAGE_READY", zip_path.name, zip_path.stat().st_size)
        send_telegram(zip_path)
        print("DONE")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("ERROR", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
