#!/usr/bin/env python3
"""Push spinal-fix artifacts to Windows VPS and run Apply-SpinalFix.ps1."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r"C:\GoldenShield_Binance"

UPLOADS = [
    "scripts/gs_kill_all.ps1",
    "gs_daemon.ps1",
    "deploy_ops/gs_snapshot_writer.py",
    "deploy/windows/Ensure-GsMobileApi.ps1",
    "deploy/windows/GS_WATCHDOG.ps1",
    "deploy/windows/GS_START_FULL_STACK.ps1",
    "deploy/windows/Install-GsWindowsServices.ps1",
    "deploy/windows/REGISTER_GS_WATCHDOG.ps1",
    "deploy/windows/Apply-SpinalFix.ps1",
    "deploy/windows/STOP_BOT_FULL.bat",
    "terminal_app/routes/api_public.py",
    "control-panel-www/js/ui_components.js",
    "control-panel-www/js/ui_components.css",
]


def _session() -> winrm.Session:
    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "").strip()
    password = (os.getenv("WIN_PASSWORD") or "").strip()
    if not (host and user and password):
        raise SystemExit("WIN_HOST / WIN_USER / WIN_PASSWORD required")
    return winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=3600,
        operation_timeout_sec=900,
    )


def _upload(session: winrm.Session, rel: str) -> None:
    local = ROOT / rel
    if not local.is_file():
        print("SKIP missing", rel)
        return
    remote = REMOTE + "\\" + rel.replace("/", "\\")
    parent = str(Path(remote).parent)
    session.run_ps(f"New-Item -ItemType Directory -Force -Path '{parent}' | Out-Null")
    b64 = base64.b64encode(local.read_bytes()).decode("ascii")
    rb = remote + ".b64part"
    session.run_ps(f"Remove-Item '{rb}' -Force -EA SilentlyContinue")
    for i in range(0, len(b64), 5000):
        chunk = b64[i : i + 5000].replace("'", "''")
        session.run_ps(f"Add-Content -Path '{rb}' -Value '{chunk}' -Encoding ASCII")
    session.run_ps(
        f"[IO.File]::WriteAllBytes('{remote}', [Convert]::FromBase64String((Get-Content '{rb}' -Raw -Encoding ASCII))); "
        f"Remove-Item '{rb}' -Force"
    )
    print("UPLOADED", rel)


def main() -> int:
    session = _session()
    for rel in UPLOADS:
        _upload(session, rel)
    ps = rf"""
$Root='{REMOTE}'
Set-Location $Root
powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\deploy\windows\Apply-SpinalFix.ps1" -Root $Root
"""
    r = session.run_ps(ps)
    out = (r.std_out or b"").decode("utf-8", "replace")
    err = (r.std_err or b"").decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("STDERR:", err[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
