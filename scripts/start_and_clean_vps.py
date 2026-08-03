"""تشغيل البوت الرسمي وتنظيف مخلفات غير متعلقة على VPS (بدون قتل العامل الرسمي)."""

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

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Write-Host '=== START_AND_CLEAN_V2 ==='

Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

# اقتل فقط المسارات الأجنبية الواضحة (لا تلمس python -u main.py العام)
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'main\.py' -and (
    $_.CommandLine -match 'Downloads' -or
    $_.CommandLine -match 'Telegram Desktop' -or
    $_.CommandLine -match 'C:\\GoldenShield\\' -or
    $_.CommandLine -match 'C:\\GoldenShield"' -or
    $_.CommandLine -match 'C:\\GS_Bot' -or
    $_.CommandLine -match 'GOLDENSHIELD_BINANCE_DEMO'
  )
} | ForEach-Object {
  Write-Host ("KILL_FOREIGN " + $_.ProcessId)
  Write-Host $_.CommandLine
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}

$mains = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
if ($mains.Count -eq 0) {
  Write-Host 'STARTING_OFFICIAL'
  schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
  Start-Sleep -Seconds 18
} elseif ($mains.Count -gt 1) {
  Write-Host 'TOO_MANY_MAINS — keep oldest, kill extras'
  $sorted = $mains | Sort-Object ProcessId
  foreach ($extra in $sorted | Select-Object -Skip 1) {
    Write-Host ("KILL_EXTRA " + $extra.ProcessId)
    Stop-Process -Id $extra.ProcessId -Force -EA SilentlyContinue
  }
} else {
  Write-Host ('ALREADY_RUNNING pid=' + $mains[0].ProcessId)
}

# تنظيف مجلدات/ملفات غير متعلقة — لا نلمس الرسمي
$junkDirs = @(
  'C:\Users\Administrator\Downloads\Telegram Desktop\GOLDENSHIELD_BINANCE_DEMO',
  'C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227',
  'C:\Users\Administrator\Downloads\Telegram Desktop\GOLDENSHIELD_START_FIX',
  'C:\GoldenShield',
  'C:\GoldenShield_AI',
  'C:\GS_Bot',
  'C:\bot',
  'C:\Users\Administrator\Desktop\GOLDENSHIELD_BINANCE_DEMO',
  'C:\Users\Administrator\Desktop\GoldenShield_CONTABO_DEMO'
)

Write-Host '--- CLEAN ---'
foreach ($p in $junkDirs) {
  if (-not (Test-Path $p)) { continue }
  if ($p -eq $good) { continue }
  try {
    Get-CimInstance Win32_Process | Where-Object {
      $_.CommandLine -and ($_.CommandLine -like ("*" + $p.Replace('\','\\') + "*"))
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 1
    Remove-Item -LiteralPath $p -Recurse -Force -EA Stop
    Write-Host ("REMOVED " + $p)
  } catch {
    Write-Host ("FAIL_REMOVE " + $p + " :: " + $_.Exception.Message)
  }
}

$td = 'C:\Users\Administrator\Downloads\Telegram Desktop'
if (Test-Path $td) {
  Get-ChildItem $td -Directory -EA SilentlyContinue | Where-Object {
    $_.Name -match 'GOLDENSHIELD|GoldenShield|goldenshield'
  } | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Recurse -Force -EA Stop
      Write-Host ("REMOVED_TD " + $_.FullName)
    } catch {
      Write-Host ("FAIL_TD " + $_.FullName)
    }
  }
}

foreach ($pat in @(
  'C:\Users\Administrator\Downloads\*GOLDENSHIELD*.zip',
  'C:\Users\Administrator\Downloads\*GoldenShield*.zip',
  'C:\Users\Administrator\Desktop\*GOLDENSHIELD*.zip',
  'C:\Users\Administrator\Desktop\*GoldenShield*.zip'
)) {
  Get-Item $pat -EA SilentlyContinue | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Force -EA Stop
      Write-Host ("REMOVED_ZIP " + $_.FullName)
    } catch {
      Write-Host ("FAIL_ZIP " + $_.FullName)
    }
  }
}

# تأكد التشغيل مرة أخيرة
Start-Sleep -Seconds 8
$mains = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
if ($mains.Count -eq 0) {
  Write-Host 'FALLBACK_START'
  Start-Process -FilePath (Join-Path $good 'run_official_bot.bat') -WorkingDirectory $good -WindowStyle Hidden
  Start-Sleep -Seconds 15
  $mains = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
  })
}

Write-Host ('MAIN_COUNT=' + $mains.Count)
foreach ($p in $mains) {
  Write-Host ('PID=' + $p.ProcessId)
  Write-Host $p.CommandLine
}

# تحقق أن cwd تقريباً الرسمي عبر ملفات مفتوحة صعبة — نعتمد على وجود السجل حديثاً
$log = Join-Path $good 'storage\logs\bot_stdout.log'
if (Test-Path $log) {
  $age = (Get-Date) - (Get-Item $log).LastWriteTime
  Write-Host ('LOG_AGE_SEC=' + [int]$age.TotalSeconds)
  Write-Host 'LOG_TAIL:'
  Get-Content $log -Tail 5 -EA SilentlyContinue
}

$still = @()
foreach ($p in $junkDirs) { if (Test-Path $p) { $still += $p } }
if ($still.Count -gt 0) {
  Write-Host 'STILL_EXISTS:'
  $still | ForEach-Object { Write-Host $_ }
} else {
  Write-Host 'JUNK_CLEARED'
}

if ($mains.Count -eq 1 -and (Test-Path $good) -and $still.Count -eq 0) {
  Write-Host 'RUN_AND_CLEAN_OK'
} elseif ($mains.Count -ge 1 -and (Test-Path $good)) {
  Write-Host 'RUN_OK_CLEAN_PARTIAL'
} else {
  Write-Host 'RUN_AND_CLEAN_CHECK'
}
"""


def main() -> int:
    if not HOST or not USER:
        print("WIN_HOST/WIN_USER missing")
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
        remote = r"C:\ProgramData\GoldenShield\start_and_clean_v2.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, stdout, stderr = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
            timeout=360,
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        text = (out + err).strip()
        print(text.encode("ascii", errors="replace").decode("ascii"))
        if "RUN_AND_CLEAN_OK" in text or "RUN_OK_CLEAN_PARTIAL" in text:
            return 0
        return 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
