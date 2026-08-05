"""List launch package on VPS."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

PS = r"""
$bot='C:\GoldenShield_Binance'
Write-Host ('ROOT=' + $bot)
Write-Host ('EXISTS=' + (Test-Path $bot))
@(
  'start_bot.bat','restart_bot.bat','stop_bot.bat',
  'GS_START.bat','GS_RESTART.bat','GS_STOP.bat',
  '00_START.bat','00_STOP.bat','REST_BOT.bat',
  'run_bot_visible.cmd','live_console.ps1','gs_daemon.ps1',
  'LAUNCHERS_AR.txt','scripts\gs_common_env.cmd','scripts\gs_kill_all.ps1'
) | ForEach-Object {
  $p = Join-Path $bot $_
  Write-Host (('  {0} = {1}' -f $_, (Test-Path $p)))
}
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_list_pkg.ps1"
    sftp = c.open_sftp()
    with sftp.file(remote, "wb") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()
    _, o, e = c.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=40,
    )
    print(o.read().decode("utf-8", "replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
