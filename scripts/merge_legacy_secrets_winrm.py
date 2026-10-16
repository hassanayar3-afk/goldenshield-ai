#!/usr/bin/env python3
"""Upload legacy secret files + run Harvest-GsSecrets on VPS (no secret logging)."""

from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r"C:\GoldenShield_Binance"

FILL_KEYS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_API_KEY_2",
    "BINANCE_API_SECRET_2",
    "BINANCE_DEMO_TRADING",
    "BINANCE_HTTPS_PROXY",
    "DISCORD_WEBHOOK_URL",
    "DISCORD_BOT_TOKEN",
    "DISCORD_CHANNEL_ID",
    "DISCORD_NOTIFY_ENABLED",
    "CLOUDFLARE_TUNNEL_TOKEN",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_GLOBAL_API_KEY",
    "CLOUDFLARE_EMAIL",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_ZONE_ID",
    "MOBILE_PUBLIC_BASE_URL",
    "MOBILE_PAIR_CODE",
    "MOBILE_API_TOKEN",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "WIN_HOST",
    "WIN_USER",
    "WIN_PASSWORD",
    "EXECUTION_MODE",
    "EXECUTION_BACKEND",
    "GS_BAN_QUICK_TUNNEL",
    "CLOUDFLARE_TUNNEL_ENABLED",
)


def _session() -> winrm.Session:
    load_dotenv(ROOT / ".env", override=True)
    load_dotenv(ROOT / "goldenshield.env", override=False)
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


def _parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        t = line.strip()
        if not t or t.startswith("#") or "=" not in t:
            continue
        k, v = t.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            out[k.strip()] = v
    return out


def _upload_bytes(session: winrm.Session, remote_path: str, data: bytes) -> None:
    b64 = base64.b64encode(data).decode("ascii")
    chunk = 6000
    remote_b64 = remote_path + ".b64part"
    session.run_ps(f"Remove-Item '{remote_b64}' -Force -EA SilentlyContinue")
    for i in range(0, len(b64), chunk):
        part = b64[i : i + chunk]
        session.run_ps(f"Add-Content -Path '{remote_b64}' -Value '{part}' -Encoding ASCII")
    fin = f"""
$path = '{remote_path}'
$b64 = Get-Content -Path ($path + '.b64part') -Raw -Encoding ASCII
[IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($b64))
Remove-Item ($path + '.b64part') -Force -EA SilentlyContinue
Write-Output ('WROTE ' + $path)
"""
    r = session.run_ps(fin)
    if r.status_code != 0:
        err = (r.std_err or b"").decode("utf-8", errors="replace")
        raise RuntimeError(err[-400:])


def _redact(text: str, secrets: list[str]) -> str:
    out = text
    for s in secrets:
        if len(s) >= 8:
            out = out.replace(s, "***")
    return out


def main() -> int:
    session = _session()
    merged: dict[str, str] = {}
    for rel in (".env", "goldenshield.env", "config/USER_SECRETS.env"):
        p = ROOT / rel
        if p.is_file():
            merged.update(_parse_env(p.read_text(encoding="utf-8", errors="replace")))

    gs = REMOTE + r"\goldenshield.env"
    harvest = REMOTE + r"\deploy_ops\Harvest-GsSecrets.ps1"
    _upload_bytes(session, gs, (ROOT / "goldenshield.env").read_bytes())
    _upload_bytes(
        session,
        harvest,
        (ROOT / "deploy_ops" / "Harvest-GsSecrets.ps1").read_bytes(),
    )

    secrets = [v for v in merged.values() if v]
    ps = rf"""
$ErrorActionPreference='Continue'
& '{harvest}' -Root '{REMOTE}'
Write-Output 'HARVEST_RAN'
"""
    r = session.run_ps(ps)
    print(_redact((r.std_out or b"").decode("utf-8", errors="replace"), secrets)[-4000:])

    # Fill only keys still blank on VPS from local legacy files
    probe = rf"""
function KeyBlank($path,$key){{
  if(-not(Test-Path $path)){{return 'missing'}}
  foreach($line in Get-Content $path){{
    if($line -match ('^\s*'+[regex]::Escape($key)+'\s*=')){{
      $v=($line -split '=',2)[1].Trim().Trim('"')
      if([string]::IsNullOrWhiteSpace($v)){{return 'blank'}} else {{return 'set'}}
    }}
  }}
  return 'missing'
}}
$p='{REMOTE}\.env'
"""
    for k in FILL_KEYS:
        probe += f"Write-Output ('CHK {k}='+(KeyBlank $p '{k}'))\n"

    chk_out = (session.run_ps(probe).std_out or b"").decode("utf-8", errors="replace")
    need = []
    for line in chk_out.splitlines():
        if line.startswith("CHK ") and (line.endswith("=blank") or line.endswith("=missing")):
            key = line.split("=", 1)[0].replace("CHK ", "").strip()
            if key in merged:
                need.append(key)

    if need:
        patch_lines = []
        for k in need:
            v = merged[k]
            patch_lines.append(f"{k}={v}")
        patch_text = "\n".join(patch_lines) + "\n"
        patch_remote = REMOTE + r"\storage\runtime\legacy_secret_patch.env"
        _upload_bytes(session, patch_remote, patch_text.encode("utf-8"))
        apply = rf"""
$p='{REMOTE}\.env'
$patch='{patch_remote}'
foreach($line in Get-Content $patch){{
  if($line -notmatch '='){{continue}}
  $k,$v=$line.Split('=',2)
  $k=$k.Trim(); $v=$v.Trim()
  if($p -match ('(?m)^'+[regex]::Escape($k)+'=.*$')){{
    $cur=(Get-Content $p | Where-Object {{ $_ -match ('^\s*'+[regex]::Escape($k)+'\s*=') }} | Select-Object -First 1)
    $cv=($cur -split '=',2)[1].Trim()
    if([string]::IsNullOrWhiteSpace($cv)){{
      (Get-Content $p -Raw) -replace ('(?m)^'+[regex]::Escape($k)+'=.*$'), ($k+'='+$v) | Set-Content $p -Encoding UTF8
    }}
  }} else {{
    Add-Content $p -Value ($k+'='+$v) -Encoding UTF8
  }}
}}
Remove-Item $patch -Force -EA SilentlyContinue
Write-Output ('PATCHED_KEYS={len(need)}')
"""
        r2 = session.run_ps(apply)
        print(_redact((r2.std_out or b"").decode("utf-8", errors="replace"), secrets))

    report = rf"""
function HasKey($path,$key){{
  if(-not(Test-Path $path)){{return 'no'}}
  foreach($line in Get-Content $path){{
    if($line -match ('^\s*'+[regex]::Escape($key)+'\s*=')){{
      $v=($line -split '=',2)[1].Trim()
      if([string]::IsNullOrWhiteSpace($v)){{return 'empty'}} else {{return 'yes'}}
    }}
  }}
  return 'no'
}}
$p='{REMOTE}\.env'
"""
    for k in FILL_KEYS:
        report += f"Write-Output ('{k}='+(HasKey $p '{k}'))\n"
    report += """
try {
  $d=Invoke-RestMethod http://127.0.0.1:8790/api/discord -TimeoutSec 20
  Write-Output ('DISCORD mode='+$d.mode+' configured='+$d.configured)
} catch { Write-Output 'DISCORD probe skipped' }
"""
    print((session.run_ps(report).std_out or b"").decode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
