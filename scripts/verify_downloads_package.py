"""تحقق من إعدادات الحزمة المثبتة داخل Downloads على السيرفر."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$p='C:\Users\Administrator\Downloads\GoldenShield\.env'
$raw=Get-Content $p -Encoding UTF8 -EA Stop
foreach($k in @(
  'BINANCE_DEMO_TRADING',
  'EXECUTION_MODE',
  'EXECUTION_BACKEND',
  'NO_SLEEP_MODE',
  'LOOP_INTERVAL_SECONDS',
  'TELEGRAM_LIVE_SIGNALS_SECONDS',
  'AUTO_ENTRY_MIN_PERCENT',
  'TELEGRAM_SIGNAL_MIN_PERCENT',
  'ENTERPRISE_PIPELINE_ENABLED'
)){
  $line = $raw | Where-Object { $_ -match ('^' + $k + '=') } | Select-Object -First 1
  if($line){
    Write-Output ('ENV ' + $line)
  } else {
    Write-Output ('ENV_MISSING ' + $k)
  }
}
"""


def main() -> int:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    if not host or not user:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)

    sftp = client.open_sftp()
    remote = r"C:\GoldenShield_Binance\storage\runtime\_verify_downloads_package.ps1"
    with sftp.open(remote, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
