from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from terminal_app.config import (
    ALERTS_FILE,
    DB,
    DEVICES_FILE,
    MASTER_TOKEN,
    PAIR_CODE,
    PANEL_ROOT,
    ROOT,
    RUNTIME,
    STRATEGY_CODE,
)

from terminal_app.services import alerts_queue as aq
from terminal_app.services import binance_mirror as bm

_SIGNAL_LINE_RE = re.compile(
    r"(?:✅|\*)\s*([A-Z0-9]+/[A-Z0-9]+)\s*\|\s*(?:price|السعر):\s*([0-9.]+)\s*\|\s*"
    r"(?:score|الدرجة):\s*(\d+(?:\.\d+)?)/10\s*\|\s*(?:الحالة:\s*)?([A-Z_ ]+|WAIT|REJECTED)",
    re.IGNORECASE,
)
_last_score_bucket: dict[str, int] = {}
def positions() -> list:
    """مصدر الحقيقة: أرصدة Binance غير المستقرة + إثراء بيانات البوت إن وُجدت."""
    snap = bm.binance_snapshot()
    db_rows = [p for p in db_open_trades() if p and "error" not in p]
    db_by_sym = {(p.get("sym") or "").upper(): p for p in db_rows}

    if snap.get("ok"):
        out = []
        for h in snap.get("holdings") or []:
            sym = (h.get("sym") or "").upper()
            if not sym:
                continue
            row = {
                "id": None,
                "sym": sym,
                "side": "BUY",
                "entry": float(h.get("entry") or h.get("price") or 0),
                "price": float(h.get("price") or 0),
                "qty": float(h.get("qty") or 0),
                "pnl": float(h.get("pnl") or 0),
                "usdt": float(h.get("usdt") or 0),
                "sl": None,
                "tp": None,
                "score": 0,
                "exitTier": 0,
                "risk_mode": None,
                "breakeven": False,
                "opened_at": None,
                "source": "binance",
                "asset": h.get("asset"),
                "dust": bool(h.get("dust")),
                "sellable": float(h.get("sellable") or 0),
            }
            meta = db_by_sym.get(sym)
            if meta:
                for key in (
                    "id",
                    "sl",
                    "tp",
                    "score",
                    "exitTier",
                    "risk_mode",
                    "breakeven",
                    "opened_at",
                    "side",
                ):
                    if meta.get(key) is not None:
                        row[key] = meta[key]
                row["linked_bot"] = True
            out.append(row)
        return out

    # إن فشلت المنصة: رجوع لقاعدة البوت فقط
    return db_rows
