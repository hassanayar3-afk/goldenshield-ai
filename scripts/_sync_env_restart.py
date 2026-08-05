"""Sync enterprise env keys + ensure single main.py on VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

MAP = {
    "BOT_FORCE_ACTIVE": "true",
    "HYBRID_SIGNAL_MODE": "true",
    "TELEGRAM_LIVE_SIGNALS": "true",
    "TELEGRAM_LIVE_SIGNALS_SECONDS": "15",
    "TELEGRAM_LIVE_POSITIONS_SECONDS": "1",
    "PROJECT_REFERENCE_CAPITAL": "5000",
    "PROJECT_MIN_TRADE_NOTIONAL": "25",
    "PROJECT_MIN_EXCHANGE_NOTIONAL": "5",
    "AUTO_ENTRY_MIN_PERCENT": "90",
    "TELEGRAM_SIGNAL_MIN_PERCENT": "70",
    "MANUAL_ENTRY_REQUIRED": "false",
    "ENTERPRISE_PIPELINE_ENABLED": "true",
    "SSOT_SYNC_ENABLED": "true",
    "POST_MORTEM_ENGINE_ACTIVE": "true",
    "CIRCUIT_BREAKER_MAX_LOSSES": "3",
}


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST", "").strip(),
        username=os.getenv("WIN_USER", "").strip(),
        password=os.getenv("WIN_PASSWORD", ""),
        timeout=45,
    )
    sftp = client.open_sftp()
    env_path = r"C:\GoldenShield_Binance\.env"
    with sftp.open(env_path, "r") as f:
        raw = f.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    keys_seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in MAP:
            out.append(f"{k}={MAP[k]}")
            keys_seen.add(k)
        else:
            out.append(line)
    for k, v in MAP.items():
        if k not in keys_seen:
            out.append(f"{k}={v}")
    payload = ("\n".join(out) + "\n").encode("utf-8")
    with sftp.open(env_path, "w") as f:
        f.write(payload)
    sftp.close()
    print("ENV_RULES_SYNCED")

    # kill all main then run official task once
    ps = r"""
$ErrorActionPreference='Continue'
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'main\.py'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep -Seconds 3
# clear locks only
$rt='C:\GoldenShield_Binance\storage\runtime'
Remove-Item (Join-Path $rt 'user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $rt 'bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.tmp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.temp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
schtasks /End /TN 'GoldenShieldBotOfficial' /F 2>$null
Start-Sleep -Seconds 2
schtasks /Run /TN 'GoldenShieldBotOfficial'
Start-Sleep -Seconds 12
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
# if >1 keep oldest
if($mains.Count -gt 1){
  $keep=($mains | Sort-Object ProcessId | Select-Object -First 1)
  foreach($p in $mains){ if($p.ProcessId -ne $keep.ProcessId){ Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue } }
  Start-Sleep -Seconds 2
  $mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
    $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
  })
}
Write-Output ('MAIN=' + $mains.Count)
"""
    # write ps to remote and run
    sftp = client.open_sftp()
    ps_path = r"C:\GoldenShield_Binance\storage\runtime\_env_restart.ps1"
    with sftp.open(ps_path, "w") as f:
        f.write(ps.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        r'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\GoldenShield_Binance\storage\runtime\_env_restart.ps1"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err[-1500:], file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
