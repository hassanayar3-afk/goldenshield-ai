"""بناء حزمة Contabo Demo وإرسالها عبر تيليجرام."""

from __future__ import annotations

import os
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env", override=True)

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".cursor",
    "htmlcov",
    "storage/logs",
    "storage/exports",
    "storage/telegram_inbox",
    "storage/db",
}
EXCLUDE_NAMES = {".env"}  # لا نضع .env الحقيقي داخل الأرشيف
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}

APPLY_SH = r'''#!/bin/bash
# تثبيت/تحديث GoldenShield Demo على Contabo
set -euo pipefail
APP_DIR=/opt/goldenshield
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== GoldenShield Contabo Demo Apply ==="
echo "Source: $SRC_DIR"
sudo mkdir -p "$APP_DIR" "$APP_DIR/storage/db/backups" "$APP_DIR/storage/logs"
sudo chown -R "$USER":"$USER" "$APP_DIR"

# نسخ الملفات (مع الإبقاء على .env الحالي إن وُجد)
rsync -a \
  --exclude '00_APPLY_CONTABO_DEMO.sh' \
  --exclude 'README_CONTABO_DEMO_AR.txt' \
  --exclude '.env' \
  "$SRC_DIR"/ "$APP_DIR"/

cd "$APP_DIR"

# إن لم يوجد .env: استخدم قالب الديمو
if [ ! -f .env ]; then
  if [ -f .env.demo ]; then
    cp .env.demo .env
    chmod 600 .env
    echo "تم إنشاء .env من .env.demo — راجع الأسرار إن لزم"
  else
    echo "ERROR: لا يوجد .env ولا .env.demo"
    exit 1
  fi
else
  # فرض إعدادات Demo على .env الموجود
  grep -q '^BINANCE_DEMO_TRADING=' .env && sed -i 's/^BINANCE_DEMO_TRADING=.*/BINANCE_DEMO_TRADING=true/' .env || echo 'BINANCE_DEMO_TRADING=true' >> .env
  grep -q '^EXECUTION_MODE=' .env && sed -i 's/^EXECUTION_MODE=.*/EXECUTION_MODE=paper/' .env || echo 'EXECUTION_MODE=paper' >> .env
  grep -q '^EXECUTION_BACKEND=' .env && sed -i 's/^EXECUTION_BACKEND=.*/EXECUTION_BACKEND=binance/' .env || echo 'EXECUTION_BACKEND=binance' >> .env
  echo "تم تحديث أعلام Demo على .env الحالي"
fi

# Docker
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  echo "=== DONE ==="
  docker compose ps
  echo "سجلات: docker compose logs -f"
else
  echo "Docker غير مثبت. شغّل: bash deployment/contabo_setup.sh"
  echo "أو: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python main.py"
fi
'''

README = """GoldenShield AI — حزمة Contabo Demo
=====================================
البناء: 2026-07-29-v13-institutional
الوضع: Demo Trading فقط (ليس Live)

======= على سيرفر Contabo (Linux) =======
1) ارفع الملف إلى السيرفر (أو حمّله من تيليجرام إلى السيرفر)
2) mkdir -p /tmp/gs_demo && tar -xzf GoldenShield_CONTABO_DEMO_*.tar.gz -C /tmp/gs_demo
3) cd /tmp/gs_demo
4) chmod +x 00_APPLY_CONTABO_DEMO.sh
5) bash 00_APPLY_CONTABO_DEMO.sh

المسار النهائي: /opt/goldenshield

======= إعدادات Demo الإلزامية =======
BINANCE_DEMO_TRADING=true
EXECUTION_MODE=paper
EXECUTION_BACKEND=binance

ملف .env.demo قالب جاهز — انسخه إلى /opt/goldenshield/.env إن لم يكن موجوداً
ثم عدّل TELEGRAM_* و BINANCE_* إن احتجت.

======= ملاحظات =======
- لا تشغّل بوتين على نفس TELEGRAM_CHAT_ID معاً (محلي + سيرفر)
- Live الحقيقي يحتاج مفاتيح api.binance.com منفصلة لاحقاً
"""


def _should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    # مسارات nested مثل storage/logs
    joined = rel.as_posix()
    for d in EXCLUDE_DIRS:
        if joined == d or joined.startswith(d + "/"):
            return True
    if rel.name in EXCLUDE_NAMES:
        return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def _build_env_demo() -> str:
    """قالب .env للديمو — ينقل القيم الحالية مع فرض Demo."""
    src = ROOT / ".env"
    lines_out: list[str] = [
        "# GoldenShield — Contabo Demo template",
        "# Demo only — NOT live Binance production",
        "ENV=production",
        "EXECUTION_MODE=paper",
        "EXECUTION_BACKEND=binance",
        "BINANCE_DEMO_TRADING=true",
        "AUTO_ENTRY_MIN_PERCENT=95",
        "MANUAL_ENTRY_REQUIRED=false",
        "IRON_PROTOCOL_ENABLED=true",
        "TELEGRAM_SIGNALS_ONLY=true",
        "TELEGRAM_SEND_CYCLE_SIGNALS=false",
        "LOOP_INTERVAL_SECONDS=15",
        "TRIAL_MODE=false",
        "DB_PATH=storage/db/goldenshield.db",
    ]
    keep = {
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_API_KEY_2",
        "BINANCE_API_SECRET_2",
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_BOT_USERNAME",
        "TELEGRAM_BACKUP_CHANNEL_ID",
    }
    if src.exists():
        for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in keep and v.strip():
                lines_out.append(f"{k}={v.strip()}")
    lines_out.append("BINANCE_DEMO_TRADING=true")
    lines_out.append("EXECUTION_MODE=paper")
    return "\n".join(lines_out) + "\n"


def main() -> int:
    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID missing")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_dir = ROOT / "storage" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_path = out_dir / f"GoldenShield_CONTABO_DEMO_{stamp}.tar.gz"

    with tarfile.open(tar_path, "w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if _should_skip(rel):
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"))

        # ملفات مساعدة
        def _add_text(name: str, text: str) -> None:
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            import io

            tar.addfile(info, io.BytesIO(data))

        _add_text("00_APPLY_CONTABO_DEMO.sh", APPLY_SH)
        _add_text("README_CONTABO_DEMO_AR.txt", README)
        _add_text(".env.demo", _build_env_demo())

    size_mb = tar_path.stat().st_size / (1024 * 1024)
    print("archive", tar_path, f"{size_mb:.2f} MB")
    if size_mb > 49:
        print("WARNING: Telegram bot limit ~50MB")

    caption = (
        "🛡️ GoldenShield — حزمة Contabo Demo\n"
        f"الملف: {tar_path.name}\n"
        f"الحجم: {size_mb:.1f} MB\n\n"
        "Demo فقط (ليس Live)\n\n"
        "على السيرفر:\n"
        f"tar -xzf {tar_path.name} -C /tmp/gs_demo\n"
        "cd /tmp/gs_demo\n"
        "chmod +x 00_APPLY_CONTABO_DEMO.sh\n"
        "bash 00_APPLY_CONTABO_DEMO.sh\n\n"
        "اقرأ README_CONTABO_DEMO_AR.txt"
    )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with tar_path.open("rb") as fh:
        resp = requests.post(
            url,
            data={"chat_id": chat, "caption": caption},
            files={"document": (tar_path.name, fh, "application/gzip")},
            timeout=300,
        ).json()
    print("send ok=", resp.get("ok"), "desc=", resp.get("description"))
    if not resp.get("ok"):
        return 1
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
