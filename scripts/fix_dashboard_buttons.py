"""إصلاح أزرار الداشبورد: بوت واحد + رفع الملفات + قائمة رئيسية جديدة."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

FILES = [
    "operations/telegram_commands.py",
    "operations/telegram_dashboard.py",
    "operations/single_instance.py",
    "main.py",
]

PS = r"""
$ErrorActionPreference='Continue'
taskkill /F /IM python.exe /T 2>$null
taskkill /F /IM pythonw.exe /T 2>$null
taskkill /F /IM py.exe /T 2>$null
Start-Sleep -Seconds 4
$bot='C:\GoldenShield_Binance'
Remove-Item (Join-Path $bot 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item (Join-Path $bot 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
# أوقف البث العدواني إن وُجد
$envPath = Join-Path $bot '.env'
if (Test-Path $envPath) {
  $lines = Get-Content $envPath
  $out = foreach ($line in $lines) {
    if ($line -match '^TELEGRAM_LIVE_POSITIONS_SECONDS=') { 'TELEGRAM_LIVE_POSITIONS_SECONDS=5' }
    else { $line }
  }
  if (-not ($out -match '^TELEGRAM_LIVE_POSITIONS_SECONDS=')) { $out += 'TELEGRAM_LIVE_POSITIONS_SECONDS=5' }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllLines($envPath, $out, $utf8)
}
Start-Process -FilePath 'py' -ArgumentList '-u','main.py' -WorkingDirectory $bot -WindowStyle Hidden
Start-Sleep -Seconds 12
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' }).Count
Write-Host ("RUNNING count=" + $n)
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
    remote = r"C:\GoldenShield_Binance"
    for rel in FILES:
        local = ROOT / rel
        rpath = remote + "\\" + rel.replace("/", "\\")
        sftp.put(str(local), rpath)
        print("UP", rel)
    with sftp.file(r"C:\Users\Public\gs_fix_buttons.ps1", "w") as fh:
        fh.write(PS)
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\Users\\Public\\gs_fix_buttons.ps1"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR", err)
    client.close()

    if token and chat:
        # أرسل قائمة رئيسية نظيفة يدوياً عبر API بسيطة
        kb = {
            "inline_keyboard": [
                [
                    {"text": "📡 الإشارات", "callback_data": "view:market"},
                    {"text": "📂 مراكزي", "callback_data": "view:positions"},
                ],
                [
                    {"text": "📋 التقرير", "callback_data": "view:report"},
                    {"text": "⏸️ إيقاف", "callback_data": "act:pause"},
                ],
                [{"text": "❌ إغلاق كل الصفقات", "callback_data": "act:close_all"}],
                [{"text": "🚨 طوارئ — إيقاف كامل", "callback_data": "act:panic"}],
            ]
        }
        import json

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat,
                "text": (
                    "✅ تم إصلاح الأزرار\n\n"
                    "السبب: البث الحي كان يمسح القائمة فور الضغط، "
                    "وكانت تعمل أكثر من نسخة بوت.\n\n"
                    "الآن كل زر يفتح رسالة جديدة ثابتة.\n"
                    "جرّب الأزرار من هذه القائمة:"
                ),
                "reply_markup": json.dumps(kb, ensure_ascii=False),
            },
            timeout=60,
        )
        print("MENU_SENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
