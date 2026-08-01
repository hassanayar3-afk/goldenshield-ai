"""تشخيص سريع لبوت Windows عبر SSH — بدون طباعة أسرار."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
Write-Host '=== PATHS ==='
foreach ($p in @('C:\GoldenShield_Binance','C:\GoldenShield')) {
  if (Test-Path $p) {
    Write-Host "FOUND $p"
    Get-ChildItem $p -Name | Select-Object -First 25 | ForEach-Object { Write-Host "  $_" }
  } else {
    Write-Host "MISS $p"
  }
}
Write-Host '=== PROCESSES ==='
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py|GoldenShield_Binance') } |
  ForEach-Object {
    $cl = $_.CommandLine
    if ($cl.Length -gt 140) { $cl = $cl.Substring(0,140) }
    Write-Host ("PID={0} NAME={1} CL={2}" -f $_.ProcessId, $_.Name, $cl)
  }
Write-Host '=== STOP FLAG ==='
foreach ($f in @(
  'C:\GoldenShield_Binance\storage\runtime\user_stopped.flag',
  'C:\GoldenShield\storage\runtime\user_stopped.flag'
)) {
  Write-Host "$f : $(Test-Path $f)"
}
Write-Host '=== ENV FLAGS ==='
$envp = 'C:\GoldenShield_Binance\.env'
if (Test-Path $envp) {
  Get-Content $envp | Where-Object {
    $_ -match '^(EXECUTION_|BINANCE_DEMO|MT5_|TELEGRAM_SIGNALS|LOOP_|AUTO_ENTRY|MANUAL_|SHADOW_|RISK_COMMITTEE|MACRO_|ORDERBOOK_|TELEGRAM_LIVE)'
  } | ForEach-Object { Write-Host $_ }
} else {
  Write-Host 'no .env at Binance path'
}
Write-Host '=== OPERATIONS LOG TAIL ==='
$log = 'C:\GoldenShield_Binance\storage\logs\operations.log'
if (Test-Path $log) { Get-Content $log -Tail 50 } else { Write-Host 'no operations.log' }
Write-Host '=== ERRORS LOG TAIL ==='
$err = 'C:\GoldenShield_Binance\storage\logs\errors.log'
if (Test-Path $err) { Get-Content $err -Tail 40 } else { Write-Host 'no errors.log' }
"""


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    if not (host and user and password):
        print("missing WIN_*")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    # ارفع السكربت مؤقتاً ثم نفّذه لتفادي مشاكل الاقتباس
    sftp = client.open_sftp()
    remote = r"C:\Users\Public\gs_diag.ps1"
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()

    cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"'
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    report = ROOT / "storage" / "logs" / "vps_diag_cmd.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(out + ("\nSTDERR:\n" + err if err.strip() else ""), encoding="utf-8")
    # طباعة ASCII-safe
    safe = out.encode("ascii", "replace").decode("ascii")
    print(safe)
    print("WROTE", report)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
