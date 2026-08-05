"""اختبر START_BOT على السيرفر وتحقق من العمليات الناتجة."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$root='C:\GoldenShield_Binance'
cmd /c "$root\START_BOT.bat"
Start-Sleep -Seconds 10
Write-Output '=== PROCESS CHECK ==='
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.CommandLine -and ($_.CommandLine -match 'main\.py|BOT_WINDOW\.ps1|00_LIVE_CONSOLE')
  } |
  ForEach-Object {
    Write-Output ('PROC ' + $_.Name + ' PID=' + $_.ProcessId + ' CMD=' + $_.CommandLine)
  }
"""


def main() -> int:
    host = os.getenv("WIN_HOST", "").strip()
    user = os.getenv("WIN_USER", "").strip()
    password = os.getenv("WIN_PASSWORD", "")
    if not host or not user:
        print("Missing WIN_HOST/WIN_USER", file=sys.stderr)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45)

    sftp = client.open_sftp()
    remote = r"C:\GoldenShield_Binance\storage\runtime\_test_start_visible.ps1"
    with sftp.open(remote, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=180,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
