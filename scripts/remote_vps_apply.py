#!/usr/bin/env python3
"""Apply Discord + VPS_APPLY_FIX on Windows VPS via SSH (no secrets logged)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._win_ssh import WindowsSSHError, connect_windows_ssh, load_local_env_for_deploy

REMOTE = r"C:\GoldenShield_Binance"
BRANCH = "cursor/win-remote-deploy-fix-2e26"


def _run(ssh, cmd: str, timeout: int = 600) -> int:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    if out.strip():
        safe = out.replace(load_local_env_for_deploy().get("DISCORD_WEBHOOK_URL", ""), "[REDACTED]")
        print(safe[-5000:])
    return stdout.channel.recv_exit_status()


def main() -> int:
    local = load_local_env_for_deploy()
    webhook = (local.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not webhook:
        print("DISCORD_WEBHOOK_URL missing in .env / secrets", file=sys.stderr)
        return 2
    try:
        ssh = connect_windows_ssh(timeout=60)
    except WindowsSSHError as exc:
        print(exc, file=sys.stderr)
        return 3

    # Pass webhook via base64 to avoid shell escaping / logging
    b64 = base64.b64encode(webhook.encode("utf-8")).decode("ascii")
    ps = rf"""
$ErrorActionPreference='Continue'
$root='{REMOTE}'
$wh=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}'))
Set-Location $root
if (Test-Path .git) {{
  git fetch origin {BRANCH}
  git checkout {BRANCH}
  git pull origin {BRANCH}
}}
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\deploy\windows\Set-GsDiscordEnv.ps1" -WebhookUrl $wh -Root $root
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\deploy\windows\VPS_APPLY_FIX.ps1" -Root $root -Branch {BRANCH}
try {{
  $h=Invoke-RestMethod http://127.0.0.1:8790/api/health -TimeoutSec 20
  Write-Output ('HEALTH '+($h.ok))
}} catch {{ Write-Output ('HEALTH_FAIL '+$_.Exception.Message) }}
"""
    code = _run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps.replace(chr(10), "; ")}"', timeout=900)
    ssh.close()
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
