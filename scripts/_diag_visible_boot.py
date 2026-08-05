"""Diagnose main.py exit on VPS + start via interactive scheduled task."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
Set-Location $bot
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bot 'scripts\gs_kill_all.ps1')
Start-Sleep -Seconds 2
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

# Capture short boot
$env:PYTHONPATH=$bot
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUNBUFFERED='1'
$env:GOLDENSHIELD_OFFICIAL_ROOT=$bot
$env:GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT='true'
$env:GOLDENSHIELD_LOCK_FAIL_CLOSED='true'
$env:BOT_FORCE_ACTIVE='true'
$env:NO_SLEEP_MODE='true'
$env:LOOP_INTERVAL_SECONDS='4'
$env:TELEGRAM_LIVE_SIGNALS='true'
$env:EXECUTION_BACKEND='binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$out=Join-Path $bot 'storage\logs\boot_probe.txt'
$err=Join-Path $bot 'storage\logs\boot_probe_err.txt'
Remove-Item $out,$err -Force -EA SilentlyContinue
$p=Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory $bot -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 20
if(-not $p.HasExited){
  Write-Host ('PROBE_RUNNING pid='+$p.Id)
  # keep this one as the live bot — also open visible pulse for RDP user via interactive task
} else {
  Write-Host ('PROBE_EXITED code='+$p.ExitCode)
}
Write-Host '--- OUT ---'
if(Test-Path $out){ Get-Content $out -Tail 50 -EA SilentlyContinue }
Write-Host '--- ERR ---'
if(Test-Path $err){ Get-Content $err -Tail 50 -EA SilentlyContinue }

# Interactive visible windows for logged-on Administrator (RDP)
$action1 = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/k call run_bot_visible.cmd' -WorkingDirectory $bot
$action2 = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$bot\live_console.ps1`"" -WorkingDirectory $bot
$principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Unregister-ScheduledTask -TaskName 'GS_VisibleBot' -Confirm:$false -EA SilentlyContinue
Unregister-ScheduledTask -TaskName 'GS_VisiblePulse' -Confirm:$false -EA SilentlyContinue
Register-ScheduledTask -TaskName 'GS_VisibleBot' -Action $action1 -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName 'GS_VisiblePulse' -Action $action2 -Principal $principal -Settings $settings -Force | Out-Null

# If probe still running, leave it (single instance). Else start interactive visible bot.
$alive=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
if($alive.Count -eq 0){
  Start-ScheduledTask -TaskName 'GS_VisibleBot' -EA SilentlyContinue
  Start-Sleep -Seconds 5
  Start-ScheduledTask -TaskName 'GS_VisiblePulse' -EA SilentlyContinue
  Start-Sleep -Seconds 8
} else {
  Write-Host 'LEFT_PROBE_AS_BOT'
  Start-ScheduledTask -TaskName 'GS_VisiblePulse' -EA SilentlyContinue
}
$procs=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS='+$procs.Count)
foreach($p2 in $procs){ Write-Host ('PID='+$p2.ProcessId) }
Write-Host ('STOP='+(Test-Path (Join-Path $bot 'storage\runtime\user_stopped.flag')))
Write-Host 'DIAG_DONE'
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(os.environ["WIN_HOST"], username=os.environ["WIN_USER"], password=os.environ["WIN_PASSWORD"], timeout=45, allow_agent=False, look_for_keys=False)
    remote = r"C:\Users\Public\gs_diag_visible.ps1"
    sftp = c.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(PS)
    sftp.close()
    _, o, e = c.exec_command(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=180)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
