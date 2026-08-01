"""شخّص من يطلق نسخ main.py المتعددة على VPS."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
Write-Host '=== PROCESSES ==='
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GoldenShield' -or
    $_.CommandLine -match 'watchdog'
  )
} | ForEach-Object {
  Write-Host ('PID=' + $_.ProcessId + ' PPID=' + $_.ParentProcessId + ' NAME=' + $_.Name)
  Write-Host $_.CommandLine
  Write-Host '---'
}
Write-Host '=== SCHEDULED ==='
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
  $_.TaskName -match 'Golden|Shield|Bot|GS_'
} | ForEach-Object { Write-Host ($_.TaskName + ' ' + $_.State) }
Write-Host '=== WMI CMD ==='
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'cmd|powershell|wscript|cscript' -and $_.CommandLine -match 'Golden|START|main' } | ForEach-Object {
  Write-Host ('PID=' + $_.ProcessId + ' ' + $_.CommandLine)
}
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
    remote = r"C:\Users\Public\gs_find_spawners.ps1"
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
