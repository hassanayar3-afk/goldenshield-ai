"""فحص إعدادات الرموز والرصيد على السيرفر."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh, cmd, timeout=180):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(text[-4500:].encode("ascii", "replace").decode("ascii"))
    return text


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

    run(ssh, f'powershell -NoProfile -Command "Get-Content \'{KEEP}\\config\\trading_pairs.yaml\'"')
    run(ssh, f'powershell -NoProfile -Command "Get-Content \'{KEEP}\\config\\symbol_registry.yaml\'"')

    code = r'''
from config.settings import load_settings
from operations.symbol_registry import get_symbol_registry
from data.exchange_client import get_exchange, reset_exchange

s = load_settings(reload=True)
print('trading_pairs', getattr(s, 'trading_pairs', None))
reg = get_symbol_registry()
loaded = reg.load(s.trading_pairs)
print('loaded', loaded)
print('active', reg.active_pairs())
print('all', [(x.id, x.enabled, x.category) for x in reg.all_specs()])

reset_exchange()
ex = get_exchange()
print('exchange_urls', getattr(ex, 'urls', {}).get('api'))
try:
    bal = ex.fetch_balance()
    usdt = bal.get('USDT') or {}
    print('USDT', {k: usdt.get(k) for k in ('free','used','total')})
    nonzero = [(k,v) for k,v in (bal.get('total') or {}).items() if v and float(v)>0]
    print('assets', nonzero[:20])
except Exception as e:
    print('BAL_ERR', type(e).__name__, e)

# why no auto: sample scores from last cycle not available; print thresholds
print('auto_min', s.auto_entry_min_percent, 'manual', s.manual_entry_required)
'''
    remote = KEEP + r"\_diag2.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(code)
    sftp.close()
    run(ssh, f'powershell -NoProfile -Command "Set-Location \'{KEEP}\'; & \'{PY}\' _diag2.py"')
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
