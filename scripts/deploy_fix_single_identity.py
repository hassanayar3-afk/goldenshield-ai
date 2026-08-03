"""إصلاح هوية البوت الواحد: نفس DB + إعادة تشغيل آمنة + تيليجرام بلا تعارض."""

from __future__ import annotations

import os
import sys
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
    "config/settings.py",
    "operations/telegram_commands.py",
    "operations/single_instance.py",
    "00_START.bat",
    "00_LIVE_CONSOLE.bat",
]

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
Write-Host '=== FIX_SINGLE_IDENTITY ==='

# ENV: مسار DB مطلق + لوحة تحكم كاملة + جذر رسمي
$envp = Join-Path $good '.env'
$map = @{
  'DB_PATH'='C:\GoldenShield_Binance\storage\db\goldenshield.db'
  'GOLDENSHIELD_OFFICIAL_ROOT'='C:\GoldenShield_Binance'
  'GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT'='true'
  'GOLDENSHIELD_LOCK_FAIL_CLOSED'='true'
  'TELEGRAM_SIGNALS_ONLY'='false'
  'TELEGRAM_SEND_CYCLE_SIGNALS'='false'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='5'
}
if (Test-Path $envp) {
  $lines = Get-Content $envp -ErrorAction SilentlyContinue
  $keys=@{}
  $out = foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { $line; continue }
    $k=($line -split '=',2)[0].Trim()
    if ($map.ContainsKey($k)) { "$k=$($map[$k])"; $keys[$k]=1 } else { $line }
  }
  foreach ($k in $map.Keys) { if (-not $keys.ContainsKey($k)) { $out += "$k=$($map[$k])" } }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_PATCHED'
}

# عامل رسمي مع DB مطلق وإعادة تشغيل ذاتية
$launcher = Join-Path $good 'run_official_bot.bat'
$bat = @"
@echo off
cd /d C:\GoldenShield_Binance
title GoldenShield WORKER 24/7 SAME-DB
set PYTHONPATH=C:\GoldenShield_Binance
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance
set GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true
set GOLDENSHIELD_LOCK_FAIL_CLOSED=true
set DB_PATH=C:\GoldenShield_Binance\storage\db\goldenshield.db
if not exist storage\logs mkdir storage\logs
echo [%DATE% %TIME%] WORKER_START db=%DB_PATH%>> storage\logs\bot_stdout.log
:loop
"$py" -u main.py >> storage\logs\bot_stdout.log 2>&1
echo [%DATE% %TIME%] WORKER_EXIT code=%ERRORLEVEL% restart>> storage\logs\bot_stdout.log
timeout /t 5 /nobreak >nul
goto loop
"@
$bat = $bat -replace "`r`n","`n" -replace "`n","`r`n"
[System.IO.File]::WriteAllText($launcher, $bat)
Write-Host 'WORKER_UPDATED'

# أوقف الكل ثم ابدأ واحداً
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'main\.py' -or $_.CommandLine -match '00_START\.bat')
} | ForEach-Object {
  Write-Host ("KILL " + $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-Sleep -Seconds 3
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $launcher /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep -Seconds 22

$mains = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
Write-Host ('MAIN_COUNT=' + $mains.Count)
foreach ($p in $mains) { Write-Host ('PID=' + $p.ProcessId) }

# تحقق DB ومراكز
Set-Location $good
$env:PYTHONPATH=$good
$env:DB_PATH='C:\GoldenShield_Binance\storage\db\goldenshield.db'
& $py -c "from pathlib import Path; from config.settings import load_settings; import sqlite3; s=load_settings(reload=True); p=Path(s.db_path); print('DB', p); con=sqlite3.connect(str(p)); print('open_trades', con.execute(\"SELECT COUNT(*) FROM trades WHERE status='open'\").fetchone()[0])"

$log = Join-Path $good 'storage\logs\bot_stdout.log'
if (Test-Path $log) {
  Write-Host 'LOG_MATCH:'
  Select-String -Path $log -Pattern 'مراكز بعد|CWD=|DB=|Restored|synced|نفس البوت|Single-instance' |
    Select-Object -Last 15 | ForEach-Object { $_.Line }
}

if ($mains.Count -eq 1) { Write-Host 'SINGLE_IDENTITY_OK' } else { Write-Host 'SINGLE_IDENTITY_CHECK' }
"""


def main() -> int:
    if not HOST or not USER:
        print("WIN_HOST/WIN_USER missing")
        return 2
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd: str, timeout: int = 300) -> str:
            _, o, e = ssh.exec_command(cmd, timeout=timeout)
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            remote_dir = str(Path(remote).parent).replace("/", "\\")
            run(f'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path \'{remote_dir}\' | Out-Null"')
            sftp.put(str(local), remote)
            print(f"UPLOADED {rel}")
        remote_ps = r"C:\ProgramData\GoldenShield\fix_single_identity.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        out = run(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"', 300)
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "SINGLE_IDENTITY_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
