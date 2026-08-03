"""إصلاح أزرار تيليجرام: إيقاف الفيض 429 + أولوية callbacks + فاصل آمن."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()

UPLOADS = [
    "operations/telegram_bot.py",
    "operations/telegram_commands.py",
    "operations/telegram_dashboard.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$envp=Join-Path $g '.env'
$map=@{
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='5'
  'BOT_FORCE_ACTIVE'='true'
}
$lines=@(Get-Content $envp -EA SilentlyContinue)
$keys=@{}
$out=foreach($line in $lines){
  if($line -match '^\s*#' -or $line -notmatch '='){ $line; continue }
  $k=$line.Split('=',2)[0].Trim()
  if($map.ContainsKey($k)){ $keys[$k]=$true; "$k=$($map[$k])" } else { $line }
}
foreach($k in $map.Keys){ if(-not $keys.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
$utf8=New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($envp, $out, $utf8)

schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'main\.py|run_official_bot'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 3
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 12
$m=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN_COUNT=' + $m.Count)
Select-String -Path $envp -Pattern 'TELEGRAM_LIVE_SIGNALS_SECONDS|TELEGRAM_LIVE_POSITIONS_SECONDS' | ForEach-Object { $_.Line }
Write-Host 'BUTTONS_FIX_APPLIED'
"""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    for rel in UPLOADS:
        sftp.put(str(ROOT / rel), KEEP + "\\" + rel.replace("/", "\\"))
        print("UPLOADED", rel)

    # deleteWebhook first
    if TOKEN:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/deleteWebhook",
                params={"drop_pending_updates": False},
                timeout=15,
            )
            print("deleteWebhook", r.status_code, r.text[:120])
        except Exception as exc:
            print("deleteWebhook_err", exc)

    remote = r"C:\ProgramData\GoldenShield\_fix_buttons_flood.ps1"
    with sftp.file(remote, "w") as fh:
        fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()
    _, o, e = ssh.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=120
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))

    # send fresh main menu if possible
    if TOKEN and CHAT:
        try:
            from operations.dashboard_templates import format_main_dashboard
            # simple recovery message with keyboard via API
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "📊 الرئيسية", "callback_data": "view:main"},
                        {"text": "📡 الإشارات", "callback_data": "view:market"},
                    ],
                    [
                        {"text": "📂 المراكز", "callback_data": "view:positions"},
                        {"text": "📜 السجل", "callback_data": "view:history"},
                    ],
                ]
            }
            text = (
                "✅ <b>تم إصلاح الأزرار</b>\n"
                "تم إيقاف التحديث العدواني الذي تسبب بحظر تيليجرام (429).\n"
                "لوحة تيليجرام كل 15 ثانية — نافذة CMD تبقى للإشارات.\n"
                "جرّب الأزرار من هذه الرسالة."
            )
            resp = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": kb,
                },
                timeout=20,
            )
            print("sendMenu", resp.status_code, resp.text[:200])
        except Exception as exc:
            print("sendMenu_err", exc)

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
