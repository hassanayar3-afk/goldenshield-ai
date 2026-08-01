"""رفع سكربت القتل/المزامنة وتشغيله ثم إرسال تقرير تيليجرام."""

from __future__ import annotations

import os
import re
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)


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
    local_ps = ROOT / "storage" / "logs" / "gs_kill_sync_start.ps1"
    sftp.put(str(local_ps), r"C:\Users\Public\gs_kill_sync_start.ps1")
    sftp.close()

    _i, stdout, stderr = client.exec_command(
        'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\\Users\\Public\\gs_kill_sync_start.ps1"',
        timeout=200,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err.encode("ascii", "replace").decode("ascii"))

    sftp = client.open_sftp()
    report = ""
    try:
        with sftp.file(
            r"C:\GoldenShield_Binance\storage\logs\holdings_report.txt", "r"
        ) as fh:
            report = fh.read().decode("utf-8", "replace")
    except Exception as exc:
        report = f"تعذر قراءة التقرير: {exc}\n{out[-1500:]}"
    sftp.close()
    client.close()

    plain = re.sub(r"<[^>]+>", "", report)
    msg = (
        "تم الإصلاح الآن:\n"
        "- إيقاف النسخ المكررة من البوت (سبب خربطة الداشبورد)\n"
        "- مزامنة أرصدة Binance Demo إلى المراكز\n"
        "- صفقاتك لم تُلغَ من المنصة؛ كانت موجودة كرصيد لكن البوت لم يعرضها\n\n"
        f"{plain}\n\n"
        "من تيليجرام افتح: مراكزي ثم التقرير"
    )
    if token and chat:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": msg[:3500]},
            timeout=60,
        )
        print("TELEGRAM_SENT")
    print(plain[:1000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
