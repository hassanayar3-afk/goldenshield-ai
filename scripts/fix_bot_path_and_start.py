"""أوقف بوت Downloads الخاطئ + المهام المجدولة، وشغّل C:\\GoldenShield_Binance فقط."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$good = 'C:\GoldenShield_Binance'

Write-Host '=== KILL ALL main.py / related CMD ==='
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match 'main\.py' -or
    $_.CommandLine -match 'GOLDENSHIELD_BINANCE' -or
    $_.CommandLine -match 'GoldenShield_Binance' -or
    $_.CommandLine -match '00_START\.bat'
  )
} | ForEach-Object {
  Write-Host ("KILL PID=" + $_.ProcessId + " NAME=" + $_.Name)
  Write-Host $_.CommandLine
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# عطّل المهام المجدولة القديمة حتى لا تعيد تشغيل مسار خاطئ
foreach ($tn in @('GoldenShieldBot','GoldenShieldBotBoot','GoldenShieldBotVisible')) {
  try {
    schtasks /End /TN $tn /F 2>$null | Out-Null
    schtasks /Change /TN $tn /DISABLE 2>$null | Out-Null
    Write-Host ("TASK_DISABLED " + $tn)
  } catch {
    Write-Host ("TASK_SKIP " + $tn)
  }
}

# أعد إنشاء مهمة واحدة صحيحة تشير للمسار الجيد فقط
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) {
  $py = (Get-Command py -ErrorAction SilentlyContinue).Source
}
$tr = "cmd.exe /c cd /d $good && `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
Write-Host 'TASK_OFFICIAL_CREATED'

# نظّف أعلام الإيقاف والقفل
New-Item -ItemType Directory -Force -Path (Join-Path $good 'storage\runtime') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $good 'storage\logs') | Out-Null
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -ErrorAction SilentlyContinue

# شغّل البوت الرسمي فقط
Set-Location $good
$env:PYTHONPATH = $good
$env:PYTHONIOENCODING = 'utf-8'
Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory $good -WindowStyle Hidden
Start-Sleep -Seconds 20

Write-Host '=== AFTER ==='
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("BOT_PROCS=" + $procs.Count)
foreach ($p in $procs) {
  Write-Host ("PID=" + $p.ProcessId + " PPID=" + $p.ParentProcessId + " NAME=" + $p.Name)
  Write-Host $p.CommandLine
}
$goodOnes = @($procs | Where-Object { $_.CommandLine -match 'GoldenShield_Binance' -or $_.ExecutablePath -match 'Python313' })
$badOnes = @($procs | Where-Object { $_.CommandLine -match 'Downloads|Telegram Desktop' })
Write-Host ("BAD_DOWNLOADS=" + $badOnes.Count)
if ($procs.Count -ge 1 -and $badOnes.Count -eq 0) {
  Write-Host 'PATH_OK'
} else {
  Write-Host 'PATH_FAIL'
}
"""


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
    remote = r"C:\Users\Public\gs_fix_path_bot.ps1"
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
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
