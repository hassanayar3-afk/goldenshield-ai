#!/usr/bin/env python3
"""نشر GoldenShield إلى Windows VPS عبر WinRM (basic auth)."""
from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

import winrm

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass
REMOTE = r"C:\GoldenShield_Binance"
ZIP_NAME = os.getenv("GS_DEPLOY_ZIP", "GoldenShield-Terminal-P1-20261012-e946bf2.zip")
ZIP_URL = os.getenv("GS_DEPLOY_ZIP_URL", "").strip()


def _session() -> winrm.Session:
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "").strip()
    if not host or not user:
        raise SystemExit("WIN_HOST and WIN_USER required")
    password = os.getenv("WIN_PASSWORD", "").strip()
    if not password:
        raise SystemExit("WIN_PASSWORD required")
    return winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=3600,
        operation_timeout_sec=600,
    )


def _run_ps(session: winrm.Session, ps: str) -> None:
    r = session.run_ps(ps)
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    if out.strip():
        print(out[-3000:])
    if r.status_code != 0:
        print("PS_FAIL", r.status_code, err[-1500:])
        raise SystemExit(r.status_code)


def _production_env_text() -> str:
    tpl = (ROOT / "config" / "env.production.template").read_text(encoding="utf-8")
    keys = (
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_API_KEY_2",
        "BINANCE_API_SECRET_2",
        "BINANCE_DEMO_TRADING",
        "DISCORD_WEBHOOK_URL",
        "DISCORD_BOT_TOKEN",
        "DISCORD_CHANNEL_ID",
        "DISCORD_NOTIFY_ENABLED",
        "EXECUTION_MODE",
        "EXECUTION_BACKEND",
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
    )
    text = tpl
    for k in keys:
        v = (os.getenv(k) or "").strip()
        if not v and k == "BINANCE_DEMO_TRADING":
            v = "true"
        if not v and k == "DISCORD_NOTIFY_ENABLED":
            v = "true"
        if not v and k == "EXECUTION_MODE":
            v = "paper"
        if not v:
            continue
        pat = re.compile(rf"^{re.escape(k)}=.*$", re.M)
        text = pat.sub(f"{k}={v}", text, count=1) if pat.search(text) else text.rstrip() + f"\n{k}={v}\n"
    fixed: list[str] = []
    for line in text.splitlines():
        if line.startswith("GOLDENSHIELD_OFFICIAL_ROOT="):
            fixed.append(f"GOLDENSHIELD_OFFICIAL_ROOT={REMOTE}")
        else:
            fixed.append(line)
    return "\n".join(fixed) + "\n"


def main() -> int:
    if not ZIP_URL:
        raise SystemExit("GS_DEPLOY_ZIP_URL required")
    session = _session()
    r = session.run_cmd("hostname")
    print("HOST", (r.std_out or b"").decode().strip())

    zip_url = ZIP_URL.rstrip("/") + "/" + ZIP_NAME
    ps_deploy = rf"""
$ErrorActionPreference='Stop'
$zipUrl='{zip_url}'
$root='{REMOTE}'
$zip=Join-Path $env:TEMP '{ZIP_NAME}'
Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing
if(Test-Path $root){{ Remove-Item $root -Recurse -Force }}
New-Item -ItemType Directory -Force -Path $root | Out-Null
py -c "import zipfile; z=zipfile.ZipFile(r'$zip'); z.extractall(r'$root')"
Write-Output 'EXPAND_OK'
"""
    _run_ps(session, ps_deploy)

    env_url = ZIP_URL.rstrip("/") + "/goldenshield.production.env"
    ps_env = rf"""
Invoke-WebRequest -Uri '{env_url}' -OutFile '{REMOTE}\\.env' -UseBasicParsing
Write-Output 'ENV_OK'
"""
    _run_ps(session, ps_env)

    ps_setup = rf"""
Set-Location '{REMOTE}'
Set-ExecutionPolicy -Scope Process Bypass
py -m pip install -r requirements.txt --quiet
py scripts\bootstrap_storage.py
.\deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1
New-NetFirewallRule -DisplayName 'GS Mobile 8790' -Direction Inbound -Protocol TCP -LocalPort 8790 -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName 'GS WS 8791' -Direction Inbound -Protocol TCP -LocalPort 8791 -Action Allow -ErrorAction SilentlyContinue | Out-Null
.\deploy\windows\GS_START_FULL_STACK.ps1 -Root '{REMOTE}'
$h=Invoke-RestMethod http://127.0.0.1:8790/api/health -TimeoutSec 30
Write-Output ('HEALTH '+($h|ConvertTo-Json -Compress))
"""
    _run_ps(session, ps_setup)

    print("VPS_DEPLOY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
