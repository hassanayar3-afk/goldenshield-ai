"""Deploy SSoT open-positions unification (main + مراكزي)."""

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

VERIFY_PY = r'''
import sys, inspect
sys.path.insert(0, r"C:\GoldenShield_Binance")
from execution.binance_position_sync import get_live_open_positions_ssot, discover_live_spot_holdings
from operations.telegram_dashboard import TelegramDashboard
assert hasattr(TelegramDashboard, "_live_open_ssot")
src_main = inspect.getsource(TelegramDashboard.render_main)
src_pos = inspect.getsource(TelegramDashboard.render_positions)
assert "_live_open_ssot" in src_main and "_live_open_ssot" in src_pos
assert "position_manager.all()" not in src_pos
h = discover_live_spot_holdings()
print("HOLDINGS", len(h))
print("SSOT_IMPORT_OK")
'''

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
& $py 'C:\ProgramData\GoldenShield\_verify_ssot.py'
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
if($n -ge 1){ Write-Host 'SSOT_UNIFY_OK' } else { Write-Host 'SSOT_UNIFY_CHECK' }
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
        for rel in (
            "execution/binance_position_sync.py",
            "operations/telegram_dashboard.py",
        ):
            sftp.put(str(ROOT / rel), f"{KEEP}/{rel}")
            print("UPLOADED", rel)
        with sftp.file(r"C:\ProgramData\GoldenShield\_verify_ssot.py", "w") as fh:
            fh.write(VERIFY_PY)
        remote_ps = r"C:\ProgramData\GoldenShield\_deploy_ssot.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
            timeout=180,
        )
        out = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "SSOT_UNIFY_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
