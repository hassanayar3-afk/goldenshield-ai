"""إرسال حزمة Windows مسطّحة — بدون مجلد فرعي مربك."""

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

from scripts.windows_package import CHECK_BAT, START_BAT, STOP_BAT, production_env

EXCLUDE = {".venv", "__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".cursor", "htmlcov", "tests", ".github", "saas"}
EXCLUDE_SUF = {".pyc", ".pyo", ".log"}
EXCLUDE_NAME_PARTS = ("binance", "contabo", "deploy_to", "diagnose_server", "migrate_backup")
EXCLUDE_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".dockerignore",
    "SESSION_STATE.md",
    "pytest.ini",
}
EXCLUDE_SCRIPTS = {
    "test_binance_connection.py",
    "send_windows_zip_telegram.py",
    "send_simple_windows_zip.py",
    "send_iron_protocol_telegram.py",
    "send_complete_iron_law_telegram.py",
    "send_update_with_start_telegram.py",
    "deploy_to_contabo.py",
    "deploy_watchdog_contabo.py",
    "deploy_diagnostic_watchdog.py",
    "deploy_to_windows.py",
}


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    assert token and chat

    local: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        local[k.strip()] = v.strip()

    env_txt = production_env(local)
    readme = (
        "GOLDENSHIELD — Windows MT5 (حزمة تثبيت كاملة)\r\n"
        "========================================\r\n"
        "1) Extract All الى C:\\GoldenShield\r\n"
        "2) شغّل فحص_المجلد_CHECK.bat\r\n"
        "3) افتح XM MT5 وسجّل دخول يدوياً\r\n"
        "4) شغّل 00_فحص_MT5.bat واتبع التعليمات\r\n"
        "5) شغّل 00_START.bat\r\n"
        "6) Disconnect RDP — لا تعمل Log off أو Shutdown\r\n"
        "\r\n"
        "القانون الحديدي الكامل داخل:\r\n"
        "docs\\GOLDENSHIELD_IRON_LAW_COMPLETE_AR.md\r\n"
    )

    zip_path = ROOT / "storage" / "GOLDENSHIELD_MT5_WINDOWS.zip"
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
            if rel.name in EXCLUDE_SCRIPTS:
                continue
            if rel.name in EXCLUDE_FILES:
                continue
            if rel.name in {"00_START.bat", "00_STOP.bat", "فحص_المجلد_CHECK.bat"}:
                continue
            if any(part in EXCLUDE_NAME_PARTS for part in rel.as_posix().lower()):
                continue
            if "storage" in rel.parts and rel.suffix in {".db", ".zip"}:
                continue
            # وثائق كبيرة غير لازمة للتثبيت — نُبقي القانون الحديدي فقط
            if "docs" in rel.parts and rel.name != "GOLDENSHIELD_IRON_LAW_COMPLETE_AR.md":
                if rel.name not in {"MT5_WINDOWS_SETUP.md", "EXECUTION_PROTOCOLS_AR.md"}:
                    continue
            zf.write(path, str(rel).replace("\\", "/"))
        zf.writestr(".env", env_txt)
        zf.writestr("00_START.bat", START_BAT.replace("\n", "\r\n"))
        zf.writestr("00_STOP.bat", STOP_BAT.replace("\n", "\r\n"))
        zf.writestr("فحص_المجلد_CHECK.bat", CHECK_BAT.replace("\n", "\r\n"))
        zf.writestr("README_اقرأني.txt", readme)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    caption = (
        "🛡️ GOLDENSHIELD — حزمة تثبيت ZIP كاملة\r\n"
        f"الملف: GOLDENSHIELD_MT5_WINDOWS.zip ({size_mb:.1f} MB)\r\n"
        "✅ قانون حديدي + حماية SL/TP + Auto≥95 + R:R 1:3\r\n\r\n"
        "1) Extract All الى C:\\GoldenShield\r\n"
        "2) فحص_المجلد_CHECK.bat\r\n"
        "3) افتح XM MT5 وسجّل دخول\r\n"
        "4) 00_START.bat\r\n"
        "5) لا تعمل Log off — Disconnect فقط"
    )
    targets: list[str] = []
    for cid in (chat, os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or ""):
        if cid and cid not in targets:
            targets.append(cid)
    ok = True
    for cid in targets:
        with zip_path.open("rb") as fh:
            data = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": cid, "caption": caption},
                files={"document": ("GOLDENSHIELD_MT5_WINDOWS.zip", fh)},
                timeout=300,
            ).json()
        print(cid[:12], data.get("ok"), data.get("description", "ok"), f"{size_mb:.1f}MB")
        ok = ok and bool(data.get("ok"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
