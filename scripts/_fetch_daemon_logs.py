"""Fetch daemon + stderr + process state."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

PS = r"""
$bot='C:\GoldenShield_Binance'
Write-Host ('BOT_PROCS=' + (@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' })).Count)
Write-Host ('DAEMON=' + (@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'gs_daemon' })).Count)
Write-Host '=== DAEMON LOG ==='
Get-Content (Join-Path $bot 'storage\logs\gs_daemon.log') -Tail 30 -EA SilentlyContinue
Write-Host '=== STDERR ==='
Get-Content (Join-Path $bot 'storage\logs\bot_stderr.log') -Tail 40 -EA SilentlyContinue
Write-Host '=== STDOUT TAIL ==='
Get-Content (Join-Path $bot 'storage\logs\bot_stdout.log') -Tail 30 -EA SilentlyContinue
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(os.environ["WIN_HOST"], username=os.environ["WIN_USER"], password=os.environ["WIN_PASSWORD"], timeout=40, allow_agent=False, look_for_keys=False)
    remote = r"C:\Users\Public\gs_fetch_logs.ps1"
    sftp = c.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(PS)
    sftp.close()
    _, o, e = c.exec_command(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=60)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-500:])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
