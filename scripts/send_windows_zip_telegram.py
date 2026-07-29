"""تعبئة المشروع وإرساله عبر تيليجرام كبديل لـ SSH."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXCLUDE = {".venv", "__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".cursor", "htmlcov"}
EXCLUDE_SUF = {".pyc", ".pyo", ".log"}


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram config missing")
        return 1

    local: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        local[k.strip()] = v.strip()

    from scripts.windows_package import production_env

    env_txt = production_env(local)

    bat = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "py -m pip install -r requirements.txt MetaTrader5\r\n"
        "if not exist storage\\db\\backups mkdir storage\\db\\backups\r\n"
        "if not exist storage\\logs mkdir storage\\logs\r\n"
        "echo Keep MetaTrader5 open and logged in.\r\n"
        "py -u main.py\r\n"
        "pause\r\n"
    )

    zip_path = ROOT / "storage" / "goldenshield_windows_deploy.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if set(rel.parts) & EXCLUDE:
                continue
            if rel.suffix in EXCLUDE_SUF:
                continue
            if rel.name == ".env":
                continue
            if "storage" in rel.parts and rel.suffix in {".db", ".zip"}:
                continue
            zf.write(path, str(rel).replace("\\", "/"))
        zf.writestr(".env", env_txt)
        zf.writestr("START_WINDOWS.bat", bat)

    print("zip_bytes", zip_path.stat().st_size)
    caption = (
        "حزمة GoldenShield لسيرفر Windows\n"
        "1) من داخل السيرفر افتح Edge → web.telegram.org\n"
        "2) سجل دخولك وافتح محادثة البوت\n"
        "3) حمّل هذا الملف zip\n"
        "4) فكّه إلى المجلد C:\\GoldenShield\n"
        "5) ميتاتريدر مفتوح ومسجّل دخول\n"
        "6) شغّل الملف START_WINDOWS.bat"
    )
    with zip_path.open("rb") as fh:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption},
            files={"document": ("goldenshield_windows_deploy.zip", fh)},
            timeout=180,
        )
    data = response.json()
    print(response.status_code, data.get("ok"), data.get("description", "ok"))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
