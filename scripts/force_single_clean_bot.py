"""يفرض بوتاً واحداً نظيفاً من C:\\GoldenShield_Binance فقط."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "operations/single_instance.py",
    "main.py",
    "00_START.bat",
]

# Avoid Arabic/quotes inside PowerShell here-strings — keep PS ASCII-only.
PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
$bad='C:\Users\Administrator\Downloads\Telegram Desktop\GOLDENSHIELD_BINANCE_DEMO'

Write-Host '=== KILL ALL BOTS ==='
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GOLDENSHIELD_BINANCE' -or
    ($_.CommandLine -match '00_START\.bat')
  )
} | ForEach-Object {
  Write-Host ("KILL " + $_.ProcessId + " " + $_.Name)
  Write-Host $_.CommandLine
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

if (Test-Path $bad) {
  $src = Join-Path $bad '00_START.bat'
  $bak = Join-Path $bad '00_START.bat.DISABLED'
  $blocker = @(
    '@echo off',
    'echo Do NOT run from Telegram Downloads.',
    'echo Use only C:\GoldenShield_Binance\00_START.bat',
    'pause',
    'exit /b 1'
  ) -join "`r`n"
  if (Test-Path $src) { Copy-Item $src $bak -Force -ErrorAction SilentlyContinue }
  [System.IO.File]::WriteAllText($src, $blocker)
  Write-Host 'DOWNLOADS_START_DISABLED'
}

foreach ($tn in @('GoldenShieldBot','GoldenShieldBotBoot','GoldenShieldBotVisible')) {
  schtasks /End /TN $tn /F 2>$null | Out-Null
  schtasks /Change /TN $tn /DISABLE 2>$null | Out-Null
}

$envp = Join-Path $good '.env'
$map = @{
  'GOLDENSHIELD_OFFICIAL_ROOT'='C:\GoldenShield_Binance'
  'GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT'='true'
  'GOLDENSHIELD_LOCK_FAIL_CLOSED'='true'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='5'
}
if (Test-Path $envp) {
  $lines = Get-Content $envp
  $keys = @{}
  $out = foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { $line; continue }
    $k = ($line -split '=',2)[0].Trim()
    if ($map.ContainsKey($k)) { "$k=$($map[$k])"; $keys[$k]=1 } else { $line }
  }
  foreach ($k in $map.Keys) { if (-not $keys.ContainsKey($k)) { $out += "$k=$($map[$k])" } }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envp, $out, $utf8)
  Write-Host 'ENV_PATCHED'
}

Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path 'C:\ProgramData\GoldenShield' | Out-Null
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path (Join-Path $good 'storage\logs') | Out-Null

# Ensure START.bat is CRLF ASCII-safe on official path
$startBat = Join-Path $good '00_START.bat'
if (Test-Path $startBat) {
  $raw = [System.IO.File]::ReadAllText($startBat)
  $raw = $raw -replace "`r`n","`n" -replace "`n","`r`n"
  [System.IO.File]::WriteAllText($startBat, $raw)
  Write-Host 'START_BAT_CRLF'
}

$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$tr = "cmd.exe /c cd /d $good && set PYTHONPATH=$good&& set PYTHONIOENCODING=utf-8&& set GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT=true&& set GOLDENSHIELD_OFFICIAL_ROOT=C:\GoldenShield_Binance&& `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep -Seconds 22

Write-Host '=== VERIFY ==='
$all = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
$pyMains = @($all | Where-Object { $_.Name -eq 'python.exe' })
$badOnes = @($all | Where-Object { $_.CommandLine -match 'Downloads|Telegram Desktop' })
Write-Host ('ALL_MAIN_CMDLINE=' + $all.Count)
Write-Host ('PYTHON_MAIN=' + $pyMains.Count)
Write-Host ('BAD_DOWNLOADS=' + $badOnes.Count)
foreach ($p in $all) {
  Write-Host ('PID=' + $p.ProcessId + ' NAME=' + $p.Name)
  Write-Host $p.CommandLine
}
if ($pyMains.Count -eq 1 -and $badOnes.Count -eq 0) { Write-Host 'SINGLE_CLEAN_OK' } else { Write-Host 'SINGLE_CLEAN_FAIL' }

Set-Location $good
$env:PYTHONPATH = $good
$env:GOLDENSHIELD_ENFORCE_OFFICIAL_ROOT = 'true'
$env:GOLDENSHIELD_OFFICIAL_ROOT = 'C:\GoldenShield_Binance'
& $py scripts\notify_single_bot.py
"""

NOTIFY_PY = r'''
from operations.telegram_bot import TelegramBot
from operations.telegram_keyboards import main_menu_keyboard

text = (
    "🛡 <b>بوت واحد فقط</b>\n"
    "تم إيقاف كل النسخ المكررة.\n"
    "التشغيل الرسمي: <code>C:\\GoldenShield_Binance</code>\n"
    "لا تشغّل مجلد Downloads أبداً."
)
mid = TelegramBot().send_message(text, reply_markup=main_menu_keyboard(paused=False))
print("NOTICE", mid)
'''


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
    sftp = client.open_sftp()
    for rel in FILES:
        sftp.put(str(ROOT / rel), r"C:\GoldenShield_Binance\\" + rel.replace("/", "\\"))
        print("UP", rel)
    # helper notify script on VPS
    remote_notify = r"C:\GoldenShield_Binance\scripts\notify_single_bot.py"
    try:
        sftp.stat(r"C:\GoldenShield_Binance\scripts")
    except OSError:
        try:
            sftp.mkdir(r"C:\GoldenShield_Binance\scripts")
        except OSError:
            pass
    with sftp.file(remote_notify, "w") as fh:
        fh.write(NOTIFY_PY)
    print("UP scripts/notify_single_bot.py")

    remote = r"C:\Users\Public\gs_force_single.ps1"
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    path = ROOT / "storage" / "logs" / "force_single_out.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out + "\n" + err, encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-1200:])
    print("SAVED", path)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
