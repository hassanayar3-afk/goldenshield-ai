"""Tail bot log and count main.py on VPS."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

PS = r"""
$bot='C:\GoldenShield_Binance'
$procs=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS='+$procs.Count)
foreach($p in $procs){ Write-Host ('PID='+$p.ProcessId) }
$helpers=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'run_bot_visible|live_console') })
Write-Host ('HELPERS='+$helpers.Count)
Write-Host '--- LOG TAIL ---'
$log=Join-Path $bot 'storage\logs\bot_stdout.log'
if(Test-Path $log){ Get-Content $log -Tail 40 -EA SilentlyContinue }
Write-Host '--- STOP FLAG ---'
Write-Host ('STOP='+(Test-Path (Join-Path $bot 'storage\runtime\user_stopped.flag')))
Write-Host ('BOARD='+(Test-Path (Join-Path $bot 'storage\runtime\signals_board.txt')))
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(os.environ["WIN_HOST"], username=os.environ["WIN_USER"], password=os.environ["WIN_PASSWORD"], timeout=40, allow_agent=False, look_for_keys=False)
    remote = r"C:\Users\Public\gs_tail_bot.ps1"
    sftp = c.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(PS)
    sftp.close()
    _, o, e = c.exec_command(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=60)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR", err[-800:])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
