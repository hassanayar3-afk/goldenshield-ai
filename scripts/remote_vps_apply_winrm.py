#!/usr/bin/env python3
"""Apply .env + VPS_APPLY_FIX on Windows VPS via WinRM (no secrets logged)."""

from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._win_ssh import load_local_env_for_deploy  # noqa: E402

REMOTE = r"C:\GoldenShield_Binance"
BRANCH = "cursor/win-remote-deploy-fix-2e26"
DEFAULT_ENV_ARTIFACT = Path("/opt/cursor/artifacts/vps-production.env")


def _session() -> winrm.Session:
    load_dotenv(ROOT / ".env", override=True)
    load_dotenv(ROOT / "goldenshield.env", override=True)
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


def _redact(text: str, secrets: list[str]) -> str:
    out = text
    for s in secrets:
        if s and len(s) > 8:
            out = out.replace(s, "[REDACTED]")
    return out


def _upload_bytes(session: winrm.Session, remote: str, raw: bytes) -> None:
    b64 = base64.b64encode(raw).decode("ascii")
    remote_ps = remote.replace("'", "''")
    chunk_size = 600
    chunks = [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)] or [""]
    for idx, chunk in enumerate(chunks):
        chunk_esc = chunk.replace("'", "''")
        if idx == 0:
            ps = f"""
$path = '{remote_ps}'
$dir = Split-Path -Parent $path
if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Force -Path $dir | Out-Null }}
if (Test-Path $path) {{ Remove-Item $path -Force }}
$acc = New-Object System.Text.StringBuilder
[void]$acc.Append('{chunk_esc}')
Set-Content -Path ($path + '.b64part') -Value $acc.ToString() -Encoding ASCII -NoNewline
"""
        else:
            ps = f"""
$acc = Get-Content -Path ('{remote_ps}' + '.b64part') -Raw -Encoding ASCII
$acc += '{chunk_esc}'
Set-Content -Path ('{remote_ps}' + '.b64part') -Value $acc -Encoding ASCII -NoNewline
"""
        r = session.run_ps(ps)
        if r.status_code != 0:
            err = (r.std_err or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"upload chunk failed: {err[-400:]}")

    fin = f"""
$path = '{remote_ps}'
$b64 = Get-Content -Path ($path + '.b64part') -Raw -Encoding ASCII
[IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($b64))
Remove-Item ($path + '.b64part') -Force -EA SilentlyContinue
Write-Output ('WROTE ' + $path)
"""
    r = session.run_ps(fin)
    if r.status_code != 0:
        err = (r.std_err or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"upload finalize failed: {err[-400:]}")


def _production_env_bytes() -> bytes:
    src = os.getenv("GS_VPS_ENV_FILE", "").strip()
    path = Path(src) if src else DEFAULT_ENV_ARTIFACT
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    else:
        tpl = (ROOT / "config" / "env.production.template").read_text(encoding="utf-8")
        text = tpl

    local = load_local_env_for_deploy()
    merge_keys = (
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
        "TELEGRAM_MUTE_ALL",
        "TELEGRAM_OUTBOUND_DISABLED",
        "TELEGRAM_SEND_CYCLE_SIGNALS",
        "TELEGRAM_LIVE_SIGNALS",
        "MOBILE_WEB_DIRECT_ACCESS",
        "BOT_FORCE_ACTIVE",
    )
    for k in merge_keys:
        v = (local.get(k) or os.getenv(k) or "").strip()
        if not v and k in ("TELEGRAM_MUTE_ALL", "TELEGRAM_OUTBOUND_DISABLED"):
            v = "true"
        if not v and k in ("TELEGRAM_SEND_CYCLE_SIGNALS", "TELEGRAM_LIVE_SIGNALS"):
            v = "false"
        if not v:
            continue
        pat = re.compile(rf"^{re.escape(k)}=.*$", re.M)
        if pat.search(text):
            text = pat.sub(f"{k}={v}", text, count=1)
        else:
            text = text.rstrip() + f"\n{k}={v}\n"

    def _root_line(_: re.Match[str]) -> str:
        return f"GOLDENSHIELD_OFFICIAL_ROOT={REMOTE}"

    text = re.sub(
        r"^GOLDENSHIELD_OFFICIAL_ROOT=.*$",
        _root_line,
        text,
        count=1,
        flags=re.M,
    )
    if (local.get("TELEGRAM_MUTE_ALL") or os.getenv("TELEGRAM_MUTE_ALL", "")).strip().lower() == "true":
        for blank in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
            pat = re.compile(rf"^{re.escape(blank)}=.*$", re.M)
            text = pat.sub(f"{blank}=", text, count=1) if pat.search(text) else text
    if "TELEGRAM_MUTE_ALL=" not in text:
        text += "TELEGRAM_MUTE_ALL=true\nTELEGRAM_OUTBOUND_DISABLED=true\n"
    return text.encode("utf-8")


