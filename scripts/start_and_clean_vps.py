"""تشغيل البوت الرسمي وتنظيف مخلفات غير متعلقة على VPS."""

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

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Write-Host '=== START_AND_CLEAN ==='

# 1) تأكد أن العامل يعمل
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue

$mains = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -and
  $_.CommandLine -match 'main\.py' -and $_.CommandLine -match 'GoldenShield_Binance'
})
if ($mains.Count -eq 0) {
  Write-Host 'STARTING_OFFICIAL'
  schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
  Start-Sleep -Seconds 15
} else {
  Write-Host ('ALREADY_RUNNING pid=' + $mains[0].ProcessId)
}

# اقتل أي main من Downloads أو مسارات قديمة
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'main\.py' -and (
    $_.CommandLine -match 'Downloads|Telegram Desktop|C:\\GoldenShield[^_]' -or
    ($_.CommandLine -notmatch 'GoldenShield_Binance')
  )
} | ForEach-Object {
  Write-Host ("KILL_FOREIGN " + $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}

# 2) تنظيف مخلفات غير متعلقة (لا نلمس C:\GoldenShield_Binance)
$junk = @(
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

# زيبات قديمة في Downloads/Desktop
$zipPatterns = @(
  'C:\Users\Administrator\Downloads\*GOLDENSHIELD*.zip',
  'C:\Users\Administrator\Downloads\*GoldenShield*.zip',
  'C:\Users\Administrator\Downloads\*goldenshield*.zip',
  'C:\Users\Administrator\Desktop\*GOLDENSHIELD*.zip',
  'C:\Users\Administrator\Desktop\*GoldenShield*.zip'
)

Write-Host '--- CLEAN_SCAN ---'
foreach ($p in $junk) {
  if (Test-Path $p) {
    Write-Host ("FOUND " + $p)
  }
}

# حذف المجلدات القديمة
foreach ($p in $junk) {
  if (-not (Test-Path $p)) { continue }
  if ($p -eq $good) { Write-Host 'SKIP_OFFICIAL'; continue }
  try {
    # إن وُجدت عمليات من هذا المسار اقتلها أولاً
    Get-CimInstance Win32_Process | Where-Object {
      $_.CommandLine -and ($_.CommandLine -like ("*" + $p + "*"))
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 1
    Remove-Item -LiteralPath $p -Recurse -Force -EA Stop
    Write-Host ("REMOVED " + $p)
  } catch {
    Write-Host ("FAIL_REMOVE " + $p + " :: " + $_.Exception.Message)
    # محاولة تعطيل 00_START إن فشل الحذف الكامل
    $bat = Join-Path $p '00_START.bat'
    if (Test-Path $bat) {
      $blocker = "@echo off`r`necho OBSOLETE folder. Use C:\GoldenShield_Binance only.`r`nexit /b 1`r`n"
      [System.IO.File]::WriteAllText($bat, $blocker)
      Write-Host ("BLOCKED_START " + $bat)
    }
  }
}

foreach ($pat in $zipPatterns) {
  Get-Item $pat -EA SilentlyContinue | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Force -EA Stop
      Write-Host ("REMOVED_ZIP " + $_.FullName)
    } catch {
      Write-Host ("FAIL_ZIP " + $_.FullName)
    }
  }
}

# ملفات مؤقتة لنشر قديم
$tmpJunk = @(
  'C:\ProgramData\GoldenShield\always_on_24h.ps1.bak',
  'C:\Users\Administrator\Downloads\Telegram Desktop\*.bat'
)
# لا نحذف كل bat في Telegram Desktop عشوائياً — فقط إن بقي مجلد demo
$td = 'C:\Users\Administrator\Downloads\Telegram Desktop'
if (Test-Path $td) {
  Get-ChildItem $td -Directory -EA SilentlyContinue | Where-Object {
    $_.Name -match 'GOLDENSHIELD|GoldenShield|goldenshield'
  } | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Recurse -Force -EA Stop
      Write-Host ("REMOVED_TD " + $_.FullName)
    } catch {
      Write-Host ("FAIL_TD " + $_.FullName + " :: " + $_.Exception.Message)
    }
  }
}

# 3) تحقق نهائي
Start-Sleep -Seconds 5
$mains = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
$goodMains = @($mains | Where-Object { $_.CommandLine -match 'GoldenShield_Binance' })
$badMains = @($mains | Where-Object { $_.CommandLine -notmatch 'GoldenShield_Binance' })
Write-Host ('GOOD_MAIN=' + $goodMains.Count)
Write-Host ('BAD_MAIN=' + $badMains.Count)
foreach ($p in $goodMains) {
  Write-Host ('PID=' + $p.ProcessId)
  Write-Host $p.CommandLine
}
foreach ($p in $badMains) {
  Write-Host ('BAD_PID=' + $p.ProcessId)
  Write-Host $p.CommandLine
}

Write-Host '--- REMAINING_JUNK_CHECK ---'
foreach ($p in $junk) {
  if (Test-Path $p) { Write-Host ("STILL_EXISTS " + $p) }
}
if (Test-Path $good) { Write-Host 'OFFICIAL_OK C:\GoldenShield_Binance' }

$log = Join-Path $good 'storage\logs\bot_stdout.log'
if (Test-Path $log) {
  Write-Host 'LOG_TAIL:'
  Get-Content $log -Tail 6 -EA SilentlyContinue
}

if ($goodMains.Count -eq 1 -and $badMains.Count -eq 0) {
  Write-Host 'RUN_AND_CLEAN_OK'
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
        remote = r"C:\ProgramData\GoldenShield\start_and_clean.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, stdout, stderr = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
            timeout=300,
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        text = (out + err).strip()
        print(text.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "RUN_AND_CLEAN_OK" in text else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
