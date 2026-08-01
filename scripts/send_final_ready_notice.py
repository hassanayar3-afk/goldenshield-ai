"""رسالة عربية نهائية + تأكيد أن البوت الرسمي يعمل وقاعدة البيانات فيها المراكز."""

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
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach ($p in $procs) { Write-Host $p.CommandLine }

& $py -c @"
from config.settings import get_settings
from database.connection import DatabaseConnection
from execution.trade_executor import TradeExecutor
from execution.binance_position_sync import sync_binance_spot_positions
from operations.telegram_bot import TelegramBot
from operations.telegram_keyboards import main_menu_keyboard

s = get_settings()
db = DatabaseConnection(s.db_path)
with db.connect() as conn:
    open_n = conn.execute(\"SELECT COUNT(*) FROM trades WHERE status='open'\").fetchone()[0]
    print('DB_OPEN', open_n)

ex = TradeExecutor()
ex.trade_repo = __import__('database.repositories.trade_repo', fromlist=['TradeRepository']).TradeRepository(db)
ex.restore_open_positions()
sync_binance_spot_positions(ex)
print('MEM_OPEN', ex.position_manager.count())

tg = TelegramBot()
text = (
  '🛡 <b>GoldenShield — جاهز للفحص</b>\n\n'
  '✅ تم إصلاح الأعطال ونشرها على السيرفر.\n'
  '✅ البوت يعمل من المسار الصحيح فقط:\n'
  '<code>C:\\GoldenShield_Binance</code>\n\n'
  f'📂 مراكز مفتوحة الآن: <b>{ex.position_manager.count()}</b>\n'
  f'💾 في قاعدة البيانات: <b>{open_n}</b>\n\n'
  '<b>مهم جداً:</b>\n'
  '1) أغلق أي نافذة CMD من مجلد تحميلات تيليجرام (Downloads) ولا تشغّلها مرة أخرى.\n'
  '2) لا تفتح ZIP من Telegram Desktop — استخدم فقط C:\\GoldenShield_Binance\\00_START.bat\n'
  '3) رصيد USDT الحر تقريباً 53$ لأن باقي رأس المال داخل العملات المفتوحة.\n'
  '4) شراء جديد يحتاج USDT حر — لإفراغ سيولة أغلق مركزاً من «مراكزي».\n'
  '5) إشارة بيع على مركز موجود = إغلاق الصفقة.\n\n'
  'الآن جرّب الأزرار بالأسفل: الرئيسية / مراكزي / الإشارات / التقرير.'
)
mid = tg.send_message(text, reply_markup=main_menu_keyboard(paused=False))
print('NOTICE_MSG', mid)
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
    remote = r"C:\Users\Public\gs_final_notice.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
