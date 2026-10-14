#!/usr/bin/env python3
"""Named Cloudflare tunnel supervisor — bans quick trycloudflare when static URL set."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from deploy_ops.logging_config import configure_sovereign_logging

log = configure_sovereign_logging("gs_tunnel")


def _root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    return p if p.is_dir() else Path.cwd()


def _write_static_url(runtime: Path, base: str) -> None:
    url = base.rstrip("/") + "/"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mobile_tunnel_url.txt").write_text(url + "\n", encoding="utf-8")


def _cloudflared_exe(root: Path) -> Path | None:
    bundled = root / "tools" / "cloudflared.exe"
    if bundled.is_file():
        return bundled
    for name in ("cloudflared", "cloudflared.exe"):
        try:
            import shutil

            found = shutil.which(name)
            if found:
                return Path(found)
        except Exception:
            pass
    return None


def main() -> int:
    root = _root()
    os.chdir(root)
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=False)
    except Exception:
        pass

    static = (os.getenv("MOBILE_PUBLIC_BASE_URL") or "").strip()
    token = (os.getenv("CLOUDFLARE_TUNNEL_TOKEN") or "").strip()
    ban_quick = (os.getenv("GS_BAN_QUICK_TUNNEL", "true").lower() not in {"0", "false", "no"}) or bool(
        static
    )
    runtime = root / "storage" / "runtime"
    logs = root / "storage" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_file = logs / "cloudflare_tunnel.log"

    if static.startswith("http"):
        _write_static_url(runtime, static)
        log.info("TUNNEL_STATIC_OK %s", static.split("://", 1)[-1][:48])
    if not token:
        if ban_quick:
            log.warning("QUICK_TUNNEL_BANNED — set CLOUDFLARE_TUNNEL_TOKEN for cloudflared")
            return 0 if static else 2
        log.error("No CLOUDFLARE_TUNNEL_TOKEN and quick tunnel banned")
        return 2

    exe = _cloudflared_exe(root)
    if not exe:
        log.error("cloudflared not found")
        return 3

    local = (os.getenv("CLOUDFLARE_TUNNEL_LOCAL_URL") or "http://127.0.0.1:8790").strip()
    token_file = root / "storage" / "runtime" / "tunnel.token"
    try:
        token_file.write_text(token.strip(), encoding="utf-8")
    except Exception as exc:
        log.error("token file write failed: %s", exc)
        return 4
    args = [
        str(exe),
        "tunnel",
        "run",
        "--token-file",
        str(token_file),
        "--logfile",
        str(log_file),
        "--loglevel",
        "info",
    ]
    log.info("Starting named tunnel -> %s", local)
    while True:
        try:
            proc = subprocess.Popen(args, cwd=str(root))  # noqa: S603
            proc.wait()
            log.warning("cloudflared exited %s — restart in 5s", proc.returncode)
        except Exception as exc:
            log.exception("tunnel crash: %s", exc)
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
