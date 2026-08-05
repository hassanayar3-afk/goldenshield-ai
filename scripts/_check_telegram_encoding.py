"""Check if Arabic source on VPS is UTF-8 intact vs mojibake."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
$env:PYTHONPATH=$bot
$env:PYTHONIOENCODING='utf-8'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if(-not (Test-Path $py)){ $py='py' }
& $py -c @'
from pathlib import Path
from operations.dashboard_templates import format_main_dashboard
from operations.message_templates import _BRAND

p = Path(r"C:\GoldenShield_Binance\operations\dashboard_templates.py")
raw = p.read_bytes()
print("HAS_UTF8_AR", b"\xd9\x84\xd9\x88\xd8\xad\xd8\xa9" in raw)  # لوحة
print("HAS_MOJIBAKE_BYTES", "Ù„ÙˆØ­Ø©".encode("utf-8") in raw)
text = format_main_dashboard(
    env="demo", mode="PAPER", balance=5336.03, daily_pnl="+0",
    open_count=0, paused=False, kill_switch="OK", pairs_count=14,
)
print("BRAND_OK", "GoldenShield" in text)
print("AR_OK", "لوحة" in text or "الحالة" in text)
print("MOJI", "Ø" in text or "Ù" in text[:200])
# show first 120 chars as unicode escapes
print("SAMPLE", text[:120].encode("unicode_escape").decode("ascii"))
'@
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_check_enc.ps1"
    sftp = c.open_sftp()
    with sftp.file(remote, "wb") as f:
        f.write(PS.encode("utf-8"))
    sftp.close()
    _, o, e = c.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=60,
    )
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[-1500:])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
