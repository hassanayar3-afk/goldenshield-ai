#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configure Discord webhook/bot on VPS (same role as old Telegram outbound)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\GoldenShield_Binance")
RUNTIME = ROOT / "storage" / "runtime"
CFG = RUNTIME / "discord_bridge.json"
ENV = ROOT / ".env"


def upsert_env(updates: dict[str, str]) -> None:
    text = ENV.read_text(encoding="utf-8", errors="replace") if ENV.exists() else ""
    for k, v in updates.items():
        os.environ[k] = v
        pat = re.compile(rf"^(?:export\s+)?{re.escape(k)}=.*$", re.M)
        if pat.search(text):
            text = pat.sub(f"{k}={v}", text, count=1)
        else:
            text = text.rstrip() + f"\n{k}={v}\n"
    ENV.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webhook", default=os.getenv("DISCORD_WEBHOOK_URL", ""))
    ap.add_argument("--bot-token", default=os.getenv("DISCORD_BOT_TOKEN", ""))
    ap.add_argument("--channel-id", default=os.getenv("DISCORD_CHANNEL_ID", ""))
    ap.add_argument("--username", default=os.getenv("DISCORD_BOT_USERNAME", "GoldenShield"))
    args = ap.parse_args()

    webhook = (args.webhook or "").strip()
    bot_token = (args.bot_token or "").strip()
    channel_id = (args.channel_id or "").strip()
    username = (args.username or "GoldenShield").strip()

    if not webhook and not (bot_token and channel_id):
        print("USAGE: configure_discord.py --webhook URL")
        print("   or: configure_discord.py --bot-token TOKEN --channel-id ID")
        return 2

    if webhook and not (
        webhook.startswith("https://discord.com/api/webhooks/")
        or webhook.startswith("https://discordapp.com/api/webhooks/")
    ):
        print("ERROR: invalid webhook url")
        return 2

    RUNTIME.mkdir(parents=True, exist_ok=True)
    cfg = {
        "webhook_url": webhook,
        "bot_token": bot_token,
        "channel_id": channel_id,
        "username": username,
    }
    CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    upsert_env(
        {
            "DISCORD_NOTIFY_ENABLED": "true",
            "DISCORD_BOT_USERNAME": username,
            "DISCORD_WEBHOOK_URL": webhook,
            "DISCORD_BOT_TOKEN": bot_token,
            "DISCORD_CHANNEL_ID": channel_id,
            "MOBILE_NOTIFY_ONLY": "true",
            "TELEGRAM_MUTE_ALL": "true",
            "TELEGRAM_OUTBOUND_DISABLED": "true",
        }
    )
    print("SAVED", CFG)

    # restart bridge process lightly
    bridge = ROOT / "bridges" / "discord" / "discord_bridge.py"
    if bridge.exists():
        subprocess.Popen(
            [sys.executable, "-u", str(bridge)],
            cwd=str(ROOT),
            creationflags=0x00000008 | 0x00000200 | 0x08000000,
        )
        print("STARTED discord_bridge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
