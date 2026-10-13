#!/usr/bin/env python3
"""Pull branch zipball from GitHub on VPS via WinRM, merge into install dir, restart."""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.remote_vps_apply_winrm import (  # noqa: E402
    BRANCH,
    REMOTE,
    _production_env_bytes,
    _redact,
    _session,
    _upload_bytes,
)
from scripts._win_ssh import load_local_env_for_deploy  # noqa: E402


def _github_token() -> str:
    import subprocess

    url = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True
    ).strip()
    if url.startswith("git@"):
        return ""
    parsed = urlparse(url)
    if parsed.username and parsed.password:
        return unquote(parsed.password)
    return ""


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    load_dotenv(ROOT / "goldenshield.env", override=True)
    token = _github_token()
    if not token:
        print("No GitHub token in origin remote — cannot zipball deploy", file=sys.stderr)
        return 2

    session = _session()
    print("HOST", (session.run_cmd("hostname").std_out or b"").decode().strip())

    env_remote = REMOTE + r"\.env"
    _upload_bytes(session, env_remote, _production_env_bytes())
    print("ENV_UPLOAD_OK")

    tok_b64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
    branch = BRANCH
    ps = rf"""
$ErrorActionPreference='Stop'
$root='{REMOTE}'
$token=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{tok_b64}'))
$zip=Join-Path $env:TEMP ('gs_'+[guid]::NewGuid().ToString()+'.zip')
$hdr=@{{ Authorization=('Bearer '+$token); 'User-Agent'='GoldenShield-CloudAgent' }}
$url='https://api.github.com/repos/hassanayar3-afk/goldenshield-ai/zipball/{branch}'
Invoke-WebRequest -Uri $url -Headers $hdr -OutFile $zip -UseBasicParsing
$dest=Join-Path $env:TEMP ('gs_'+[guid]::NewGuid().ToString())
Expand-Archive -Path $zip -DestinationPath $dest -Force
$inner=Get-ChildItem $dest -Directory | Select-Object -First 1
if (-not $inner) {{ throw 'zip empty' }}
Write-Output ('ZIP_ROOT '+$inner.FullName)
robocopy $inner.FullName $root /E /XD storage .git /XF .env goldenshield.env /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if ($LASTEXITCODE -ge 8) {{ throw ('robocopy failed '+$LASTEXITCODE) }}
Remove-Item $zip -Force -EA SilentlyContinue
Remove-Item $dest -Recurse -Force -EA SilentlyContinue
Write-Output 'SYNC_OK'
& "$root\deploy\windows\Fix-GsRuntimeAcl.ps1" -Root $root
$c=Get-Content (Join-Path $root '.env') -Raw -Encoding UTF8
if ($c -match '(?m)^CLOUDFLARE_TUNNEL_ENABLED=false') {{
  $c=[regex]::Replace($c,'(?m)^CLOUDFLARE_TUNNEL_ENABLED=false','CLOUDFLARE_TUNNEL_ENABLED=true',1)
  Set-Content (Join-Path $root '.env') -Value $c -Encoding UTF8
}}
& "$root\deploy\windows\GS_START_VIA_TASK.ps1" -Root $root
Start-Sleep -Seconds 45
& "$root\deploy\windows\VPS_APPLY_FIX.ps1" -Root $root -Branch {branch} -SkipStackStart
& "$root\deploy\windows\START_DISCORD_BRIDGE.ps1" -Root $root
& "$root\deploy\windows\START_CLOUDFLARE_TUNNEL.ps1" -Root $root
Start-Sleep -Seconds 6
& "$root\deploy\windows\Sync-GsMobileUrls.ps1" -Root $root
Start-ScheduledTask -TaskName GoldenShieldTunnel -ErrorAction SilentlyContinue
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
try {{
  $tu=Get-Content (Join-Path $root 'storage\runtime\mobile_tunnel_url.txt') -Raw -EA SilentlyContinue
  if ($tu) {{ Write-Output ('TUNNEL '+$tu.Trim()) }}
}} catch {{}}
"""
    r = session.run_ps(ps)
    secrets = [v for v in load_local_env_for_deploy().values() if v]
    secrets.append(token)
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    print(_redact(out, secrets)[-12000:])
    if err.strip():
        print(_redact(err, secrets)[-2500:])
    return 0 if r.status_code == 0 else int(r.status_code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
