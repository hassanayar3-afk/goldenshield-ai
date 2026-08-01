"""تشغيل مستقر لبوت واحد من C:\\GoldenShield_Binance بدون Redirect (لا يُقتل عند إغلاق SSH)."""

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

Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GOLDENSHIELD_BINANCE' -or
    $_.CommandLine -match '00_START\.bat'
  )
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue

$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
# استخدم cmd start حتى ينفصل عن جلسة SSH تماماً
$cmd = "cd /d `"$good`" && set PYTHONPATH=$good&& set PYTHONIOENCODING=utf-8&& `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$cmd -WorkingDirectory $good -WindowStyle Hidden
Start-Sleep -Seconds 22

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach ($p in $procs) {
  Write-Host ('PID=' + $p.ProcessId + ' NAME=' + $p.Name)
  Write-Host $p.CommandLine
}
$bad = @($procs | Where-Object { $_.CommandLine -match 'Downloads|Telegram Desktop' })
Write-Host ('BAD=' + $bad.Count)
if ($procs.Count -eq 1 -and $bad.Count -eq 0) { Write-Host 'STABLE_OK' } else { Write-Host 'STABLE_CHECK' }
Get-Content (Join-Path $good 'storage\logs\bot_stdout.log') -Tail 25 -EA SilentlyContinue
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
    remote = r"C:\Users\Public\gs_stable_start.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-1000:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
