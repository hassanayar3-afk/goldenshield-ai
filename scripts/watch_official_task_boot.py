"""شغّل عبر المهمة الرسمية وراقب 60 ثانية مع ذيل السجل."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$good = 'C:\GoldenShield_Binance'

Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}
Start-Sleep -Seconds 2
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue

# حدّث المهمة لتعمل الآن
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$tr = "cmd.exe /c cd /d $good && set PYTHONPATH=$good&& set PYTHONIOENCODING=utf-8&& `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Write-Host 'TASK_RUN_ISSUED'
Start-Sleep -Seconds 25
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'python.exe') -and ($_.CommandLine -match 'main\.py') })
Write-Host ('T25_PYTHON_MAIN=' + $procs.Count)
foreach ($p in $procs) { Write-Host ('PID=' + $p.ProcessId); Write-Host $p.CommandLine }

Start-Sleep -Seconds 40
$procs2 = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'python.exe') -and ($_.CommandLine -match 'main\.py') })
Write-Host ('T65_PYTHON_MAIN=' + $procs2.Count)
foreach ($p in $procs2) { Write-Host ('PID=' + $p.ProcessId); Write-Host $p.CommandLine }

Write-Host '=== LOG TAIL ==='
Get-Content (Join-Path $good 'storage\logs\bot_stdout.log') -Tail 40 -EA SilentlyContinue
Write-Host '=== ERRORS TAIL ==='
Get-Content (Join-Path $good 'storage\logs\errors.log') -Tail 30 -EA SilentlyContinue
Write-Host '=== FLAG ==='
Test-Path (Join-Path $good 'storage\runtime\user_stopped.flag')
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST"),
        username=os.getenv("WIN_USER"),
        password=os.getenv("WIN_PASSWORD"),
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_task_watch.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=150,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
