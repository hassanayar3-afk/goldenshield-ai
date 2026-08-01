"""رفع إصلاح قوة الدخول ثم إعادة تشغيل البوت الرسمي فقط."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "operations/dashboard_templates.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_keyboards.py",
    "execution/binance_position_sync.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}
Start-Sleep -Seconds 2
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$tr = "cmd.exe /c cd /d $good && set PYTHONPATH=$good&& set PYTHONIOENCODING=utf-8&& `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep -Seconds 18
$n = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ("PYTHON_MAIN=" + $n)
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
    sftp = client.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        remote = r"C:\GoldenShield_Binance\\" + rel.replace("/", "\\")
        sftp.put(str(local), remote)
        print("UP", rel)
    sftp.close()

    remote = r"C:\Users\Public\gs_strength_restart.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-800:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
