"""احذف ملفات التشغيل المكررة من سطح المكتب العام وأبق نسخة واحدة."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$pub = 'C:\Users\Public\Desktop'
$admin = 'C:\Users\Administrator\Desktop'
$files = @('START_BOT.bat', 'REST_BOT.bat', 'STOP_BOT.bat', 'BOT_WINDOW.bat')
Write-Output '=== REMOVE DUPLICATE DESKTOP FILES ==='
foreach ($name in $files) {
  $p = Join-Path $pub $name
  if (Test-Path $p) {
    Remove-Item $p -Force -ErrorAction SilentlyContinue
    Write-Output ('REMOVED_PUBLIC ' + $name)
  }
}
Write-Output '=== FINAL ADMIN DESKTOP ==='
Get-ChildItem $admin -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW)\.bat$' } |
  Sort-Object Name |
  ForEach-Object { Write-Output ('ADMIN_FILE ' + $_.Name) }
Write-Output '=== FINAL PUBLIC DESKTOP ==='
Get-ChildItem $pub -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW)\.bat$' } |
  Sort-Object Name |
  ForEach-Object { Write-Output ('PUBLIC_FILE ' + $_.Name) }
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
    remote = r"C:\GoldenShield_Binance\storage\runtime\_remove_desktop_dupes.ps1"
    with sftp.open(remote, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
