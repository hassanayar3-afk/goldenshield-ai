"""بناء حزمة تحديث مع ملفات START وإرسالها عبر تيليجرام."""

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

FILES = [
    "execution/sl_attachment_guard.py",
    "execution/trade_executor.py",
    "execution/order_manager.py",
    "execution/emergency_flat.py",
    "execution/models/order.py",
    "risk/halt_policy.py",
    "risk/emergency_protocols.py",
    "risk/pre_execution_gate.py",
    "risk/risk_orchestrator.py",
    "audit/execution_events.py",
    "audit/__init__.py",
    "main.py",
    "config/settings.py",
    "config/risk_params.yaml",
    ".env.example",
    "scripts/_deploy_env.py",
    "scripts/deploy_diagnostic_watchdog.py",
    "scripts/_tmp_cron.py",
    "scripts/sync_all_settings.py",
    "scripts/check_infra_reachability.py",
    "scripts/deploy_watchdog_contabo.py",
    "scripts/diagnose_server_signals.py",
    "scripts/deploy_to_contabo.py",
    "scripts/check_contabo.py",
    "scripts/read_telegram_inbox.py",
    "scripts/wait_telegram_screenshot.py",
    "scripts/00_START_AUTO.bat",
    "scripts/00_STOP.bat",
    "scripts/WINDOWS_BOOT.bat",
    "scripts/lifecycle.py",
    "scripts/bootstrap_storage.py",
    "tests/risk/test_critical_halt_and_sl.py",
    "tests/risk/test_v112_emergency_protocols.py",
    "docs/PROJECT_COMPLETION_STATUS.md",
    "docs/EXECUTION_PROTOCOLS_AR.md",
    "00_START.bat",
    "00_STOP.bat",
    "run.bat",
    "INSTALL_AUTOSTART.bat",
    "فحص_المجلد_CHECK.bat",
    "requirements.txt",
    "deployment/contabo_setup.sh",
    "deployment/run_infrastructure_watchdog.sh",
    "docker-compose.yml",
    "docker-compose.prod.yml",
]

APPLY_SH = r"""#!/bin/bash
# تطبيق حزمة الإصلاحات على Contabo ثم إعادة التشغيل
set -euo pipefail
APP_DIR=/opt/goldenshield
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Apply GoldenShield update from: $SCRIPT_DIR ==="
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR not found"
  exit 1
fi
cd "$SCRIPT_DIR"
rsync -a --exclude '00_APPLY_AND_RESTART.sh' --exclude 'README_INSTALL_AR.txt' ./ "$APP_DIR"/
cd "$APP_DIR"
if [ -f .env ]; then
  grep -q 'REQUIRE_SL_ON_ALL_CHUNKS' .env || echo 'REQUIRE_SL_ON_ALL_CHUNKS=true' >> .env
  grep -q 'CLOSE_NAKED_TICKETS' .env || echo 'CLOSE_NAKED_TICKETS=true' >> .env
  grep -q 'MANAGE_POSITIONS_DURING_HALT' .env || echo 'MANAGE_POSITIONS_DURING_HALT=true' >> .env
  grep -q 'PRE_EXECUTION_GATE_ENABLED' .env || echo 'PRE_EXECUTION_GATE_ENABLED=true' >> .env
  grep -q 'EMERGENCY_PROTOCOLS_ENABLED' .env || echo 'EMERGENCY_PROTOCOLS_ENABLED=true' >> .env
fi
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
echo "=== DONE — check: docker logs -f goldenshield-bot ==="
"""

README = """GoldenShield — حزمة تحديث مع ملفات START
========================================
البناء: 2026-07-18-halt-sl

محتويات مهمة:
- 00_START.bat / 00_STOP.bat / فحص_المجلد_CHECK.bat  (ويندوز Binance)
- 00_APPLY_AND_RESTART.sh  (سيرفر Contabo Linux)
- ملفات الإصلاحات الحرجة v1.1.2

======= Contabo (Linux) =======
1) ارفع الأرشيف إلى السيرفر
2) unzip -o GoldenShield_UPDATE_WITH_START_20260721.zip -d /tmp/gs_update
3) cd /tmp/gs_update
4) chmod +x 00_APPLY_AND_RESTART.sh
5) bash 00_APPLY_AND_RESTART.sh

======= Windows (Binance Demo) =======
1) Extract All إلى مجلد المشروع (أو C:\\GoldenShield_Binance)
2) شغّل فحص_المجلد_CHECK.bat
3) شغّل 00_START.bat
"""


def main() -> int:
    import zipfile

    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    backup = (os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or "").strip()
    if not token or not chat:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID missing")
        return 2

    out_dir = ROOT / "storage" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "GoldenShield_UPDATE_WITH_START_20260721.zip"

    missing: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in FILES:
            src = ROOT / rel
            if not src.exists():
                missing.append(rel)
                continue
            zf.write(src, rel.replace("\\", "/"))
        zf.writestr("00_APPLY_AND_RESTART.sh", APPLY_SH)
        zf.writestr("README_INSTALL_AR.txt", README)

    print("zip", zip_path, "size", zip_path.stat().st_size)
    if missing:
        print("missing", missing)

    caption = (
        "🛡️ GoldenShield — حزمة تحديث + ملفات START\n"
        "الملف: GoldenShield_UPDATE_WITH_START_20260721.zip\n\n"
        "Contabo:\n"
        "unzip ثم: bash 00_APPLY_AND_RESTART.sh\n\n"
        "Windows:\n"
        "00_START.bat بعد فك الضغط\n\n"
        "اقرأ README_INSTALL_AR.txt"
    )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    targets = []
    for cid in (chat, backup):
        if cid and cid not in targets:
            targets.append(cid)

    for cid in targets:
        with zip_path.open("rb") as fh:
            data = requests.post(
                url,
                data={"chat_id": cid, "caption": caption},
                files={"document": (zip_path.name, fh, "application/zip")},
                timeout=180,
            ).json()
        print("send", cid[:10], "ok", data.get("ok"), data.get("description"))
        if not data.get("ok"):
            return 1
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