def status() -> dict:
    risk = risk_state()
    paused = (RUNTIME / "user_stopped.flag").exists()
    bot_running = False
    try:
        # ملف نبض حديث؟
        heartbeat = RUNTIME / "heartbeat.json"
        if heartbeat.exists():
            age = time.time() - heartbeat.stat().st_mtime
            bot_running = age < 30
        else:
            log = ROOT / "storage" / "logs" / "bot_stdout.log"
            if log.exists():
                bot_running = (time.time() - log.stat().st_mtime) < 20
    except Exception:
        pass

    snap = bm.binance_snapshot()
    positions = [p for p in positions() if p and "error" not in p]
    if snap.get("ok") and snap.get("equity") is not None:
        bal = float(snap["equity"])
        session_start = float(snap.get("session_start_equity") or bal)
        session_pnl = float(snap.get("session_pnl") or (bal - session_start))
        unrealized = float(snap.get("unrealized_pnl") or 0)
        free_cash = float(snap.get("free_cash") or 0)
        balance_source = "binance"
        exchange_ok = True
        assets = snap.get("assets") or []
        demo = bool(snap.get("demo"))
    else:
        bal = float(risk.get("current_balance") or risk.get("session_start_balance") or 0)
        session_start = float(risk.get("session_start_balance") or bal)
        session_pnl = bal - session_start
        unrealized = sum(float(p.get("pnl") or 0) for p in positions)
        free_cash = bal
        balance_source = "risk_state"
        exchange_ok = False
        assets = []
        demo = str(os.getenv("BINANCE_DEMO_TRADING", "")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    tradeable = [p for p in positions if not p.get("dust")]
    dust_n = len(positions) - len(tradeable)
    win_open = sum(float(p.get("pnl") or 0) for p in tradeable if float(p.get("pnl") or 0) >= 0)
    lose_open = sum(float(p.get("pnl") or 0) for p in tradeable if float(p.get("pnl") or 0) < 0)

    daily_profit = float(risk.get("daily_profit") or 0)
    daily_loss = float(risk.get("daily_loss") or 0)
    # Realized calendar-day net (closed trades) — not session equity delta
    daily_net = daily_profit + daily_loss
    day_base = session_start if session_start else (bal if bal else 0.0)
    daily_net_pct = (daily_net / day_base * 100.0) if day_base else 0.0

    return {
        "bot_running": bot_running,
        "paused": paused,
        "balance": round(bal, 8),
        "session_start_balance": round(session_start, 8),
        "session_pnl": round(session_pnl, 8),
        "unrealized_pnl": round(unrealized, 8),
        "free_cash": round(free_cash, 8),
        "win_open": round(win_open, 8),
        "lose_open": round(lose_open, 8),
        "daily_trades": int(risk.get("daily_trades") or 0),
        "daily_profit": round(daily_profit, 8),
        "daily_loss": round(daily_loss, 8),
        "daily_net": round(daily_net, 8),
        "daily_net_pct": round(daily_net_pct, 4),
        "kill_switch": bool(risk.get("kill_switch_active")),
        "open_positions": len(tradeable),
        "dust_positions": dust_n if exchange_ok else int(snap.get("dust_positions") or 0) if isinstance(snap, dict) else 0,
        "assets": assets,
        "balance_source": balance_source,
        "exchange_ok": exchange_ok,
        "demo": demo,
        "exchange_error": None if exchange_ok else (snap.get("error") if isinstance(snap, dict) else None),
        "ts": aq.utc(),
        "pair_code_hint": PAIR_CODE[:3] + "***",
        "strategy_code": STRATEGY_CODE,
        "trading_enabled": True,
    }
def score_bucket(score: int) -> int:
    """0 | 70 | 80 buckets for alert escalation."""
    if score >= 8:
        return 80
    if score >= 7:
        return 70
    return 0
def maybe_alert_signal(row: dict) -> None:
    sym = row["sym"]
    score = int(row["score"])
    bucket = score_bucket(score)
    prev = _last_score_bucket.get(sym, 0)
    if bucket <= prev:
        if bucket == 0 and prev:
            _last_score_bucket[sym] = 0
        return
    _last_score_bucket[sym] = bucket
    pct = score * 10
    status = row.get("signal") or "WAIT"
    if bucket >= 80:
        title = "⚡ إشارة دخول تلقائي" if status in {"BUY SIGNAL", "SELL SIGNAL"} else "📡 قوة ≥80"
        aq.push_alert(
            "auto_signal",
            title,
            f"{sym} · {pct}/100 · {status} · تلقائي من 80",
            level="trade" if status in {"BUY SIGNAL", "SELL SIGNAL"} else "signal",
            meta={"sym": sym, "score": score, "pct": pct},
        )
    else:
        aq.push_alert(
            "signal",
            "📡 إشارة قوية",
            f"{sym} · {pct}/100 · {status}",
            level="signal",
            meta={"sym": sym, "score": score, "pct": pct},
        )
def discord_cfg_public() -> dict:
    cfg_path = RUNTIME / "discord_bridge.json"
    disk = aq.load_json(cfg_path, {})
    if not isinstance(disk, dict):
        disk = {}
    wh = (os.getenv("DISCORD_WEBHOOK_URL") or disk.get("webhook_url") or "").strip()
    token = (os.getenv("DISCORD_BOT_TOKEN") or disk.get("bot_token") or "").strip()
    channel = (os.getenv("DISCORD_CHANNEL_ID") or disk.get("channel_id") or "").strip()
    enabled_env = os.getenv("DISCORD_NOTIFY_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
    mode = "webhook" if wh else ("bot" if (token and channel) else "unconfigured")
    return {
        "enabled_env": enabled_env,
        "configured": bool(wh or (token and channel)),
        "mode": mode,
        "username": os.getenv("DISCORD_BOT_USERNAME") or disk.get("username") or "GoldenShield",
        "has_webhook": bool(wh),
        "has_bot_token": bool(token),
        "has_channel_id": bool(channel),
        "tip": "ضع Webhook أو Bot Token + Channel ID لبث الإشارات مثل تيليجرام",
    }
def rules_payload() -> dict:
    try:
        from config.settings import get_settings
        from core.constants import (
            CONFIRMED_SUCCESS_MIN_PERCENT,
            SIGNAL_AUTO_PERCENT,
            SIGNAL_MIN_PERCENT,
            STRENGTH_LADDER,
        )
        from config.project_rules import load_project_rules

        st = get_settings()
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()
        rules = load_project_rules()
        return {
            "strength_ladder": list(STRENGTH_LADDER),
            "notify_min": int(SIGNAL_MIN_PERCENT),
            "auto_min": int(getattr(st, "auto_entry_min_percent", SIGNAL_AUTO_PERCENT) or 80),
            "manual_max": 75,
            "confirmed_min": int(CONFIRMED_SUCCESS_MIN_PERCENT),
            "daily_trade_cap": int(getattr(st, "max_daily_trades", 10) or 10),
            "manual_entry_required": bool(getattr(st, "manual_entry_required", False)),
            "progressive_sequential_tp": os.getenv("PROGRESSIVE_SEQUENTIAL_TP", "true").lower()
            in {"1", "true", "yes", "on"},
            "targets": 3,
            "hybrid_auto_min_score": int(rules.hybrid_auto_min_score),
            "display_min": 70,
            "liquidity_high": 75,
            "bot_force_active": True,
        }
    except Exception as exc:
        return {
            "strength_ladder": [70, 75, 80, 85, 90, 95, 100],
            "notify_min": 70,
            "auto_min": 80,
            "manual_max": 75,
            "confirmed_min": 90,
            "daily_trade_cap": 10,
            "manual_entry_required": False,
            "progressive_sequential_tp": True,
            "targets": 3,
            "display_min": 70,
            "error": str(exc),
        }
def mark_trade_closed(trade_id: str, exit_price: float, pnl: float) -> None:
    try:
        conn = db()
        conn.execute(
            """
            UPDATE trades
            SET status='closed', exit_price=?, pnl=?, closed_at=?
            WHERE id=? AND (status='open' OR closed_at IS NULL)
            """,
            (exit_price, pnl, aq.utc(), trade_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
def history(limit: int = 100) -> list:
    """كل الصفقات المغلقة من 2026-10-04 فصاعداً (رابحة وخاسرة ومتعادلة)."""
    out = []
    keep_from = "2026-10-04"
    try:
        conn = db()
        rows = conn.execute(
            """
            SELECT id, symbol, side, entry_price, exit_price, amount, pnl,
                   status, closed_at, signal_score, exit_tier
            FROM trades
            WHERE (status='closed'
               OR (closed_at IS NOT NULL AND LOWER(COALESCE(status,'')) NOT IN ('open','')))
              AND date(substr(COALESCE(closed_at,''), 1, 10)) >= date(?)
            ORDER BY closed_at DESC
            LIMIT ?
            """,
            (keep_from, limit),
        ).fetchall()
        conn.close()
        for r in rows:
            pnl = float(r["pnl"] or 0)
            if pnl > 0:
                result = "win"
            elif pnl < 0:
                result = "loss"
            else:
                result = "flat"
            closed = r["closed_at"] or ""
            # تاريخ + وقت مختصر
            at = closed[5:16].replace("T", " ") if len(closed) >= 16 else closed[11:16]
            out.append(
                {
                    "id": r["id"],
                    "sym": r["symbol"],
                    "side": (r["side"] or "buy").upper(),
                    "entry": float(r["entry_price"] or 0),
                    "exit": float(r["exit_price"] or 0) if r["exit_price"] is not None else None,
                    "qty": float(r["amount"] or 0),
                    "pnl": pnl,
                    "at": at,
                    "closed_at": closed,
                    "win": pnl > 0,
                    "result": result,
                    "score": int(r["signal_score"] or 0),
                    "exitTier": int(r["exit_tier"] or 0),
                    "status": r["status"],
                }
            )
    except Exception as exc:
        out.append({"error": str(exc)})
    return out
def db_open_trades() -> list:
    """صفقات البوت المفتوحة من SQLite (للدمج مع مرآة المنصة)."""
    out = []
    try:
        conn = db()
        rows = conn.execute(
            """
            SELECT id, symbol, side, entry_price, amount, stop_loss, take_profit,
                   signal_score, exit_tier, risk_mode, breakeven_applied, status, opened_at
            FROM trades
            WHERE status='open' OR (exit_price IS NULL AND closed_at IS NULL)
            ORDER BY opened_at DESC
            """
        ).fetchall()
        conn.close()
        syms = list({(r["symbol"] or "").upper() for r in rows if r["symbol"]})
        live = bm.live_prices(syms)
        for r in rows:
            entry = float(r["entry_price"] or 0)
            sym = (r["symbol"] or "").upper()
            side = (r["side"] or "buy").upper()
            qty = float(r["amount"] or 0)
            price = float(live.get(sym) or entry)
            if side == "BUY":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty
            out.append(
                {
                    "id": r["id"],
                    "sym": sym,
                    "side": side,
                    "entry": entry,
                    "price": price,
                    "qty": qty,
                    "pnl": round(pnl, 6),
                    "sl": r["stop_loss"],
                    "tp": r["take_profit"],
                    "score": int(r["signal_score"] or 0),
                    "exitTier": int(r["exit_tier"] or 0),
                    "risk_mode": r["risk_mode"],
                    "breakeven": bool(r["breakeven_applied"]),
                    "opened_at": r["opened_at"],
                    "source": "bot_db",
                }
            )
    except Exception as exc:
        out.append({"error": str(exc)})
    return out
def save_discord_config(body: dict) -> dict:
    cfg_path = RUNTIME / "discord_bridge.json"
    cur = aq.load_json(cfg_path, {})
    if not isinstance(cur, dict):
        cur = {}
    webhook = str(body.get("webhook_url") or body.get("DISCORD_WEBHOOK_URL") or "").strip()
    bot_token = str(body.get("bot_token") or body.get("DISCORD_BOT_TOKEN") or "").strip()
    channel_id = str(body.get("channel_id") or body.get("DISCORD_CHANNEL_ID") or "").strip()
    username = str(body.get("username") or body.get("DISCORD_BOT_USERNAME") or cur.get("username") or "GoldenShield").strip()
    if webhook:
        if not (
            webhook.startswith("https://discord.com/api/webhooks/")
            or webhook.startswith("https://discordapp.com/api/webhooks/")
        ):
            return {"ok": False, "error": "webhook_url غير صالح"}
        cur["webhook_url"] = webhook
    if bot_token:
        cur["bot_token"] = bot_token
    if channel_id:
        cur["channel_id"] = channel_id
    if username:
        cur["username"] = username
    if not cur.get("webhook_url") and not (cur.get("bot_token") and cur.get("channel_id")):
        return {"ok": False, "error": "يلزم webhook_url أو bot_token+channel_id"}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    # أفضل جهد: حدّث .env دون مسح قيم أخرى
    try:
        env_path = ROOT / ".env"
        text = env_path.read_text(encoding="utf-8", errors="replace") if env_path.exists() else ""
        updates = {
            "DISCORD_NOTIFY_ENABLED": "true",
            "DISCORD_BOT_USERNAME": username,
            "MOBILE_NOTIFY_ONLY": "true",
            "TELEGRAM_MUTE_ALL": "true",
            "TELEGRAM_OUTBOUND_DISABLED": "true",
        }
        if cur.get("webhook_url"):
            updates["DISCORD_WEBHOOK_URL"] = cur["webhook_url"]
        if cur.get("bot_token"):
            updates["DISCORD_BOT_TOKEN"] = cur["bot_token"]
        if cur.get("channel_id"):
            updates["DISCORD_CHANNEL_ID"] = cur["channel_id"]
        for k, v in updates.items():
            os.environ[k] = v
            import re as _re

            pat = _re.compile(rf"^(?:export\s+)?{ _re.escape(k) }=.*$", _re.M)
            if pat.search(text):
                text = pat.sub(f"{k}={v}", text, count=1)
            else:
                text = text.rstrip() + f"\n{k}={v}\n"
        env_path.write_text(text, encoding="utf-8")
    except Exception:
        pass
    aq.push_alert("discord", "تم ضبط Discord", "البث جاهز مثل تيليجرام السابق", level="ok")
    return {"ok": True, "discord": discord_cfg_public()}
def stack_payload() -> dict:
    stack_disk = aq.load_json(RUNTIME / "gs_stack_status.json", {})
    tun = tunnel_url()
    discord = discord_cfg_public()
    payload = {
        "ts": aq.utc(),
        "os_version": os.getenv("GS_BOT_OS_VERSION", "2026.10_dual_battalion_v1"),
        "tunnel_url": tun,
        "app_download": (tun.rstrip("/") + "/download/apk?v=battalion1") if tun else "",
        "pair_code": PAIR_CODE,
        "strategy_code": STRATEGY_CODE,
        "battalion": battalion_payload(),
        "notify": {
            "mobile": True,
            "telegram_outbound": False,
            "discord": discord,
        },
        "rules": {
            "notify_min": 70,
            "auto_min": 80,
            "scalp_min": 50,
            "scalp_max_positions": 10,
            "macro_max_positions": 5,
            "pair": STRATEGY_CODE,
            "mobile_pair_code": PAIR_CODE,
            "demo": True,
            "dual_battalion": True,
        },
        "starter": "GS_START_FULL_STACK.bat",
    }
    if isinstance(stack_disk, dict):
        for k in ("bot_main_pids", "daemon_pids", "mobile_api_pids", "discord_bridge_pids"):
            if k in stack_disk:
                payload[k] = stack_disk[k]
        if stack_disk.get("tunnel_url") and not payload["tunnel_url"]:
            payload["tunnel_url"] = stack_disk["tunnel_url"]
    return payload
def tunnel_url() -> str:
    p = RUNTIME / "mobile_tunnel_url.txt"
    try:
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        pass
    return ""
def signal_as_percent(row: dict) -> dict:
    """Bot logs score N/10; control UI ladder is 70/80/90 on a 0–100 scale."""
    out = dict(row or {})
    try:
        raw = float(out.get("score") or out.get("strength") or 0)
    except Exception:
        raw = 0.0
    if raw <= 10:
        out["score10"] = int(round(raw))
        pct = int(round(raw * 10))
    else:
        pct = int(round(raw))
        out["score10"] = int(round(pct / 10))
    out["score"] = pct
    out["strength"] = pct
    return out
def parse_signals_from_log() -> list:
    """استخرج آخر دورة إشارات من سجل البوت (صيغة score N/10)."""
    log = ROOT / "storage" / "logs" / "bot_stdout.log"
    if not log.exists():
        return []
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    # خذ آخر بلوك LIVE SIGNALS إن وُجد، وإلا آخر تطابقات في الذيل
    block = text
    idx = text.rfind("LIVE SIGNALS")
    if idx >= 0:
        block = text[idx:]
        end = block.find("=====")
        # second ===== after header; find signals section end
        parts = block.split("--------------------------------------------------------")
        if len(parts) >= 2:
            block = parts[1]
    found: dict[str, dict] = {}
    for ln in block.splitlines():
        row = parse_signal_line(ln)
        if row:
            found[row["sym"]] = row
    if not found:
        # fallback: scan last 200 lines of whole log
        for ln in text.splitlines()[-200:]:
            row = parse_signal_line(ln)
            if row:
                found[row["sym"]] = row
    rows = sorted(found.values(), key=lambda r: (-int(r["score"]), r["sym"]))
    if rows:
        try:
            (RUNTIME / "last_cycle_signals.json").write_text(
                json.dumps({"signals": rows, "ts": aq.utc()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        write_heartbeat({"signals": len(rows)})
    return rows
def parse_signal_line(ln: str) -> dict | None:
    m = _SIGNAL_LINE_RE.search(ln)
    if not m:
        return None
    sym = m.group(1).upper()
    price = float(m.group(2))
    score = int(float(m.group(3)))
    status = (m.group(4) or "WAIT").strip().upper()
    if status in {"BUY", "BUY SIGNAL", "شراء"}:
        status = "BUY SIGNAL"
    elif status in {"SELL", "SELL SIGNAL", "بيع"}:
        status = "SELL SIGNAL"
    elif "REJECT" in status:
        status = "REJECTED"
    else:
        status = "WAIT" if status not in {"BUY SIGNAL", "SELL SIGNAL", "REJECTED"} else status
    return {
        "sym": sym,
        "score": score,
        "signal": status,
        "price": price,
        "liquidity": 50 + min(40, score * 5),
    }
def signals_live() -> list:
    """اقرأ آخر إشارات من ملف النبض أو من سجل البوت مباشرة."""
    rows = parse_signals_from_log()
    if not rows:
        pulse = RUNTIME / "last_cycle_signals.json"
        if pulse.exists():
            try:
                data = json.loads(pulse.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict) and "signals" in data:
                    rows = data["signals"]
            except Exception:
                rows = []
    if rows:
        return [signal_as_percent(r) for r in rows if isinstance(r, dict)]
    try:
        from config.settings import get_settings

        pairs = list(getattr(get_settings(), "trading_pairs", []) or [])
    except Exception:
        pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
    return [
        signal_as_percent({"sym": p, "score": 0, "signal": "WAIT", "price": 0, "liquidity": 50})
        for p in pairs[:20]
    ]
def write_heartbeat(extra: dict | None = None) -> None:
    payload = {"ts": aq.utc(), "service": "mobile-api-pulse"}
    if extra:
        payload.update(extra)
    try:
        (RUNTIME / "heartbeat.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
def risk_state() -> dict:
    try:
        conn = db()
        row = conn.execute("SELECT value FROM app_config WHERE key='risk_state'").fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
    except Exception:
        pass
    return {}
def battalion_payload() -> dict:
    try:
        from core.battalion.battalion_router import status_payload  # type: ignore

        return status_payload()
    except Exception as exc:
        p = RUNTIME / "dual_battalion.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("ok", True)
                    data["from_file"] = True
                    return data
            except Exception:
                pass
        return {"ok": False, "dual_battalion": False, "error": str(exc)[:200]}
def db():
    conn = sqlite3.connect(str(DB), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