def _install_ssh_pubkey(session: winrm.Session, pub_line: str) -> None:
    pub_esc = pub_line.strip().replace("'", "''")
    ps = f"""
$ErrorActionPreference='Continue'
$pub='{pub_esc}'
& '{REMOTE}\\deploy\\windows\\ENABLE_CLOUD_AGENT_SSH.ps1' -PublicKeyLine $pub -UserName $env:USERNAME
New-NetFirewallRule -DisplayName 'OpenSSH-Server-In-TCP' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue | Out-Null
Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service sshd -ErrorAction SilentlyContinue
Write-Output 'SSH_KEY_INSTALLED'
"""
    r = session.run_ps(ps)
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    print(out[-1500:])


def main() -> int:
    local = load_local_env_for_deploy()
    webhook = (local.get("DISCORD_WEBHOOK_URL") or "").strip()
    secrets = [v for v in local.values() if v]

    session = _session()
    probe = session.run_cmd("hostname")
    if probe.status_code != 0:
        print("WINRM probe failed")
        return 1
    print("HOST", (probe.std_out or b"").decode().strip())

    env_remote = REMOTE + r"\.env"
    _upload_bytes(session, env_remote, _production_env_bytes())
    print("ENV_UPLOAD_OK")

    pub_path = Path("/opt/cursor/artifacts/gs_vps_ed25519.pub")
    if pub_path.is_file():
        try:
            _install_ssh_pubkey(session, pub_path.read_text(encoding="utf-8").splitlines()[0])
        except Exception as exc:
            print("SSH_KEY_SKIP", type(exc).__name__)

    wh_b64 = base64.b64encode(webhook.encode("utf-8")).decode("ascii") if webhook else ""
    fix_ps = rf"""
$ErrorActionPreference='Continue'
$root='{REMOTE}'
Set-Location $root
if ('{wh_b64}') {{
  $wh=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{wh_b64}'))
  & "$root\deploy\windows\Set-GsDiscordEnv.ps1" -WebhookUrl $wh -Root $root
}}
& "$root\deploy\windows\VPS_APPLY_FIX.ps1" -Root $root -Branch {BRANCH}
& "$root\deploy\windows\START_DISCORD_BRIDGE.ps1" -Root $root -ErrorAction SilentlyContinue
try {{
  $h=Invoke-RestMethod http://127.0.0.1:8790/api/health -TimeoutSec 25
  Write-Output ('HEALTH '+($h.ok))
}} catch {{ Write-Output ('HEALTH_FAIL '+$_.Exception.Message) }}
try {{
  $d=Invoke-RestMethod http://127.0.0.1:8790/api/discord -TimeoutSec 25
  Write-Output ('DISCORD configured='+$d.configured)
}} catch {{ Write-Output ('DISCORD_FAIL '+$_.Exception.Message) }}
try {{
  $s=Invoke-RestMethod http://127.0.0.1:8790/api/status -TimeoutSec 25
  Write-Output ('STATUS bot_running='+$s.status.bot_running+' balance='+$s.status.balance+' exchange_ok='+$s.status.exchange_ok)
}} catch {{ Write-Output ('STATUS_FAIL '+$_.Exception.Message) }}
"""
    r = session.run_ps(fix_ps)
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    print(_redact(out, secrets)[-8000:])
    if err.strip():
        print(_redact(err, secrets)[-2000:])
    return 0 if r.status_code == 0 else int(r.status_code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
