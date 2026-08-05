"""نظّم ملفات GoldenShield المبعثرة داخل مجلد واحد في Downloads."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$downloads = 'C:\Users\Administrator\Downloads'
$desktop = 'C:\Users\Administrator\Desktop'
$target = Join-Path $downloads 'GoldenShield'
New-Item -ItemType Directory -Path $target -Force | Out-Null

Write-Output '=== ORGANIZE DOWNLOADS ==='
Get-ChildItem $downloads -Force -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.PSIsContainer -and $_.Name -eq 'GoldenShield') { return }
  $name = $_.Name
  if (
    $name -match '(?i)goldenshield' -or
    $name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW|00_LIVE_CONSOLE|run_official_bot)\.(bat|ps1|zip)$'
  ) {
    $dest = Join-Path $target $name
    Move-Item $_.FullName $dest -Force -ErrorAction SilentlyContinue
    Write-Output ('MOVED_DOWNLOAD ' + $name)
  }
}

Write-Output '=== ORGANIZE DESKTOP ==='
Get-ChildItem $desktop -Force -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.PSIsContainer -and $_.Name -eq 'GoldenShield') { return }
  $name = $_.Name
  if ($name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW)\.bat$') {
    $dest = Join-Path $target $name
    Move-Item $_.FullName $dest -Force -ErrorAction SilentlyContinue
    Write-Output ('MOVED_DESKTOP ' + $name)
  }
}

Write-Output '=== FINAL TARGET CONTENTS ==='
Get-ChildItem $target -Force -ErrorAction SilentlyContinue |
  Sort-Object Name |
  ForEach-Object { Write-Output ('TARGET_ITEM ' + $_.Name) }

Write-Output '=== ACTIVE PROJECT ==='
if (Test-Path 'C:\GoldenShield_Binance') {
  Write-Output 'ACTIVE_PROJECT_OK C:\GoldenShield_Binance'
} else {
  Write-Output 'ACTIVE_PROJECT_MISSING C:\GoldenShield_Binance'
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
    remote = r"C:\GoldenShield_Binance\storage\runtime\_organize_gs_files.ps1"
    with sftp.open(remote, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
