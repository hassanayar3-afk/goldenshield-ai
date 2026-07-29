"""إيقاف Contabo مؤقتاً ثم انتظار رسالة واحدة من المستخدم على تيليجرام."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = str(os.getenv("TELEGRAM_CHAT_ID") or "")
OUT = ROOT / "storage" / "telegram_inbox"
OUT.mkdir(parents=True, exist_ok=True)


def ssh_run(cmd: str) -> str:
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
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        return stdout.read().decode("utf-8", errors="replace") + stderr.read().decode(
            "utf-8", errors="replace"
        )
    finally:
        client.close()


def main() -> int:
    print(ssh_run("docker stop goldenshield-bot || true"))
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=20)
    # clear backlog
    r0 = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"timeout": 0, "limit": 100}, timeout=30).json()
    updates = r0.get("result") or []
    if updates:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": updates[-1]["update_id"] + 1, "timeout": 0},
            timeout=30,
        )

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT,
            "text": (
                "أرسل السكرين مرة ثانية الآن خلال دقيقتين.\n"
                "البوت متوقف مؤقتاً لأتمكن من قراءة الصورة."
            ),
        },
        timeout=20,
    )
    print("WAITING_FOR_USER")

    deadline = time.time() + 120
    saved = None
    while time.time() < deadline:
        r = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"timeout": 25, "limit": 50},
            timeout=40,
        ).json()
        batch = r.get("result") or []
        for u in batch:
            msg = u.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != CHAT:
                continue
            if msg.get("text"):
                p = OUT / f"msg_{msg.get('message_id')}.txt"
                p.write_text(msg["text"], encoding="utf-8")
                print("TEXT_SAVED", p)
                saved = str(p)
            photos = msg.get("photo") or []
            if photos:
                file_id = photos[-1]["file_id"]
                fr = requests.get(
                    f"https://api.telegram.org/bot{TOKEN}/getFile",
                    params={"file_id": file_id},
                    timeout=30,
                ).json()
                path = (fr.get("result") or {}).get("file_path")
                if path:
                    content = requests.get(
                        f"https://api.telegram.org/file/bot{TOKEN}/{path}",
                        timeout=60,
                    ).content
                    dest = OUT / f"photo_{msg.get('message_id')}.jpg"
                    dest.write_bytes(content)
                    print("PHOTO_SAVED", dest, len(content))
                    saved = str(dest)
            if saved:
                requests.get(
                    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                    params={"offset": u["update_id"] + 1, "timeout": 0},
                    timeout=20,
                )
                break
        if saved:
            break
        if batch:
            requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": batch[-1]["update_id"] + 1, "timeout": 0},
                timeout=20,
            )

    print(ssh_run("docker start goldenshield-bot || true"))
    print("SAVED" if saved else "TIMEOUT")
    print(saved or "")
    return 0 if saved else 2


if __name__ == "__main__":
    raise SystemExit(main())
