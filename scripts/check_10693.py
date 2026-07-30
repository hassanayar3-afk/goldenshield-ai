from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"

CODE = r"""
from data.exchange_client import get_exchange, reset_exchange
from config.settings import load_settings

load_settings(reload=True)
reset_exchange()
ex = get_exchange()
bal = ex.fetch_balance()
info = bal.get("info") or {}
print("uid", info.get("uid"))
usdt = float((bal.get("USDT") or {}).get("total") or 0)
usdc = float((bal.get("USDC") or {}).get("total") or 0)
ltc = float((bal.get("LTC") or {}).get("total") or 0)
print("USDT", usdt)
print("USDC", usdc)
print("LTC", ltc)
try:
    px = float((ex.fetch_ticker("LTC/USDT") or {}).get("last") or 0)
except Exception:
    px = 0.0
ltc_v = ltc * px
total = usdt + usdc + ltc_v
print("LTC_PRICE", px)
print("LTC_VALUE_USDT", round(ltc_v, 2))
print("EST_TOTAL_USDT", round(total, 2))
print("NEAR_10693", abs(total - 10693) < 100)
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = KEEP + r"\_cmp10693.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(CODE)
    sftp.close()
    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -Command "Set-Location \'{KEEP}\'; & \'{PY}\' _cmp10693.py"',
        timeout=120,
    )
    print((o.read() + e.read()).decode("utf-8", errors="replace").encode("ascii", "replace").decode("ascii"))
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
