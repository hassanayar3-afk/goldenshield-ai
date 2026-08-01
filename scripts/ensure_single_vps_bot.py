"""أوقف كل نسخ main.py ثم شغّل بوتاً واحداً فقط."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'

# اقتل كل ما يتعلق بـ GoldenShield / main.py
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GoldenShield_Binance'
  ) -and $_.Name -match 'python|py\.exe'
} | ForEach-Object {
  Write-Host ("KILL " + $_.ProcessId + " " + $_.Name)
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# تأكيد صفر
$left = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("AFTER_KILL=" + $left.Count)
if ($left.Count -gt 0) {
  foreach ($p in $left) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 2
}

$flag = Join-Path $bot 'storage\runtime\user_stopped.flag'
if (Test-Path $flag) { Remove-Item $flag -Force }
$lock = Join-Path $bot 'storage\runtime\bot_instance.lock'
if (Test-Path $lock) { Remove-Item $lock -Force -ErrorAction SilentlyContinue }

# احذف webhook تيليجرام عبر بايثون إن أمكن
Set-Location $bot
$env:PYTHONPATH = $bot
$py = 'py'
try { & $py -V | Out-Null } catch { $py = 'python' }

Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 18

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("BOT_PROCS=" + $procs.Count)
foreach ($p in $procs) { Write-Host ("PID=" + $p.ProcessId) }
if ($procs.Count -eq 1) { Write-Host 'SINGLE_OK' } else { Write-Host 'SINGLE_FAIL' }
"""


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_single_bot.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
