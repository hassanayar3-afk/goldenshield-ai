#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoldenShield Discord Bridge — بث إشارات/تنبيهات مثل تيليجرام السابق.

يراقب:
- storage/runtime/mobile_alerts.json
- storage/runtime/last_cycle_signals.json
- storage/runtime/gs_runtime_status.json / heartbeat

ويرسل إلى Discord عبر Webhook أو Bot Token.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\GoldenShield_Binance")
RUNTIME = ROOT / "storage" / "runtime"
LOGS = ROOT / "storage" / "logs"
STATE_FILE = RUNTIME / "discord_bridge_state.json"
LOG_FILE = LOGS / "discord_bridge.log"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from discord_notify import discord_enabled, load_cfg, push_discord_alert, send_discord  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8", errors="replace") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_alert_id": "", "last_signal_fp": "", "boot_sent": False}


def save_state(st: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    return default


def tunnel_url() -> str:
    p = RUNTIME / "mobile_tunnel_url.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def process_alerts(st: dict) -> None:
    raw = read_json(RUNTIME / "mobile_alerts.json", [])
    # support {"alerts": [...]} or bare list
    if isinstance(raw, dict):
        items = raw.get("alerts") or []
    else:
        items = raw if isinstance(raw, list) else []
    if not items:
        return
    last = st.get("last_alert_id") or ""
    # send only new ones after last id
    new_items = []
    seen = False if last else True
    for a in items:
        aid = str(a.get("id") or "")
        if not seen:
            if aid == last:
                seen = True
            continue
        new_items.append(a)
    if not last and items:
        # on first run, only send last 3 to avoid flood
        new_items = items[-3:]
    for a in new_items[-20:]:
        title = str(a.get("title") or a.get("kind") or "تنبيه")
        body = str(a.get("body") or "")
        level = str(a.get("level") or "info")
        kind = str(a.get("kind") or "alert")
        ok = push_discord_alert(kind, title, body, level=level)
        log(f"alert id={a.get('id')} ok={ok} title={title[:60]}")
        st["last_alert_id"] = str(a.get("id") or st.get("last_alert_id") or "")
    save_state(st)


def process_signals(st: dict) -> None:
    data = read_json(RUNTIME / "last_cycle_signals.json", {})
    signals = data.get("signals") if isinstance(data, dict) else None
    if not isinstance(signals, list) or not signals:
        return
    notify_min = int(os.getenv("TELEGRAM_SIGNAL_MIN_PERCENT", "70") or 70)
    # score 7 = 70%, 8 = 80%
    notable = []
    for s in signals:
        score = float(s.get("score") or 0)
        pct = int(round(score * 10)) if score <= 10 else int(score)
        sig = str(s.get("signal") or "WAIT").upper()
        if pct >= notify_min or sig in {"BUY", "SELL", "BUY SIGNAL", "SELL SIGNAL"}:
            notable.append((pct, s))
    notable.sort(key=lambda x: -x[0])
    if not notable:
        return
    top = notable[:5]
    fp = "|".join(f"{x[1].get('sym')}:{x[1].get('score')}:{x[1].get('signal')}" for x in top)
    if fp == st.get("last_signal_fp"):
        return
    lines = ["📡 إشارات GoldenShield (مثل تيليجرام)"]
    for pct, s in top:
        lines.append(
            f"• {s.get('sym')} · {s.get('score')}/10 ({pct}%) · {s.get('signal')} · {s.get('price')}"
        )
    auto = [x for x in top if x[0] >= 80 and str(x[1].get("signal")).upper() in {"BUY", "SELL", "BUY SIGNAL", "SELL SIGNAL"}]
    if auto:
        lines.append("⚡ مرشّح دخول تلقائي ≥80")
    tun = tunnel_url()
    if tun:
        lines.append(f"🔗 التطبيق: {tun}")
    ok = send_discord("\n".join(lines))
    log(f"signals ok={ok} n={len(top)}")
    st["last_signal_fp"] = fp
    save_state(st)


def boot_message(st: dict) -> None:
    if st.get("boot_sent"):
        return
    cfg = load_cfg()
    mode = "webhook" if cfg.get("webhook_url") else ("bot" if cfg.get("bot_token") else "unconfigured")
    tun = tunnel_url() or "(tunnel pending)"
    text = (
        "✅ GoldenShield Discord Bridge متصل\n"
        f"وضع: {mode}\n"
        f"القواعد: إشعار≥70 · تلقائي≥80 · GS-GOLD80 · Demo\n"
        f"التطبيق/النفق: {tun}\n"
        "البث يعمل كما كان على تيليجرام (إشارات + تنبيهات + صفقات)."
    )
    ok = send_discord(text) if discord_enabled() else False
    log(f"boot_message ok={ok} enabled={discord_enabled()} mode={mode}")
    st["boot_sent"] = True
    save_state(st)


def main() -> int:
    os.chdir(ROOT)
    interval = int(os.getenv("DISCORD_BRIDGE_INTERVAL_SEC", "20") or 20)
    log(f"DISCORD_BRIDGE_START interval={interval}s enabled={discord_enabled()}")
    st = load_state()
    boot_message(st)
    while True:
        try:
            if not discord_enabled():
                log("waiting for DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN+DISCORD_CHANNEL_ID")
                time.sleep(max(30, interval))
                continue
            process_alerts(st)
            process_signals(st)
        except Exception as e:
            log(f"loop_error {e}")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
