"""مزامنة المراكز المفتوحة وإرسالها إلى تيليجرام فوراً."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "execution/binance_position_sync.py",
    "scripts/sync_holdings_local.py",
    "main.py",
    "operations/telegram_dashboard.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$bot='C:\GoldenShield_Binance'
Set-Location $bot
$env:PYTHONPATH=$bot
$env:PYTHONIOENCODING='utf-8'
Write-Host 'SYNC_START'
py -u scripts\sync_holdings_local.py
Write-Host 'SYNC_DONE'
if (Test-Path storage\logs\holdings_report.txt) {
  Get-Content storage\logs\holdings_report.txt
}
# أعد تشغيل البوت بنسخة واحدة ليقرأ المراكز من DB
taskkill /F /IM python.exe /T 2>$null
taskkill /F /IM py.exe /T 2>$null
Start-Sleep -Seconds 3
Remove-Item storage\runtime\bot_instance.lock -Force -ErrorAction SilentlyContinue
Remove-Item storage\runtime\user_stopped.flag -Force -ErrorAction SilentlyContinue
Start-Process -FilePath 'py' -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 10
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' }).Count
Write-Host ("RUNNING=" + $n)
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
        host,
        username=user,
        password=password,
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    remote_root = r"C:\GoldenShield_Binance"
    for rel in FILES:
        local = ROOT / rel
        rpath = remote_root + "\\" + rel.replace("/", "\\")
        parent = str(Path(rpath).parent)
        try:
            sftp.stat(parent)
        except OSError:
            try:
                sftp.mkdir(parent)
            except OSError:
                pass
        sftp.put(str(local), rpath)
        print("UP", rel)
    with sftp.file(r"C:\Users\Public\gs_sync_pos.ps1", "w") as fh:
        fh.write(PS)
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\Users\\Public\\gs_sync_pos.ps1"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR", err.encode("ascii", "replace").decode("ascii"))

    sftp = client.open_sftp()
    report = ""
    try:
        with sftp.file(remote_root + r"\storage\logs\holdings_report.txt", "r") as fh:
            report = fh.read().decode("utf-8", "replace")
    except Exception as exc:
        report = f"تعذر قراءة التقرير: {exc}"
    sftp.close()
    client.close()

    plain = re.sub(r"<[^>]+>", "", report).strip()
    if not plain:
        plain = "لا توجد مراكز بعد المزامنة — تحقق من رصيد Binance Demo."

    kb = {
        "inline_keyboard": [
            [{"text": "📂 مراكزي الآن", "callback_data": "view:positions"}],
            [{"text": "📋 التقرير", "callback_data": "view:report"}],
            [{"text": "🏠 الرئيسية", "callback_data": "view:main"}],
        ]
    }
    if token and chat:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat,
                "text": (
                    "📂 صفقاتك المفتوحة (مزامنة من Binance Demo):\n\n"
                    f"{plain}\n\n"
                    "اضغط «مراكزي الآن» لعرضها داخل البوت."
                )[:3500],
                "reply_markup": json.dumps(kb, ensure_ascii=False),
            },
            timeout=60,
        )
        print("TELEGRAM_SENT")
    print(plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
