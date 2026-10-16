#!/usr/bin/env python3
"""Verify Discord sovereign migration — health, no Telegram modules, Discord bot process."""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance")).resolve()


def check_health() -> tuple[bool, str]:
    url = os.getenv("GS_MOBILE_HEALTH_URL", "http://127.0.0.1:8790/api/health")
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok = resp.status == 200
            if ok:
                import json

                try:
                    ok = bool(json.loads(body).get("ok"))
                except Exception:
                    ok = '"ok":true' in body.replace(" ", "").lower()
            return ok, f"HTTP {resp.status} {body[:200]}"
    except Exception as exc:
        return False, str(exc)


def scan_telegram_residual() -> list[str]:
    hits: list[str] = []
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    patterns = (
        re.compile(r"\btelebot\b", re.I),
        re.compile(r"python-telegram-bot", re.I),
        re.compile(r"from operations\.telegram_", re.I),
        re.compile(r"import operations\.telegram_", re.I),
        re.compile(r"TelegramCommandHandler", re.I),
    )
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".ps1", ".cmd", ".bat", ".txt", ".md", ".yml", ".yaml"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("scripts/") or rel.startswith("docs/") or rel.startswith("tests/"):
            continue
        if rel.startswith("storage/runtime/"):
            continue
        if rel == "deploy_ops/verify_discord_sovereign.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pat in patterns:
            if pat.search(text):
                hits.append(f"{rel}: {pat.pattern}")
                break
    return hits


def discord_bot_running() -> bool:
    if os.name != "nt":
        return bool(os.getenv("DISCORD_BOT_TOKEN"))
    try:
        import subprocess

        ps = (
            "(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object { $_.CommandLine -match 'gs_discord_bot\\.py' }).Count"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return int((r.stdout or "0").strip() or "0") >= 1
    except Exception:
        return False


def main() -> int:
    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path, override=True)
        except Exception:
            pass
    print(f"ROOT={ROOT}")
    health_ok, health_detail = check_health()
    print(f"HEALTH_OK={health_ok} detail={health_detail}")
    tg_hits = scan_telegram_residual()
    print(f"TELEGRAM_RESIDUAL_COUNT={len(tg_hits)}")
    for line in tg_hits[:30]:
        print(f"  {line}")
    bot_run = discord_bot_running()
    token_set = bool((os.getenv("DISCORD_BOT_TOKEN") or "").strip())
    print(f"DISCORD_BOT_TOKEN_SET={token_set}")
    print(f"DISCORD_BOT_PROCESS={bot_run}")
    if health_ok and not tg_hits and (bot_run or not token_set):
        print("VERIFY_PASS")
        return 0
    print("VERIFY_FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
