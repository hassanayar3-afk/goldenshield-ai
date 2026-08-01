"""تشخيص مراكز/صفقات/عمليات البوت على VPS."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$bot = 'C:\GoldenShield_Binance'
Write-Host '=== PROCESSES ==='
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("main.py count=" + $procs.Count)
$procs | ForEach-Object { Write-Host ("PID=" + $_.ProcessId + " CL=" + $_.CommandLine.Substring(0, [Math]::Min(100, $_.CommandLine.Length))) }

Write-Host '=== LOCAL DB OPEN/CLOSED ==='
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'
py -c @"
from database.connection import init_database
from config.settings import get_settings
s=get_settings()
db=init_database(s.db_path)
with db.connect() as conn:
    try:
        rows=conn.execute('SELECT id,symbol,side,entry_price,exit_price,pnl,status,opened_at,closed_at FROM trades ORDER BY id DESC LIMIT 20').fetchall()
        print('TRADES', len(rows))
        for r in rows:
            print(dict(r))
    except Exception as e:
        print('trades_err', e)
        cols=conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
        print('tables', [dict(c) for c in cols])
"@

Write-Host '=== BINANCE DEMO OPEN ORDERS / BALANCES SNAPSHOT ==='
py -c @"
from data.exchange_client import get_exchange
ex=get_exchange()
try:
    bal=ex.fetch_balance()
    total={k:v for k,v in (bal.get('total') or {}).items() if float(v or 0)>0}
    print('BAL_NONZERO', total)
except Exception as e:
    print('bal_err', e)
try:
    oo=ex.fetch_open_orders()
    print('OPEN_ORDERS', len(oo))
    for o in oo[:15]:
        print({k:o.get(k) for k in ('id','symbol','type','side','amount','price','stopPrice','status')})
except Exception as e:
    print('oo_err', e)
try:
    # recent trades sample
    for sym in ['ADA/USDT','BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT']:
        try:
            tr=ex.fetch_my_trades(sym, limit=5)
            if tr:
                print('MYTRADES', sym, len(tr))
                for t in tr[-3:]:
                    print({k:t.get(k) for k in ('id','side','amount','price','cost','timestamp')})
        except Exception as te:
            pass
except Exception as e:
    print('mt_err', e)
"@

Write-Host '=== LOG TAIL ==='
$log = Join-Path $bot 'storage\logs\operations.log'
if (Test-Path $log) { Get-Content $log -Tail 60 }
$err = Join-Path $bot 'storage\logs\errors.log'
if (Test-Path $err) { Write-Host '--- errors ---'; Get-Content $err -Tail 40 }
"""


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
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
    remote = r"C:\Users\Public\gs_diag_trades.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    report = ROOT / "storage" / "logs" / "vps_trades_diag.txt"
    report.write_text(out + ("\nSTDERR:\n" + err if err.strip() else ""), encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    print("WROTE", report)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
