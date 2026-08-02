"""تفاصيل AVAX + مسار عمل البوت + إعادة دفع المراكز لتيليجرام."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Set-Location $good
$env:PYTHONPATH=$good
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'

Write-Host '=== CWD OF BOT ==='
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' } | ForEach-Object {
  Write-Host ('PID=' + $_.ProcessId)
  Write-Host $_.CommandLine
  try {
    $p = Get-Process -Id $_.ProcessId -ErrorAction Stop
    Write-Host ('Path=' + $p.Path)
  } catch {}
}

& $py -c @"
from data.exchange_client import get_exchange
from config.settings import get_settings
from database.connection import DatabaseConnection
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions
from operations.telegram_bot import TelegramBot
from operations.telegram_keyboards import main_menu_keyboard, positions_list_keyboard
from operations.dashboard_templates import format_positions_list, compute_open_floating_pnl

ex = get_exchange()
# AVAX trades
try:
    trades = ex.fetch_my_trades('AVAX/USDT', limit=20) or []
    print('AVAX_TRADES', len(trades))
    for t in trades[-10:]:
        print(t.get('datetime'), t.get('side'), t.get('amount'), t.get('price'), t.get('cost'))
except Exception as e:
    print('AVAX_TRADES_ERR', e)

bal = ex.fetch_balance() or {}
avax = bal.get('AVAX') or {}
print('AVAX_BAL', avax)

s=get_settings()
db=DatabaseConnection(s.db_path)
executor=TradeExecutor()
executor.trade_repo=TradeRepository(db)
executor.restore_open_positions()
sync_binance_spot_positions(executor)
# prices
prices={}
for p in executor.position_manager.all():
    try:
        t=ex.fetch_ticker(p.symbol)
        prices[p.symbol]=float(t.get('last') or t.get('close') or p.entry_price)
    except Exception:
        prices[p.symbol]=p.entry_price
total,pct=compute_open_floating_pnl(executor.position_manager.all(), prices)
print(f'FLOATING={total:.2f} PCT={pct:.2f} COUNT={executor.position_manager.count()}')
text = '🛡 <b>تأكيد المراكز</b>\nالمراكز لم تُغلق — ما زالت مفتوحة.\n\n' + format_positions_list(list(executor.position_manager.all()), prices)
tg=TelegramBot()
mid=tg.send_message(text, reply_markup=positions_list_keyboard(list(executor.position_manager.all()), prices, live=False))
print('SENT_POS', mid)
mid2=tg.send_message('📂 اضغط مراكزي من القائمة إن لم تظهر التفاصيل.', reply_markup=main_menu_keyboard(paused=False))
print('SENT_MENU', mid2)
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
    remote = r"C:\Users\Public\gs_confirm_pos.ps1"
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
    path = ROOT / "storage" / "logs" / "diag_confirm_pos.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out + "\n" + err, encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-1500:])
    print("SAVED", path)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
