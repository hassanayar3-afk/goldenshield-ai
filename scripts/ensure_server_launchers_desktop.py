"""تأكد من وجود ملفات التشغيل على السيرفر وفي سطح المكتب."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

SERVER_ROOT = r"C:\GoldenShield_Binance"
SERVER_RUNTIME = SERVER_ROOT + r"\storage\runtime"

UPLOADS = [
    "START_BOT.bat",
    "REST_BOT.bat",
    "STOP_BOT.bat",
    "BOT_WINDOW.bat",
    "BOT_WINDOW.ps1",
    "00_LIVE_CONSOLE.bat",
    "run_official_bot.ps1",
    "run_official_bot.bat",
]

VERIFY_AND_DESKTOP_PS = r"""
$ErrorActionPreference = 'Continue'
$root = 'C:\GoldenShield_Binance'
$desktopCandidates = @(
  'C:\Users\Administrator\Desktop',
  'C:\Users\Public\Desktop'
)
$needed = @(
  'START_BOT.bat',
  'REST_BOT.bat',
  'STOP_BOT.bat',
  'BOT_WINDOW.bat',
  '00_LIVE_CONSOLE.bat',
  'run_official_bot.bat'
)
$desktopOnly = @(
  'START_BOT.bat',
  'REST_BOT.bat',
  'STOP_BOT.bat',
  'BOT_WINDOW.bat'
)

Write-Output '=== SERVER LAUNCHERS CHECK ==='
foreach ($name in $needed) {
  $p = Join-Path $root $name
  if (Test-Path $p) {
    Write-Output ('FOUND_ROOT ' + $name)
  } else {
    Write-Output ('MISSING_ROOT ' + $name)
  }
}

foreach ($desk in $desktopCandidates) {
  if (-not (Test-Path $desk)) { continue }
  Write-Output ('DESKTOP ' + $desk)
  foreach ($name in $desktopOnly) {
    $src = Join-Path $root $name
    $dst = Join-Path $desk $name
    if (Test-Path $src) {
      Copy-Item $src $dst -Force -ErrorAction SilentlyContinue
      if (Test-Path $dst) {
        Write-Output ('DESKTOP_OK ' + $name + ' -> ' + $desk)
      } else {
        Write-Output ('DESKTOP_FAIL ' + $name + ' -> ' + $desk)
      }
    }
  }
  foreach ($name in @('00_LIVE_CONSOLE.bat', 'run_official_bot.bat', 'run_official_bot.ps1')) {
    $dst = Join-Path $desk $name
    if (Test-Path $dst) {
      Remove-Item $dst -Force -ErrorAction SilentlyContinue
      Write-Output ('DESKTOP_REMOVE ' + $name + ' -> ' + $desk)
    }
  }
}

Write-Output '=== SERVER ROOT LIST ==='
Get-ChildItem $root -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW|00_LIVE_CONSOLE|run_official_bot)\.(bat|ps1)$' } |
  Sort-Object Name |
  ForEach-Object { Write-Output ('ROOT_FILE ' + $_.Name) }

foreach ($desk in $desktopCandidates) {
  if (-not (Test-Path $desk)) { continue }
  Write-Output ('=== DESKTOP LIST ' + $desk + ' ===')
  Get-ChildItem $desk -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^(START_BOT|REST_BOT|STOP_BOT|BOT_WINDOW|00_LIVE_CONSOLE|run_official_bot)\.(bat|ps1)$' } |
    Sort-Object Name |
    ForEach-Object { Write-Output ('DESKTOP_FILE ' + $_.Name) }
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
    for rel in UPLOADS:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = f"{SERVER_ROOT}\\{rel.replace('/', chr(92))}"
        sftp.put(str(local), remote)
        print("UPLOADED", rel)
    with sftp.open(f"{SERVER_RUNTIME}\\_ensure_launchers_desktop.ps1", "w") as f:
        f.write(VERIFY_AND_DESKTOP_PS.encode("utf-8"))
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{SERVER_RUNTIME}\_ensure_launchers_desktop.ps1"',
        timeout=120,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err[-1200:])

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
