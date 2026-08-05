"""Force-start visible bot package on VPS (SSH-safe)."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
Set-Location $bot
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
$rt=Join-Path $bot 'storage\runtime'
New-Item -ItemType Directory -Force -Path $rt,(Join-Path $bot 'storage\logs') | Out-Null
Remove-Item (Join-Path $rt 'user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $rt 'bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null

# Visible core window
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k','call run_bot_visible.cmd' -WorkingDirectory $bot -WindowStyle Normal
Start-Sleep -Seconds 6
# Visible pulse board
Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $bot 'live_console.ps1') -WorkingDirectory $bot -WindowStyle Normal
Start-Sleep -Seconds 8

$procs=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach($p in $procs){ Write-Host ('PID='+$p.ProcessId+' CMD='+$p.CommandLine) }
$helpers=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'run_bot_visible|live_console' })
Write-Host ('VISIBLE_HELPERS=' + $helpers.Count)
if(Test-Path (Join-Path $rt 'signals_board.txt')){ Write-Host 'BOARD=True' } else { Write-Host 'BOARD=waiting' }
Write-Host 'FORCE_START_OK'
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_force_visible_start.ps1"
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
        print("STDERR:", err[-1200:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
