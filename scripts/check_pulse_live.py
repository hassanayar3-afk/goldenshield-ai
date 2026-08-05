"""تحقق سريع من نبض البوت على VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$g = 'C:\GoldenShield_Binance'
$m = @(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
Write-Output ("MAIN=" + $m.Count)
$log = Join-Path $g 'storage\logs\bot_stdout.log'
if (Test-Path $log) {
  Get-Content $log -Tail 35 -Encoding UTF8 -EA SilentlyContinue
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
    remote = r"C:\GoldenShield_Binance\storage\runtime\_check_pulse.ps1"
    with sftp.open(remote, "w") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()
    _i, stdout, _ = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=60,
    )
    text = stdout.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
