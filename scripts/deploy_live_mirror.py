"""Deploy Live Mirror Mode for Telegram dashboard."""

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
    "execution/binance_position_sync.py",
    "operations/telegram_dashboard.py",
]

VERIFY_PY = r'''
import sys
sys.path.insert(0, r"C:\GoldenShield_Binance")
from execution.binance_position_sync import live_mirror_sync_from_binance
from operations.telegram_dashboard import TelegramDashboard
assert callable(live_mirror_sync_from_binance)
assert hasattr(TelegramDashboard, "_mirror_live_spot_state")
print("MIRROR_IMPORT_OK")
'''

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe' 'C:\ProgramData\GoldenShield\_verify_live_mirror.py'
if($LASTEXITCODE -ne 0){ Write-Host 'VERIFY_FAIL'; exit 1 }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 2
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 12
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ('MAIN=' + $n)
if($n -ge 1){ Write-Host 'LIVE_MIRROR_OK' } else { Write-Host 'LIVE_MIRROR_CHECK' }
"""


def main() -> int:
    if not HOST or not USER or not PASSWORD:
        print("Set WIN_HOST / WIN_USER / WIN_PASSWORD")
        return 1
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            sftp.put(str(local), remote.replace("\\", "/"))
            print("UPLOADED", rel)
        with sftp.file(r"C:\ProgramData\GoldenShield\_verify_live_mirror.py", "w") as fh:
            fh.write(VERIFY_PY)
        remote_ps = r"C:\ProgramData\GoldenShield\_deploy_live_mirror.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
            timeout=180,
        )
        out = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "LIVE_MIRROR_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
