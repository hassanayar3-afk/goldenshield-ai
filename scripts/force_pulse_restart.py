"""إعادة تشغيل قسرية بعد نشر وضع النبض."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
Write-Output '=== FORCE RESTART PULSE ==='
schtasks /End /TN 'GoldenShieldBotOfficial' /F 2>$null
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py|run_official_bot')
} | ForEach-Object {
  Write-Output ('KILL PID=' + $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}
Start-Sleep -Seconds 3
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
$worker=Join-Path $g 'run_official_bot.ps1'
schtasks /Run /TN 'GoldenShieldBotOfficial' | Out-Null
Start-Sleep -Seconds 12
$m=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' })
Write-Output ('MAIN=' + $m.Count)
$log=Join-Path $g 'storage\logs\bot_stdout.log'
if(Test-Path $log){
  $tail=Get-Content $log -Tail 40 -Encoding UTF8 -EA SilentlyContinue
  $tail | ForEach-Object { Write-Output $_ }
}
"""


def main() -> int:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)
    sftp = client.open_sftp()
    path = r"C:\GoldenShield_Binance\storage\runtime\_force_pulse_restart.ps1"
    with sftp.open(path, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{path}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-800:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
