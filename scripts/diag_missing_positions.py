"""تشخيص اختفاء المراكز: عمليات البوت + DB + أرصدة Binance + ذيل السجلات."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$good = 'C:\GoldenShield_Binance'
Set-Location $good
$env:PYTHONPATH = $good
$env:PYTHONIOENCODING = 'utf-8'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'

Write-Host '=== PROCS ==='
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach ($p in $procs) {
  Write-Host ('PID=' + $p.ProcessId + ' NAME=' + $p.Name)
  Write-Host $p.CommandLine
}
Write-Host ('USER_STOPPED=' + (Test-Path 'storage\runtime\user_stopped.flag'))

Write-Host '=== LOG TAIL ==='
Get-Content 'storage\logs\bot_stdout.log' -Tail 80 -ErrorAction SilentlyContinue
Write-Host '=== ERRORS TAIL ==='
Get-Content 'storage\logs\errors.log' -Tail 40 -ErrorAction SilentlyContinue

& $py -c @"
from config.settings import get_settings
from data.exchange_client import get_exchange
from database.connection import DatabaseConnection
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions, format_holdings_report

s = get_settings()
print('SETTINGS demo', s.binance_demo_trading, 'mode', s.execution_mode, 'backend', s.execution_backend)
print('DB', s.db_path)

db = DatabaseConnection(s.db_path)
with db.connect() as conn:
    open_n = conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='open'\").fetchone()[0]
    closed_n = conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='closed'\").fetchone()[0]
    print('DB_OPEN', open_n, 'DB_CLOSED', closed_n)
    print('--- OPEN ROWS ---')
    for r in conn.execute(\"SELECT id,symbol,side,amount,entry_price,signal_score,opened_at FROM trades WHERE status='open' ORDER BY opened_at\").fetchall():
        print(dict(r) if hasattr(r,'keys') else r)
    print('--- LAST CLOSED ---')
    for r in conn.execute(\"SELECT symbol,side,amount,entry_price,exit_price,pnl,closed_at FROM trades WHERE status='closed' ORDER BY closed_at DESC LIMIT 15\").fetchall():
        print(dict(r) if hasattr(r,'keys') else r)
    print('--- DECISIONS RECENT ---')
    try:
        for r in conn.execute(\"SELECT symbol,action,reason,pnl,recorded_at FROM decision_records ORDER BY recorded_at DESC LIMIT 20\").fetchall():
            print(dict(r) if hasattr(r,'keys') else r)
    except Exception as e:
        print('decisions_err', e)

exch = get_exchange()
bal = exch.fetch_balance() or {}
usdt = bal.get('USDT') or {}
free = float(usdt.get('free') if isinstance(usdt, dict) else (usdt or 0))
total_usdt = float(usdt.get('total') if isinstance(usdt, dict) else (usdt or 0))
print(f'USDT_FREE={free:.4f} USDT_TOTAL={total_usdt:.4f}')
print('--- NONSTABLE BALANCES ---')
stables={'USDT','USDC','BUSD','FDUSD','TUSD','DAI','EUR','USD'}
total = bal.get('total') or {}
for asset, qty in sorted(total.items()):
    try:
        q=float(qty or 0)
    except Exception:
        continue
    if asset.upper() in stables or q <= 0:
        continue
    if q < 0.0001 and asset.upper() not in {'BTC','ETH'}:
        continue
    print(f'ASSET {asset}={q}')

from database.repositories.trade_repo import TradeRepository
executor = TradeExecutor()
executor.trade_repo = TradeRepository(db)
restored = executor.restore_open_positions()
synced = sync_binance_spot_positions(executor)
print('restored', restored, 'synced', synced)
print('mem_open', executor.position_manager.count())
print(format_holdings_report(executor))
"@
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
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_diag_missing_pos.ps1"
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
    out_path = ROOT / "storage" / "logs" / "diag_missing_positions_out.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out + (("\nSTDERR:\n" + err) if err.strip() else ""), encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-2500:])
    print("SAVED", out_path)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
