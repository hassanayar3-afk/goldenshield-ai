"""احسب العائم الحالي + تقدير لو رأس المال 500$ بنفس نسب الربح."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
Set-Location 'C:\GoldenShield_Binance'
$env:PYTHONPATH='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
& $py -c @"
from config.settings import get_settings
from database.connection import DatabaseConnection
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions
from data.exchange_client import get_exchange
from operations.dashboard_templates import compute_open_floating_pnl

s=get_settings()
db=DatabaseConnection(s.db_path)
ex=TradeExecutor(); ex.trade_repo=TradeRepository(db)
ex.restore_open_positions()
sync_binance_spot_positions(ex)
exc=get_exchange()
prices={}
invested=0.0
print('POSITIONS')
for p in ex.position_manager.all():
    try:
        t=exc.fetch_ticker(p.symbol)
        px=float(t.get('last') or t.get('close') or p.entry_price)
    except Exception:
        px=float(p.entry_price)
    prices[p.symbol]=px
    cost=float(p.entry_price)*float(p.amount)
    invested += cost
    if p.side.value=='buy':
        pnl=(px-p.entry_price)*p.amount
        pct=((px-p.entry_price)/p.entry_price)*100 if p.entry_price else 0
    else:
        pnl=(p.entry_price-px)*p.amount
        pct=((p.entry_price-px)/p.entry_price)*100 if p.entry_price else 0
    # points roughly absolute price move
    pts=abs(px-p.entry_price)
    print(f'{p.symbol}|entry={p.entry_price:.6g}|now={px:.6g}|amt={p.amount:.8g}|cost={cost:.2f}|pnl={pnl:.2f}|pct={pct:.2f}|pts={pts:.6g}|sl={p.stop_loss:.6g}|tp={p.take_profit:.6g}')

total, pct = compute_open_floating_pnl(ex.position_manager.all(), prices)
print(f'TOTAL_FLOAT={total:.2f}')
print(f'TOTAL_PCT_ON_INVESTED={pct:.2f}')
print(f'INVESTED={invested:.2f}')
# if same % return on 500 deployed similarly
hyp500 = 500.0 * (total/invested) if invested>0 else 0.0
print(f'HYP_500_SAME_PCT={hyp500:.2f}')
# if 1% risk sizing: risk=5 per trade, sl~3% => position notional ~ risk/0.03 = 166.67 per trade
# 7 trades would need more than 500 so assume max affordable equal split of 500 across n positions
n=max(ex.position_manager.count(),1)
per=500.0/n
scaled=0.0
print('SCALED_1PCT_STYLE')
for p in ex.position_manager.all():
    px=prices[p.symbol]
    # amount if spent 'per' USDT at entry
    amt = per/float(p.entry_price) if p.entry_price>0 else 0
    if p.side.value=='buy':
        pnl=(px-p.entry_price)*amt
        pct=((px-p.entry_price)/p.entry_price)*100 if p.entry_price else 0
    else:
        pnl=(p.entry_price-px)*amt
        pct=((p.entry_price-px)/p.entry_price)*100 if p.entry_price else 0
    scaled += pnl
    print(f'{p.symbol}|size_usdt={per:.2f}|pnl={pnl:.2f}|pct={pct:.2f}')
print(f'SCALED_EQUAL_500_TOTAL={scaled:.2f}')
"@
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST"),
        username=os.getenv("WIN_USER"),
        password=os.getenv("WIN_PASSWORD"),
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_calc500.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
