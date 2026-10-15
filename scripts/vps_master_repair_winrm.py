#!/usr/bin/env python3
"""Upload repair artifacts + run purge, binance test, PM2 stack on Windows VPS."""

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
    "deploy_ops/test_binance_auth.py",
    "deploy/windows/VPS_MASTER_PURGE.ps1",
    "deploy_ops/run_pm2_clean_stack.ps1",
    "deploy_ops/pm2.ecosystem.config.cjs",
    "gateway_api/fast_router.py",
    "core_engine/neural_matrix.py",
    "terminal_app/routes/api_live.py",
    "terminal_app/services/binance_mirror.py",
    "data_highway/zero_copy_cache.py",
    "deploy/windows/START_CLOUDFLARE_TUNNEL.ps1",
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
        return
    remote = REMOTE + "\\" + rel.replace("/", "\\")
    parent = str(Path(remote).parent)
    session.run_ps(f"New-Item -ItemType Directory -Force -Path '{parent}' | Out-Null")
    b64 = base64.b64encode(local.read_bytes()).decode("ascii")
    rb = remote + ".b64part"
    session.run_ps(f"Remove-Item '{rb}' -Force -EA SilentlyContinue")
    for i in range(0, len(b64), 5000):
        session.run_ps(f"Add-Content -Path '{rb}' -Value '{b64[i:i+5000]}' -Encoding ASCII")
    session.run_ps(
        f"[IO.File]::WriteAllBytes('{remote}', [Convert]::FromBase64String((Get-Content '{rb}' -Raw -Encoding ASCII))); "
        f"Remove-Item '{rb}' -Force"
    )


def _mask_env_audit(session: winrm.Session) -> str:
    ps = rf"""
function KeyState($k){{
  foreach($line in Get-Content '{REMOTE}\.env'){{
    if($line -match ('^\s*'+[regex]::Escape($k)+'\s*=')){{
      $v=($line -split '=',2)[1].Trim()
      if([string]::IsNullOrWhiteSpace($v)){{return 'EMPTY'}} else {{return 'SET len='+$v.Length}}
    }}
  }}
  return 'MISSING'
}}
@('BINANCE_API_KEY','BINANCE_API_SECRET','BINANCE_DEMO_TRADING','DISCORD_WEBHOOK_URL','WIN_HOST','WIN_USER','WIN_PASSWORD','CLOUDFLARE_TUNNEL_TOKEN','MOBILE_PAIR_CODE','MOBILE_PUBLIC_BASE_URL') | ForEach-Object {{
  Write-Output ("ENV $_="+(KeyState $_))
}}
"""
    return (session.run_ps(ps).std_out or b"").decode("utf-8", errors="replace")


def main() -> int:
    session = _session()
    for rel in UPLOADS:
        _upload(session, rel)
    print("UPLOAD_OK")
    print(_mask_env_audit(session))
    run = rf"""
$ErrorActionPreference='Continue'
& '{REMOTE}\deploy\windows\VPS_MASTER_PURGE.ps1' -Root '{REMOTE}'
$py = & '{REMOTE}\deploy\windows\Resolve-GsPython.ps1' -Root '{REMOTE}'
Write-Output '---BINANCE_TEST---'
& $py '{REMOTE}\deploy_ops\test_binance_auth.py'
Write-Output '---PM2---'
& '{REMOTE}\deploy_ops\run_pm2_clean_stack.ps1' -Root '{REMOTE}'
Write-Output '---LATENCY---'
& $py -c "import time,urllib.request; t0=time.perf_counter(); urllib.request.urlopen('http://127.0.0.1:8790/api/health',timeout=10); print('health_ms',round((time.perf_counter()-t0)*1000,2))"
& '{REMOTE}\deploy\windows\REGISTER_GS_DAEMON_TASK.ps1' -Root '{REMOTE}' -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName GoldenShieldDaemon -ErrorAction SilentlyContinue
& '{REMOTE}\deploy\windows\START_CLOUDFLARE_TUNNEL.ps1' -Root '{REMOTE}'
Start-Sleep 5
$pair=''; Get-Content '{REMOTE}\.env' | ForEach-Object {{ if($_ -match '^\s*MOBILE_PAIR_CODE\s*='){{ $script:pair=$_.Split('=',2)[1].Trim().Trim('"').ToUpper() }} }}
try {{
  $pr=Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8790/api/pair -ContentType 'application/json' -Body (@{{pair_code=$pair;device_name='Repair'}}|ConvertTo-Json) -TimeoutSec 20
  $h=@{{'X-GS-Token'=$pr.device_token}}
  $t0=Get-Date
  1..5 | ForEach-Object {{
    $a=Invoke-RestMethod http://127.0.0.1:8790/api/status -Headers $h -TimeoutSec 20
    Start-Sleep -Milliseconds 50
  }}
  $ms=((Get-Date)-$t0).TotalMilliseconds/5
  Write-Output ('AVG_STATUS_POLL_MS='+[math]::Round($ms,2))
  Write-Output ('LIVE balance='+$a.status.balance+' exchange_ok='+$a.status.exchange_ok)
}} catch {{ Write-Output ('PAIR_STATUS_ERR '+$_.Exception.Message) }}
"""
    out = (session.run_ps(run).std_out or b"").decode("utf-8", errors="replace")
    # redact nothing specific - test script already masks
    print(out[-12000:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
