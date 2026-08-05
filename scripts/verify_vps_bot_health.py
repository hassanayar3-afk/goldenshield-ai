"""بعد النشر: يتحقق من بوت واحد + مراكز + رصيد + يرسل قائمة تيليجرام (UTF-8 آمن)."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PROBE_LOCAL = ROOT / "scripts" / "_remote_health_probe.py"
REMOTE_PROBE = r"C:\GoldenShield_Binance\scripts\_remote_health_probe.py"
REMOTE_PS = r"C:\Users\Public\gs_verify_health.ps1"

PS = r"""
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("BOT_PROCS=" + $procs.Count)
foreach ($p in $procs) { Write-Host ("PID=" + $p.ProcessId) }

$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) { $py = 'py' }
& $py -X utf8 "C:\GoldenShield_Binance\scripts\_remote_health_probe.py"
"""


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    if not (host and user and password):
        print("missing WIN_*")
        return 1
    if not PROBE_LOCAL.is_file():
        print("missing probe", PROBE_LOCAL)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    try:
        try:
            sftp.stat(r"C:\GoldenShield_Binance\scripts")
        except OSError:
            sftp.mkdir(r"C:\GoldenShield_Binance\scripts")
        # Binary upload keeps UTF-8 Arabic intact
        sftp.put(str(PROBE_LOCAL), REMOTE_PROBE)
        with sftp.file(REMOTE_PS, "wb") as fh:
            fh.write(PS.encode("utf-8"))
    finally:
        sftp.close()

    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{REMOTE_PS}"',
        timeout=180,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
