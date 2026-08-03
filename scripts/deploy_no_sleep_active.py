"""نشر: ممنوع السكون — الإشارات تستمر دائماً."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"
UPLOADS = [
    "main.py",
    "operations/telegram_dashboard.py",
    "00_START.bat",
]


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd: str, timeout: int = 200) -> str:
            _, o, e = ssh.exec_command(cmd, timeout=timeout)
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            sftp.put(str(ROOT / rel), f"{KEEP}\\{rel.replace('/', '\\')}")
            print("UPLOADED", rel)
        sftp.close()

        ps = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
powercfg -change -monitor-timeout-ac 0 | Out-Null
Write-Host 'SLEEP_OFF'

$envp=Join-Path $good '.env'
$map=@{ 'BOT_FORCE_ACTIVE'='true'; 'TELEGRAM_LIVE_SIGNALS'='true'; 'TELEGRAM_LIVE_SIGNALS_SECONDS'='15' }
$lines=Get-Content $envp -EA SilentlyContinue
$keys=@{}
$out=foreach($line in $lines){
  if($line -match '^\s*#' -or $line -notmatch '='){ $line; continue }
  $k=($line -split '=',2)[0].Trim()
  if($map.ContainsKey($k)){ "$k=$($map[$k])"; $keys[$k]=1 } else { $line }
}
foreach($k in $map.Keys){ if(-not $keys.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
$utf8=New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($envp,$out,$utf8)
Write-Host 'ENV_OK'

$launcher=Join-Path $good 'run_official_bot.bat'
$bat=@"
@echo off
cd /d C:\GoldenShield_Binance
title GoldenShield WORKER 24/7 ACTIVE
set PYTHONPATH=C:\GoldenShield_Binance
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance
set GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true
set GOLDENSHIELD_LOCK_FAIL_CLOSED=true
set DB_PATH=C:\GoldenShield_Binance\storage\db\goldenshield.db
set BOT_FORCE_ACTIVE=true
if not exist storage\logs mkdir storage\logs
if exist storage\runtime\user_stopped.flag del /f /q storage\runtime\user_stopped.flag
echo [%DATE% %TIME%] WORKER_START ACTIVE>> storage\logs\bot_stdout.log
:loop
"$py" -u main.py >> storage\logs\bot_stdout.log 2>&1
echo [%DATE% %TIME%] WORKER_EXIT restart>> storage\logs\bot_stdout.log
timeout /t 5 /nobreak >nul
goto loop
"@
$bat=$bat -replace "`r`n","`n" -replace "`n","`r`n"
[System.IO.File]::WriteAllText($launcher,$bat)
Write-Host 'WORKER_OK'

Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-Sleep 3
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 18
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ("MAIN="+$n)
Select-String -Path (Join-Path $good 'storage\logs\bot_stdout.log') -Pattern 'نشط إجبارياً|FORCE|CWD=|ACTIVE' | Select-Object -Last 8 | ForEach-Object { $_.Line }
if($n -eq 1){ Write-Host 'NO_SLEEP_OK' } else { Write-Host 'NO_SLEEP_CHECK' }
"""
        remote = r"C:\ProgramData\GoldenShield\no_sleep.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(ps.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        out = run(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', 260)
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "NO_SLEEP_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
