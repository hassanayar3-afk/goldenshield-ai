#!/usr/bin/env python3
"""Deploy Discord sovereign migration to Windows VPS."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPLOADS = [
    "gs_discord_bot.py",
    "main.py",
    "gs_daemon.ps1",
    "requirements.txt",
    "operations/alert_dispatcher.py",
    "operations/pre_flight_checklist.py",
    "operations/infrastructure_watchdog.py",
    "operations/__init__.py",
    "database/telegram_backup.py",
    "database/__init__.py",
    "config/settings.py",
    "deploy/windows/Ensure-GsServices.ps1",
    "deploy/windows/START_GS_DISCORD_BOT.ps1",
    "deploy/windows/Install-GsWindowsServices.ps1",
    "scripts/gs_kill_all.ps1",
    "deploy_ops/verify_discord_sovereign.py",
    "deploy_ops/gs_snapshot_writer.py",
    "deploy/windows/Ensure-GsMobileApi.ps1",
]


def main() -> int:
    upload = ROOT / "deploy_ops" / "winrm_upload_file.py"
    for rel in UPLOADS:
        r = subprocess.run([sys.executable, str(upload), rel], cwd=str(ROOT))
        if r.returncode != 0:
            print("UPLOAD_FAIL", rel)
            return r.returncode
    import os
    import winrm
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "").strip()
    password = (os.getenv("WIN_PASSWORD") or "").strip()
    remote = r"C:\GoldenShield_Binance"
    s = winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=3600,
        operation_timeout_sec=900,
    )
    ps = f"""
$Root='{remote}'
Set-Location $Root
$py=& "$Root\\deploy\\windows\\Resolve-GsPython.ps1" -Root $Root
& $py -m pip install --upgrade pip
& $py -m pip install discord.py aiohttp python-dotenv
powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\\deploy\\windows\\Ensure-GsServices.ps1" -Root $Root
& $py "$Root\\deploy_ops\\verify_discord_sovereign.py"
"""
    out = (s.run_ps(ps).std_out or b"").decode("utf-8", "replace")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
