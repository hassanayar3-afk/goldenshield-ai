"""Confirm MT5 remnants are gone on VPS roots."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$roots=@('C:\GoldenShield_Binance','C:\Users\Administrator\Downloads\GoldenShield')
foreach($bot in $roots){
  Write-Host ('ROOT='+$bot)
  Write-Host ('EXISTS='+(Test-Path $bot))
  if(-not (Test-Path $bot)){ continue }
  Write-Host ('BRIDGE='+(Test-Path (Join-Path $bot 'execution\mt5_bridge.py')))
  Write-Host ('MAP='+(Test-Path (Join-Path $bot 'config\mt5_symbol_map.yaml')))
  Write-Host ('FOREX_DATA='+(Test-Path (Join-Path $bot 'data\forex_market_data.py')))
  $envp=Join-Path $bot '.env'
  if(Test-Path $envp){
    $hits=@(Get-Content $envp | Where-Object { $_ -match '^(MT5_|BOT_AUTO_SYNC_MT5)=' })
    Write-Host ('ENV_MT5_KEYS='+$hits.Count)
    Get-Content $envp | Where-Object { $_ -match '^(EXECUTION_BACKEND|BINANCE_DEMO_TRADING)=' } | ForEach-Object { Write-Host ('ENV '+$_) }
  }
}
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_check_mt5_gone.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-800:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
