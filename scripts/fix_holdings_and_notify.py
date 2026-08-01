"""إيقاف النسخ المكررة + مزامنة الأرصدة + إرسال تقرير تيليجرام."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "main.py",
    "execution/binance_position_sync.py",
    "execution/order_manager.py",
    "execution/sl_attachment_guard.py",
    "execution/trade_executor.py",
    "operations/single_instance.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
# اقتل كل عمليات البوت
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2
Get-Process py,python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*Python*' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -ErrorAction SilentlyContinue
Set-Location $bot
$env:PYTHONPATH=$bot
$env:PYTHONIOENCODING='utf-8'
# مزامنة سريعة قبل التشغيل
py -c @"
from config.settings import load_settings
load_settings(reload=True)
from database.connection import init_database
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from risk.risk_orchestrator import RiskOrchestrator
from execution.binance_position_sync import sync_binance_spot_positions, format_holdings_report
s=load_settings()
db=init_database(s.db_path)
ex=TradeExecutor(risk=RiskOrchestrator())
ex.trade_repo=TradeRepository(db)
ex.restore_open_positions()
added=sync_binance_spot_positions(ex)
print('SYNCED', added)
print(format_holdings_report(ex))
open('storage/logs/holdings_report.txt','w',encoding='utf-8').write(format_holdings_report(ex)+'\nSYNCED='+str(added))
"@
Start-Process -FilePath 'py' -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep 12
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') }).Count
Write-Host ("RUNNING count=" + $n)
if (Test-Path (Join-Path $bot 'storage\logs\holdings_report.txt')) {
  Write-Host '--- HOLDINGS ---'
  Get-Content (Join-Path $bot 'storage\logs\holdings_report.txt')
}
"""


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host, username=user, password=password, timeout=40, allow_agent=False, look_for_keys=False
    )
    sftp = client.open_sftp()
    remote_root = r"C:\GoldenShield_Binance"
    for rel in FILES:
        local = ROOT / rel
        if not local.exists():
            print("missing", rel)
            continue
        rpath = remote_root + "\\" + rel.replace("/", "\\")
        parent = str(Path(rpath).parent)
        try:
            sftp.stat(parent)
        except OSError:
            # mkdir parents
            parts = parent.split("\\")
            cur = parts[0] + "\\"
            for p in parts[1:]:
                cur = cur.rstrip("\\") + "\\" + p
                try:
                    sftp.stat(cur)
                except OSError:
                    try:
                        sftp.mkdir(cur)
                    except OSError:
                        pass
        sftp.put(str(local), rpath)
        print("UP", rel)
    remote_ps = r"C:\Users\Public\gs_fix_holdings.ps1"
    with sftp.file(remote_ps, "w") as fh:
        fh.write(PS)
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR", err.encode("ascii", "replace").decode("ascii"))

    # اقرأ التقرير من السيرفر وأرسله
    sftp = client.open_sftp()
    report = ""
    try:
        with sftp.file(remote_root + r"\storage\logs\holdings_report.txt", "r") as fh:
            report = fh.read().decode("utf-8", "replace")
    except Exception as exc:
        report = f"(تعذّر قراءة التقرير: {exc})"
    sftp.close()
    client.close()

    if token and chat:
        text = (
            "توضيح مهم — ليست خربطة عشوائية:\n"
            "1) كانت تعمل نسختان من البوت معاً فصار تعارض في التيليجرام.\n"
            "2) الصفقات نُفّذت على Binance لكن البوت لم يسجّلها داخلياً بعد فشل تأكيد SL.\n"
            "3) الآن: إيقاف النسخ المكررة + مزامنة الأرصدة إلى المراكز.\n\n"
            f"{report}\n\n"
            "افتح من القائمة: مراكزي / التقرير"
        )
        # strip html tags for safety if any
        import re

        plain = re.sub(r"<[^>]+>", "", text)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": plain[:3500]},
            timeout=60,
        )
        print("TELEGRAM_SENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
