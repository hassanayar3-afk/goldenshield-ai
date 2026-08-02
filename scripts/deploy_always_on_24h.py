"""ضبط تشغيل 24/7 على VPS: مهمة رسمية + مراقب + كونسول حي + منع السكون."""

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
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"

UPLOADS = [
    "operations/report_archive.py",
    "operations/trial_journal.py",
    "operations/error_logger.py",
    "database/repositories/operations_repo.py",
    "main.py",
    "00_LIVE_CONSOLE.bat",
    "00_START.bat",
]

PS = rf"""
$ErrorActionPreference='Continue'
$good='{KEEP}'
$py='{PY}'
$bad='C:\Users\Administrator\Downloads\Telegram Desktop\GOLDENSHIELD_BINANCE_DEMO'

Write-Host '=== ALWAYS_ON_24H ==='

powercfg -change -standby-timeout-ac 0 | Out-Null
powercfg -change -hibernate-timeout-ac 0 | Out-Null
powercfg -change -monitor-timeout-ac 0 | Out-Null
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0 | Out-Null
powercfg /SETACTIVE SCHEME_CURRENT | Out-Null
Write-Host 'SLEEP_DISABLED'

Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match '00_START\.bat' -or
    $_.CommandLine -match 'run_official_bot\.bat' -or
    $_.CommandLine -match '00_LIVE_CONSOLE'
  )
}} | ForEach-Object {{
  Write-Host ("KILL " + $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}}
Start-Sleep -Seconds 3

if (Test-Path $bad) {{
  $src = Join-Path $bad '00_START.bat'
  $blocker = "@echo off`r`necho Do NOT run from Downloads. Use C:\GoldenShield_Binance only.`r`npause`r`nexit /b 1`r`n"
  if (Test-Path $src) {{ Copy-Item $src (Join-Path $bad '00_START.bat.DISABLED') -Force -EA SilentlyContinue }}
  [System.IO.File]::WriteAllText($src, $blocker)
  Write-Host 'DOWNLOADS_BLOCKED'
}}

foreach ($tn in @('GoldenShieldBot','GoldenShieldBotBoot','GoldenShieldBotVisible','GoldenShieldLiveConsole','GoldenShieldWatchdog')) {{
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Delete /TN $tn /F 2>$null | Out-Null
}}

$envp = Join-Path $good '.env'
$map = @{{
  'GOLDENSHIELD_OFFICIAL_ROOT'='C:\GoldenShield_Binance'
  'GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT'='true'
  'GOLDENSHIELD_LOCK_FAIL_CLOSED'='true'
  'TELEGRAM_SIGNALS_ONLY'='true'
  'TELEGRAM_SEND_CYCLE_SIGNALS'='false'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'LOOP_INTERVAL_SECONDS'='15'
  'REPORT_FILE_ARCHIVE_ENABLED'='true'
  'BOT_ACTIVITY_ARCHIVE_ENABLED'='true'
  'ACTIVITY_JOURNAL_ALWAYS'='true'
  'DIRECTIONAL_COMPONENT_SCORING'='true'
}}
if (Test-Path $envp) {{
  $lines = Get-Content $envp -ErrorAction SilentlyContinue
  $keys=@{{}}
  $out = foreach ($line in $lines) {{
    if ($line -match '^\s*#' -or $line -notmatch '=') {{ $line; continue }}
    $k=($line -split '=',2)[0].Trim()
    if ($map.ContainsKey($k)) {{ "$k=$($map[$k])"; $keys[$k]=1 }} else {{ $line }}
  }}
  foreach ($k in $map.Keys) {{ if (-not $keys.ContainsKey($k)) {{ $out += "$k=$($map[$k])" }} }}
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_PATCHED'
}}

New-Item -ItemType Directory -Force -Path (Join-Path $good 'storage\logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $good 'storage\reports') | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\ProgramData\GoldenShield' | Out-Null
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

$launcher = Join-Path $good 'run_official_bot.bat'
$bat = @"
@echo off
cd /d C:\GoldenShield_Binance
title GoldenShield WORKER 24/7
set PYTHONPATH=C:\GoldenShield_Binance
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance
set GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true
set GOLDENSHIELD_LOCK_FAIL_CLOSED=true
if not exist storage\logs mkdir storage\logs
echo [%DATE% %TIME%] WORKER_START>> storage\logs\bot_stdout.log
:loop
"$py" -u main.py >> storage\logs\bot_stdout.log 2>&1
echo [%DATE% %TIME%] WORKER_EXIT code=%ERRORLEVEL% — restart in 5s>> storage\logs\bot_stdout.log
timeout /t 5 /nobreak >nul
goto loop
"@
$bat = $bat -replace "`r`n","`n" -replace "`n","`r`n"
[System.IO.File]::WriteAllText($launcher, $bat)
Write-Host 'WORKER_BAT_OK'

$wd = Join-Path $good 'scripts\watchdog_official_bot.ps1'
New-Item -ItemType Directory -Force -Path (Join-Path $good 'scripts') | Out-Null
$wdBody = @'
$ErrorActionPreference="SilentlyContinue"
$good="C:\GoldenShield_Binance"
$log=Join-Path $good "storage\logs\watchdog.log"
function WLog($m){{ Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "s"), $m) }}
New-Item -ItemType Directory -Force -Path (Join-Path $good "storage\logs") | Out-Null
if (Test-Path (Join-Path $good "storage\runtime\user_stopped.flag")) {{
  WLog "SKIP user_stopped"
  exit 0
}}
$mains = @(Get-CimInstance Win32_Process | Where-Object {{
  $_.Name -eq "python.exe" -and $_.CommandLine -and $_.CommandLine -match "main\.py" -and $_.CommandLine -match "GoldenShield_Binance"
}})
if ($mains.Count -ge 1) {{
  WLog ("OK running pid=" + $mains[0].ProcessId)
  exit 0
}}
WLog "RESTART GoldenShieldBotOfficial"
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep -Seconds 8
$mains2 = @(Get-CimInstance Win32_Process | Where-Object {{
  $_.Name -eq "python.exe" -and $_.CommandLine -and $_.CommandLine -match "main\.py"
}})
WLog ("AFTER restart count=" + $mains2.Count)
'@
[System.IO.File]::WriteAllText($wd, $wdBody)
Write-Host 'WATCHDOG_PS1_OK'

schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $launcher /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Write-Host 'TASK_OFFICIAL_OK'

$trWd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$wd`""
schtasks /Create /TN GoldenShieldWatchdog /TR $trWd /SC MINUTE /MO 5 /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldWatchdog | Out-Null
Write-Host 'TASK_WATCHDOG_OK'

$live = Join-Path $good '00_LIVE_CONSOLE.bat'
schtasks /Create /TN GoldenShieldLiveConsole /TR "`"$live`"" /SC ONLOGON /RL HIGHEST /F | Out-Null
Write-Host 'TASK_LIVE_CONSOLE_OK'

Start-Sleep -Seconds 20
$all = @(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -and $_.CommandLine -match 'main\.py' }})
$pyMains = @($all | Where-Object {{ $_.Name -eq 'python.exe' }})
$badOnes = @($all | Where-Object {{ $_.CommandLine -match 'Downloads|Telegram Desktop' }})
Write-Host ('PYTHON_MAIN=' + $pyMains.Count)
Write-Host ('BAD_DOWNLOADS=' + $badOnes.Count)
foreach ($p in $pyMains) {{ Write-Host ('PID=' + $p.ProcessId); Write-Host $p.CommandLine }}

$logFile = Join-Path $good 'storage\logs\bot_stdout.log'
if (Test-Path $logFile) {{
  Write-Host 'LOG_TAIL:'
  Get-Content $logFile -Tail 10 -ErrorAction SilentlyContinue
}} else {{
  Write-Host 'LOG_MISSING'
}}

if ($pyMains.Count -ge 1 -and $badOnes.Count -eq 0) {{ Write-Host 'ALWAYS_ON_OK' }} else {{ Write-Host 'ALWAYS_ON_CHECK' }}
"""


def main() -> int:
    if not HOST or not USER:
        print("WIN_HOST / WIN_USER missing in .env")
        return 2

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    try:

        def run(cmd: str, timeout: int = 300) -> str:
            _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            return (out + err).strip()

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            if not local.is_file():
                print(f"SKIP missing {rel}")
                continue
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            remote_dir = str(Path(remote).parent).replace("/", "\\")
            run(
                "powershell -NoProfile -Command "
                f"\"New-Item -ItemType Directory -Force -Path '{remote_dir}' | Out-Null\""
            )
            sftp.put(str(local), remote)
            print(f"UPLOADED {rel}")

        remote_ps1 = r"C:\ProgramData\GoldenShield\always_on_24h.ps1"
        run(
            'powershell -NoProfile -Command '
            '"New-Item -ItemType Directory -Force -Path C:\\ProgramData\\GoldenShield | Out-Null"'
        )
        with sftp.file(remote_ps1, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()

        out = run(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps1}"',
            timeout=240,
        )
        safe = out.encode("ascii", errors="replace").decode("ascii")
        print(safe)
        return 0 if "ALWAYS_ON_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
