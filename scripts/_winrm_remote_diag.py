"""فحص سريع للبوت على Windows VPS عبر WinRM (basic)."""
from __future__ import annotations

import os
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PS = r"""
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
Set-Location $bot
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (-not (Test-Path $py)) { $py = 'py' }
Write-Host ('PY=' + $py)
& $py --version 2>&1
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Host ('BOT_PROCS=' + $procs.Count)
$daemon = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'gs_daemon' })
Write-Host ('DAEMON=' + $daemon.Count)
foreach ($name in @('bot_stderr.log','bot_stdout.log','gs_daemon.log')) {
  $p = Join-Path $bot ('storage\logs\' + $name)
  Write-Host ('--- ' + $name + ' ---')
  if (Test-Path $p) { Get-Content $p -Tail 25 -EA SilentlyContinue } else { Write-Host 'MISSING' }
}
Write-Host '--- IMPORT TEST ---'
$env:PYTHONPATH = $bot
& $py -c "import sys; sys.path.insert(0, r'$bot'); import main" 2>&1 | Select-Object -First 30
"""


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "Administrator").strip()
    password = os.getenv("WIN_PASSWORD") or ""
    if not (host and password):
        print("missing WIN_*")
        return 1
    session = winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=300,
        operation_timeout_sec=120,
    )
    r = session.run_ps(PS)
    print((r.std_out or b"").decode("utf-8", errors="replace"))
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[-1200:])
    return 0 if r.status_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
