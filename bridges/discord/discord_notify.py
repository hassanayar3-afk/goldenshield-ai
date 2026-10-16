
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Discord notify with .env + discord_bridge.json fallback (unified stack)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance"))
RUNTIME = ROOT / "storage" / "runtime"
CFG_FILE = RUNTIME / "discord_bridge.json"
ENV_FILE = ROOT / ".env"
_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    if not ENV_FILE.exists():
        return
    try:
        for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as exc:
        print(f"[discord] dotenv load fail: {exc}", flush=True)


def _env(name: str, default: str = "") -> str:
    _load_dotenv()
    return (os.getenv(name) or default).strip()


def load_cfg() -> dict[str, Any]:
    _load_dotenv()
    cfg = {
        "webhook_url": _env("DISCORD_WEBHOOK_URL"),
        "bot_token": _env("DISCORD_BOT_TOKEN"),
        "channel_id": _env("DISCORD_CHANNEL_ID"),
        "username": _env("DISCORD_BOT_USERNAME", "GoldenShield"),
        "enabled": True,
    }
    if CFG_FILE.exists():
        try:
            disk = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            if isinstance(disk, dict):
                for k, v in disk.items():
                    if v is None or v == "":
                        continue
                    if k == "enabled":
                        cfg["enabled"] = bool(v) if not isinstance(v, str) else v.lower() not in {"0", "false", "no", "off"}
                        continue
                    if not cfg.get(k):
                        cfg[k] = str(v).strip()
        except Exception:
            pass
    return cfg


def discord_enabled() -> bool:
    if _env("DISCORD_NOTIFY_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        return False
    cfg = load_cfg()
    if cfg.get("enabled") is False:
        return False
    return bool(cfg.get("webhook_url") or (cfg.get("bot_token") and cfg.get("channel_id")))


def send_discord(content: str, *, embeds: list[dict] | None = None) -> bool:
    """Send message to Discord (Webhook first, then Bot API)."""
    if not content and not embeds:
        return False
    cfg = load_cfg()
    content = (content or "")[:1900]
    wh = cfg.get("webhook_url") or ""
    if wh.startswith("https://discord.com/api/webhooks/") or wh.startswith("https://discordapp.com/api/webhooks/"):
        payload = {"username": cfg.get("username") or "GoldenShield", "content": content or None}
        if embeds:
            payload["embeds"] = embeds[:10]
        return _post_json(wh, payload)
    token = cfg.get("bot_token") or ""
    channel = cfg.get("channel_id") or ""
    if token and channel:
        url = f"https://discord.com/api/v10/channels/{channel}/messages"
        payload = {"content": content or None}
        if embeds:
            payload["embeds"] = embeds[:10]
        return _post_json(url, payload, headers={"Authorization": f"Bot {token}"})
    return False


def _post_json(url: str, payload: dict, headers: dict | None = None) -> bool:
    body = json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "GoldenShieldBot/1.0 (+discord-bridge)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= int(resp.status) < 300
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            err = str(e)
        print(f"[discord] HTTP {e.code}: {err}", flush=True)
        return False
    except Exception as e:
        print(f"[discord] fail: {e}", flush=True)
        return False


def push_discord_alert(kind: str, title: str, body: str, *, level: str = "info") -> bool:
    if not discord_enabled():
        return False
    color = {
        "info": 0x3B82F6,
        "ok": 0x22C55E,
        "warn": 0xF59E0B,
        "warning": 0xF59E0B,
        "trade": 0xA855F7,
        "emergency": 0xEF4444,
        "kill": 0xEF4444,
    }.get(level, 0x64748B)
    embed = {
        "title": title[:240],
        "description": (body or "")[:1800],
        "color": color,
        "footer": {"text": f"GoldenShield · {kind}"},
    }
    return send_discord("", embeds=[embed])
