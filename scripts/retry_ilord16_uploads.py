"""إعادة رفع النسخ التي فشلت بسبب rate limit إلى t.me/ilord16."""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_BACKUP_CHANNEL_ID")
    if not token or not chat:
        print("إعداد تيليجرام ناقص")
        return 1

    bdir = ROOT / "storage" / "db" / "backups"
    # فقط الملفات المتأخرة التي ظهرت في فشل Too Many Requests (من 213125 فما بعد تقريباً)
    failed_prefix_times = [
        "20260713_213125",
        "20260713_213533",
        "20260713_213844",
        "20260713_214115",
        "20260713_214124",
        "20260713_214417",
        "20260713_214719",
        "20260713_215050",
        "20260713_215421",
        "20260713_215746",
        "20260713_220818",
        "20260713_221241",
        "20260713_221532",
        "20260713_222014",
        "20260713_222025",
        "20260713_222835",
    ]
    paths = []
    for stamp in failed_prefix_times:
        matches = list(bdir.glob(f"*_{stamp}.db"))
        paths.extend(matches)

    print(f"إعادة رفع {len(paths)} ملف مع تأخير...")
    time.sleep(30)
    ok = 0
    for path in paths:
        for attempt in range(4):
            with path.open("rb") as fh:
                rr = requests.post(
                    f"https://api.telegram.org/bot{token}/sendDocument",
                    data={
                        "chat_id": chat,
                        "caption": f"📦 نسخة سابقة\n<code>{path.name}</code>",
                        "parse_mode": "HTML",
                    },
                    files={"document": (path.name, fh)},
                    timeout=60,
                )
            data = rr.json()
            if data.get("ok"):
                print("ok:", path.name)
                ok += 1
                time.sleep(1.5)
                break
            desc = str(data.get("description", ""))
            wait = 30
            if "retry after" in desc.lower():
                try:
                    wait = int(desc.rsplit(" ", 1)[-1]) + 2
                except ValueError:
                    wait = 30
            print("retry", path.name, desc, f"sleep {wait}s")
            time.sleep(wait)
        else:
            print("FAILED:", path.name)
    print(f"done {ok}/{len(paths)}")
    return 0 if ok == len(paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
