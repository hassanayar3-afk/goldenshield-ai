"""نشر سجل الصفقات الدائم على VPS وإعادة تشغيل البوت الواحد."""

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
    "database/repositories/trade_repo.py",
    "operations/dashboard_templates.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "operations/message_templates.py",
    "execution/trade_executor.py",
]


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd: str, timeout: int = 180) -> str:
            _, o, e = ssh.exec_command(cmd, timeout=timeout)
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            remote_dir = str(Path(remote).parent).replace("/", "\\")
            run(f"powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path '{remote_dir}' | Out-Null\"")
            sftp.put(str(ROOT / rel), remote)
            print("UPLOADED", rel)
        sftp.close()

        ps = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-Sleep 3
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
Remove-Item (Join-Path $good 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 18
$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN=' + $mains.Count)
if ($mains.Count -eq 1) { Write-Host 'HISTORY_DEPLOY_OK' } else { Write-Host 'HISTORY_DEPLOY_CHECK' }
"""
        remote = r"C:\ProgramData\GoldenShield\deploy_history.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(ps.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        out = run(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', 240)
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "HISTORY_DEPLOY_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
