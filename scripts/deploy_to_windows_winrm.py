#!/usr/bin/env python3
"""Sync slim GoldenShield tree + .env to VPS via WinRM, then start stack."""

from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._win_ssh import load_local_env_for_deploy  # noqa: E402
from scripts.remote_vps_apply_winrm import (  # noqa: E402
    REMOTE,
    _production_env_bytes,
    _redact,
    _session,
    _upload_bytes,
)

SLIM_EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "tests",
    ".github",
    "docs",
    "saas",
    "dist",
    "downloads",
    "mobile_android",
    "storage",
    "deployment",
    "ProgramData",
    "audit",
}


def build_slim_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if set(rel.parts) & SLIM_EXCLUDE_DIRS:
                continue
            if rel.name in {".env", "goldenshield.env"}:
                continue
            if rel.suffix in {".pyc", ".pyo"}:
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"))

        data = _production_env_bytes()
        info = tarfile.TarInfo(name=".env")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    load_dotenv(ROOT / "goldenshield.env", override=True)

    archive = build_slim_archive()
    print(f"slim_archive={len(archive)/1024:.1f} KB")

    session = _session()
    probe = session.run_cmd("hostname")
    print("HOST", (probe.std_out or b"").decode().strip())

    remote_tgz = REMOTE + r"\_deploy_slim.tgz"
    _upload_bytes(session, remote_tgz, archive)
    print("ARCHIVE_UPLOAD_OK")

    ps = rf"""
$ErrorActionPreference='Continue'
$root='{REMOTE}'
Set-Location $root
py -c "import tarfile; tarfile.open(r'{remote_tgz}').extractall(r'$root')"
Remove-Item '{remote_tgz}' -Force -ErrorAction SilentlyContinue
Write-Output 'EXTRACT_OK'
& "$root\deploy\windows\VPS_APPLY_FIX.ps1" -Root $root -Branch cursor/win-remote-deploy-fix-2e26
& "$root\deploy\windows\START_DISCORD_BRIDGE.ps1" -Root $root
try {{
  $h=Invoke-RestMethod http://127.0.0.1:8790/api/health -TimeoutSec 30
  Write-Output ('HEALTH '+$h.ok)
}} catch {{ Write-Output ('HEALTH_FAIL '+$_.Exception.Message) }}
try {{
  $d=Invoke-RestMethod http://127.0.0.1:8790/api/discord -TimeoutSec 30
  Write-Output ('DISCORD configured='+$d.configured)
}} catch {{ Write-Output ('DISCORD_FAIL '+$_.Exception.Message) }}
try {{
  $s=Invoke-RestMethod http://127.0.0.1:8790/api/status -TimeoutSec 30
  Write-Output ('STATUS bot_running='+$s.status.bot_running+' balance='+$s.status.balance+' exchange_ok='+$s.status.exchange_ok)
}} catch {{ Write-Output ('STATUS_FAIL '+$_.Exception.Message) }}
"""
    r = session.run_ps(ps)
    secrets = [v for v in load_local_env_for_deploy().values() if v]
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    print(_redact(out, secrets)[-10000:])
    if err.strip():
        print(_redact(err, secrets)[-2000:])
    return 0 if r.status_code == 0 else int(r.status_code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
