"""بعد النشر: يتحقق من بوت واحد + مراكز + رصيد + يرسل قائمة تيليجرام."""

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
Set-Location $bot
$env:PYTHONPATH = $bot
$env:PYTHONIOENCODING = 'utf-8'

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ("BOT_PROCS=" + $procs.Count)
foreach ($p in $procs) { Write-Host ("PID=" + $p.ProcessId) }

$py = 'py'
try { & $py -V | Out-Null } catch { $py = 'python' }

& $py -c @"
from config.settings import get_settings
from data.exchange_client import get_exchange
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions, format_holdings_report
from operations.telegram_bot import TelegramBot
from operations.telegram_keyboards import main_menu_keyboard, positions_list_keyboard

s = get_settings()
print('demo', s.binance_demo_trading, 'mode', s.execution_mode, 'backend', s.execution_backend)
print('manual', s.manual_entry_required, 'auto_min', s.auto_entry_min_percent)

ex = get_exchange()
bal = ex.fetch_balance() or {}
usdt = bal.get('USDT') or {}
free = float(usdt.get('free') if isinstance(usdt, dict) else (usdt or 0))
print(f'USDT_FREE={free:.4f}')

executor = TradeExecutor()
restored = executor.restore_open_positions()
synced = sync_binance_spot_positions(executor)
print('restored', restored, 'synced', synced)
print('open_count', executor.position_manager.count())
positions = executor.position_manager.all()
for p in positions:
    print(f'POS {p.symbol} {p.side.value} amt={p.amount:.8g} entry={p.entry_price:.6g}')

tg = TelegramBot()
menu = (
    '🛡 <b>GoldenShield — فحص صحة</b>\n'
    f'مراكز مفتوحة: <b>{len(positions)}</b>\n'
    f'USDT حر: <b>{free:.2f}</b>\n'
    f'عمليات البوت: راجع السيرفر\n'
    'اضغط الأزرار للتأكد أنها تعمل.'
)
mid = tg.send_message(menu, reply_markup=main_menu_keyboard(paused=False))
print('MAIN_MENU_MSG', mid)
report = format_holdings_report(executor)
prices = {p.symbol: p.entry_price for p in positions}
pmid = tg.send_message(report, reply_markup=positions_list_keyboard(positions, prices, live=False))
print('POSITIONS_MSG', pmid)
print('HEALTH_OK')
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
    remote = r"C:\Users\Public\gs_verify_health.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=180,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
