"""Deploy close-fix (cancel open orders + fit amount) and restart bot."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
UPLOADS = [
    "execution/trade_executor.py",
    "operations/telegram_dashboard.py",
]
PS = r"""
$g='C:\GoldenShield_Binance'
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 3
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 10
$m=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN=' + $m.Count)
Write-Host 'CLOSE_FIX_DEPLOYED'
"""

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = ssh.open_sftp()
    for rel in UPLOADS:
        sftp.put(str(ROOT / rel), KEEP + "\\" + rel.replace("/", "\\"))
        print("UP", rel)
    remote = r"C:\ProgramData\GoldenShield\_deploy_close_fix.ps1"
    with sftp.file(remote, "w") as fh:
        fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()
    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=90
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    ssh.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
