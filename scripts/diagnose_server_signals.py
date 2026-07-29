"""تشخيص إشارات السيرفر ↔ تيليجرام ( Contabo paper )."""

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

TOKEN = os.getenv("TELEGRAM_TOKEN") or ""
CHAT = str(os.getenv("TELEGRAM_CHAT_ID") or "")


def ssh(cmd: str, timeout: int = 90) -> str:
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts._deploy_env import require_deploy_credentials

    host, user, password = require_deploy_credentials()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        return (
            stdout.read().decode("utf-8", errors="replace")
            + stderr.read().decode("utf-8", errors="replace")
        )
    finally:
        client.close()


def mask_env(text: str) -> str:
    text = re.sub(r"(TELEGRAM_TOKEN=).*", r"\1***", text)
    text = re.sub(r"(BINANCE_API_SECRET=).*", r"\1***", text)
    text = re.sub(r"(MT5_PASSWORD=).*", r"\1***", text)
    return text


def main() -> int:
    print("=== 1) Contabo container ===")
    print(ssh('docker ps -a --filter name=goldenshield-bot --format "{{.Names}} | {{.Status}}"'))

    print("=== 2) Contabo .env (Telegram/execution) ===")
    print(
        mask_env(
            ssh(
                "grep -E 'TELEGRAM_|EXECUTION_|AUTO_ENTRY|MANUAL|ENV=' /opt/goldenshield/.env || true"
            )
        )
    )

    print("=== 3) Health check ===")
    print(ssh("docker exec goldenshield-bot python deployment/health_check.py || true"))

    print("=== 4) Recent bot logs (signal-related) ===")
    logs = ssh("docker logs --tail 200 goldenshield-bot 2>&1 || true")
    Path(ROOT / "storage" / "contabo_bot_tail.log").write_text(logs, encoding="utf-8")
    keywords = (
        "BUY",
        "إشارة",
        "تنفيذ",
        "رفض",
        "مؤهلة",
        "Pre-Flight",
        "خطأ",
        "ERROR",
        "Traceback",
        "Telegram",
        "ارسال",
        "صفقة",
        "KILL",
        "paused",
        "موقوف",
    )
    hits = [ln for ln in logs.splitlines() if any(k.lower() in ln.lower() for k in keywords)]
    for ln in hits[-40:]:
        print(ln)
    if not hits:
        print("(لا أسطر مطابقة للكلمات — عرض آخر 25 سطر)")
        for ln in logs.splitlines()[-25:]:
            print(ln)

    print("=== 5) Telegram getMe ===")
    if not TOKEN:
        print("TELEGRAM_TOKEN مفقود محلياً")
        return 1
    me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=30).json()
    print(json.dumps({k: me.get(k) for k in ("ok", "result")}, ensure_ascii=False)[:500])

    print("=== 6) Test send to personal chat ===")
    if not CHAT:
        print("TELEGRAM_CHAT_ID فارغ محلياً — تخطي اختبار الإرسال")
    else:
        # لا نوقف Contabo أولاً إن كان chat فارغاً هناك؛ الاختبار محلي فقط
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT,
                "text": "🧪 فحص GoldenShield: هل يصل الإشعار؟ (اختبار اتصال — تجاهل)",
            },
            timeout=30,
        ).json()
        print("send ok=", r.get("ok"), "desc=", r.get("description", "ok"))

    print("=== 7) Note ===")
    print(
        "إذا TELEGRAM_CHAT_ID فارغ على Contabo فالورق لا يرسل إشارات لمحادثتك "
        "(هذا مقصود لكتم الاختلاط). الإشارات الحية يجب أن تأتي من Windows MT5."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
