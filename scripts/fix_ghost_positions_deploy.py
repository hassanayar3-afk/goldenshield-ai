"""نشر إصلاح المراكز الشبحية + مزامنة AVAX + إعادة تشغيل."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "execution/binance_position_sync.py",
    "execution/trade_executor.py",
    "operations/message_templates.py",
    "operations/dashboard_templates.py",
    "operations/telegram_dashboard.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$good='C:\GoldenShield_Binance'
Set-Location $good
$env:PYTHONPATH=$good
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'

Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
}
Start-Sleep 2
Remove-Item 'storage\runtime\user_stopped.flag' -Force -EA SilentlyContinue
Remove-Item 'storage\runtime\bot_instance.lock' -Force -EA SilentlyContinue

& $py -c @"
from config.settings import get_settings
from database.connection import DatabaseConnection
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions
from operations.telegram_bot import TelegramBot
from operations.dashboard_templates import format_positions_list, compute_open_floating_pnl
from operations.telegram_keyboards import positions_list_keyboard, main_menu_keyboard
from data.exchange_client import get_exchange

s=get_settings()
db=DatabaseConnection(s.db_path)
ex=TradeExecutor(); ex.trade_repo=TradeRepository(db)
print('restored', ex.restore_open_positions())
print('synced', sync_binance_spot_positions(ex))
with db.connect() as conn:
    open_n=conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='open'\").fetchone()[0]
    closed_n=conn.execute(\"SELECT COUNT(*) c FROM trades WHERE status='closed'\").fetchone()[0]
    print('DB_OPEN', open_n, 'DB_CLOSED', closed_n)
    for r in conn.execute(\"SELECT symbol,exit_price,pnl,closed_at FROM trades WHERE status='closed' ORDER BY closed_at DESC LIMIT 5\").fetchall():
        print('CLOSED', dict(r) if hasattr(r,'keys') else r)

prices={}
exc=get_exchange()
for p in ex.position_manager.all():
    try:
        t=exc.fetch_ticker(p.symbol)
        prices[p.symbol]=float(t.get('last') or p.entry_price)
    except Exception:
        prices[p.symbol]=p.entry_price
total,pct=compute_open_floating_pnl(ex.position_manager.all(), prices)
print(f'FLOATING={total:.2f} COUNT={ex.position_manager.count()}')
tg=TelegramBot()
msg=(
  '🛡 <b>توضيح مهم عن الصفقات</b>\n\n'
  'الصفقات <b>لم تُمسح</b>. كانت ما زالت مفتوحة على Binance والبوت.\n'
  'سبب فراغ التقرير: الربح/الخسارة يُحتسب بعد <b>الإغلاق المسجّل</b> فقط.\n'
  'AVAX أُغلق على المنصة سابقاً (~خسارة صغيرة) دون تسجيل في التقرير — تم إصلاح التسجيل الآن.\n\n'
  f'📂 المراكز الحالية: <b>{ex.position_manager.count()}</b>\n'
  f'💹 العائم الآن: <b>{total:+.2f} USD</b> ({pct:+.2f}%)\n\n'
) + format_positions_list(list(ex.position_manager.all()), prices)
print('SENT', tg.send_message(msg, reply_markup=positions_list_keyboard(list(ex.position_manager.all()), prices, live=False)))
print('MENU', tg.send_message('القائمة الرئيسية', reply_markup=main_menu_keyboard(paused=False)))
"@

$tr = "cmd.exe /c cd /d $good && set PYTHONPATH=$good&& set PYTHONIOENCODING=utf-8&& `"$py`" -u main.py >> storage\logs\bot_stdout.log 2>&1"
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 16
Write-Host ('PYTHON_MAIN=' + @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count)
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
    sftp = client.open_sftp()
    for rel in FILES:
        sftp.put(str(ROOT / rel), r"C:\GoldenShield_Binance\\" + rel.replace("/", "\\"))
        print("UP", rel)
    sftp.close()
    remote = r"C:\Users\Public\gs_fix_ghost.ps1"
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
    path = ROOT / "storage" / "logs" / "fix_ghost_out.txt"
    path.write_text(out + "\n" + err, encoding="utf-8")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii")[-1200:])
    print("SAVED", path)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
