"""إيقاف بوت Contabo مؤقتاً، قراءة آخر رسائل تيليجرام، ثم إعادة التشغيل."""

from __future__ import annotations

import os
import sys
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
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return out + err
    finally:
        client.close()


def main() -> int:
    if not TOKEN:
        print("Missing TELEGRAM_TOKEN")
        return 1

    print("stop container...")
    print(ssh_run("docker stop goldenshield-bot || true"))

    # drop webhook if any, then fetch updates
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=20)
    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"limit": 100, "timeout": 0},
        timeout=60,
    )
    data = r.json()
    if not data.get("ok"):
        print("getUpdates fail", data)
        ssh_run("docker start goldenshield-bot || true")
        return 1

    updates = data.get("result") or []
    print("updates", len(updates))
    found = 0
    for u in updates:
        msg = u.get("message") or u.get("edited_message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        if chat_id != CHAT:
            continue
        text = msg.get("text") or msg.get("caption") or ""
        if text:
            print("TEXT:", text[:2000])
            (OUT / f"msg_{msg.get('message_id')}.txt").write_text(text, encoding="utf-8")
            found += 1
        photos = msg.get("photo") or []
        if photos:
            file_id = photos[-1]["file_id"]
            fr = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getFile",
                params={"file_id": file_id},
                timeout=30,
            ).json()
            path = ((fr.get("result") or {}).get("file_path"))
            if path:
                content = requests.get(
                    f"https://api.telegram.org/file/bot{TOKEN}/{path}",
                    timeout=60,
                ).content
                dest = OUT / f"photo_{msg.get('message_id')}.jpg"
                dest.write_bytes(content)
                print("PHOTO_SAVED", dest, "bytes", len(content))
                found += 1
        doc = msg.get("document")
        if doc:
            print("DOC", doc.get("file_name"), doc.get("mime_type"))
            found += 1

    print("FOUND", found)
    # acknowledge updates so they don't flood forever
    if updates:
        last = updates[-1]["update_id"]
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": last + 1, "timeout": 0},
            timeout=30,
        )

    print("start container...")
    print(ssh_run("docker start goldenshield-bot || true"))
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
