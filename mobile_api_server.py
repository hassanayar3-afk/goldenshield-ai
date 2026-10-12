#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GoldenShield Mobile API — يربط تطبيق الهاتف بالبوت الحي.

Endpoints:
  GET  /api/health
  GET  /api/rules
  GET  /api/status
  GET  /api/account        # مرآة محفظة Binance الحية
  GET  /api/signals
  GET  /api/positions      # أرصدة المنصة (+ إثراء البوت)
  GET  /api/history
  GET  /api/alerts          # قائمة تنبيهات حديثة
  GET  /api/stack           # حالة البوت + النفق + جسر Discord
  GET  /api/discord         # حالة ربط Discord (بدون أسرار)
  POST /api/pair            # ربط جهاز جديد → device_token
  POST /api/heartbeat       # نبضة جهاز + استلام تنبيهات معلّقة
  POST /api/act             # pause / resume / refresh (آمن)
  POST /api/discord/config  # حفظ Webhook/Bot لبث Discord مثل تيليجرام
  PUT  /upload/apk          # تحديث ملف APK على السيرفر

المصادقة: Header X-GS-Token: <MOBILE_API_TOKEN أو device_token>
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(r"C:\GoldenShield_Binance")
os.chdir(ROOT)
import sys

sys.path.insert(0, str(ROOT))

# حمّل .env
for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

PORT = int(os.getenv("MOBILE_API_PORT", "8790"))
MASTER_TOKEN = os.getenv("MOBILE_API_TOKEN") or secrets.token_urlsafe(24)
# Strategy identity (macro battalion) — NOT used for device auth/pairing.
STRATEGY_CODE = (os.getenv("GS_STRATEGY_CODE") or os.getenv("GS_PAIR_CODE") or "GS-GOLD80").strip().upper()
# Mobile device pairing secret — MUST stay distinct from strategy code.
_raw_pair = (os.getenv("MOBILE_PAIR_CODE") or "").strip().upper()
if not _raw_pair or _raw_pair == STRATEGY_CODE or _raw_pair in {"GS-GOLD80", "GOLD80"}:
    # Migrate away from legacy conflation of strategy ↔ pair code
    _raw_pair = "GS-LINK" + secrets.token_hex(3).upper()
PAIR_CODE = _raw_pair
DB = ROOT / "storage" / "db" / "goldenshield.db"
RUNTIME = ROOT / "storage" / "runtime"
DEVICES_FILE = RUNTIME / "mobile_devices.json"
ALERTS_FILE = RUNTIME / "mobile_alerts.json"
RUNTIME.mkdir(parents=True, exist_ok=True)
PANEL_ROOT = ROOT / "control-panel-www"
PANEL_ROOT.mkdir(parents=True, exist_ok=True)

# Persist separated credentials (never overwrite a good distinct pair with strategy)
_cred_path = RUNTIME / "mobile_api_credentials.txt"
_prev = {}
if _cred_path.exists():
    try:
        for _line in _cred_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in _line:
                _k, _v = _line.split("=", 1)
                _prev[_k.strip()] = _v.strip()
    except Exception:
        _prev = {}
_persisted_pair = (_prev.get("MOBILE_PAIR_CODE") or "").strip().upper()
if _persisted_pair and _persisted_pair != STRATEGY_CODE and _persisted_pair not in {"GS-GOLD80", "GOLD80"}:
    PAIR_CODE = _persisted_pair
# Keep env/.env in sync for operators
os.environ["MOBILE_PAIR_CODE"] = PAIR_CODE
os.environ["GS_STRATEGY_CODE"] = STRATEGY_CODE

(RUNTIME / "mobile_api_credentials.txt").write_text(
    (
        f"MOBILE_API_TOKEN={MASTER_TOKEN}\n"
        f"MOBILE_PAIR_CODE={PAIR_CODE}\n"
        f"GS_STRATEGY_CODE={STRATEGY_CODE}\n"
        f"MOBILE_API_PORT={PORT}\n"
        f"BASE=http://0.0.0.0:{PORT}\n"
    ),
    encoding="utf-8",
)

_lock = threading.Lock()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _devices() -> dict:
    return _load_json(DEVICES_FILE, {"devices": {}})


def _save_devices(data: dict) -> None:
    _save_json(DEVICES_FILE, data)


def _prune_devices(data: dict, max_devices: int = 8) -> dict:
    """أبقِ أحدث الأجهزة فقط — يمنع تراكم التوكنات الميتة (سبب unauthorized / طلب الرمز)."""
    devices = dict(data.get("devices") or {})
    if len(devices) <= max_devices:
        return data
    ranked = sorted(
        devices.items(),
        key=lambda kv: (
            str((kv[1] or {}).get("last_seen") or ""),
            str((kv[1] or {}).get("paired_at") or ""),
        ),
        reverse=True,
    )
    data = dict(data)
    data["devices"] = dict(ranked[:max_devices])
    data["pruned_at"] = _utc()
    data["max_devices"] = max_devices
    return data


def _alerts() -> list:
    return _load_json(ALERTS_FILE, [])


def _push_alert(kind: str, title: str, body: str, *, level: str = "info", meta: dict | None = None) -> None:
    with _lock:
        items = _alerts()
        items.append(
            {
                "id": secrets.token_hex(8),
                "ts": _utc(),
                "kind": kind,
                "title": title,
                "body": body,
                "level": level,
                "meta": meta or {},
                "tone": True,
            }
        )
        _save_json(ALERTS_FILE, items[-200:])


def _db():
    conn = sqlite3.connect(str(DB), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _risk_state() -> dict:
    try:
        conn = _db()
        row = conn.execute("SELECT value FROM app_config WHERE key='risk_state'").fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
    except Exception:
        pass
    return {}


def _rules_payload() -> dict:
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


_STABLE_ASSETS = frozenset({"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI"})
_SNAP_TTL_SEC = 20.0
_SNAP_STALE_SEC = 120.0  # serve stale rather than stall clients past UI timeouts
_SNAP_BAN_TTL_SEC = 90.0
_snap_cache: dict = {"ts": 0.0, "data": None, "ban_until": 0.0}
_snap_lock = threading.Lock()
_snap_refreshing = False
_entry_cache: dict[str, tuple[float, float]] = {}  # sym -> (ts, entry)
_ENTRY_TTL_SEC = 300.0
# Typical Binance spot min notional — used as a fast dust heuristic (no extra REST).
_FAST_DUST_USDT = 5.0


def _load_snap_disk() -> dict | None:
    """Boot / stampede fallback — keep UI alive without waiting on Binance."""
    try:
        p = RUNTIME / "binance_snapshot.json"
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("ok"):
            return data
    except Exception:
        return None
    return None


# Seed memory cache from disk so the first post-restart poll is not a 15s cold miss.
try:
    _disk_seed = _load_snap_disk()
    if _disk_seed:
        _snap_cache["data"] = _disk_seed
        # Treat as slightly stale so a background refresh still happens, but UI is instant.
        _snap_cache["ts"] = time.time() - (_SNAP_TTL_SEC + 1.0)
except Exception:
    pass


def _live_prices(symbols: list[str]) -> dict[str, float]:
    """أسعار حية من المنصة للمراكز المفتوحة."""
    prices: dict[str, float] = {}
    if not symbols:
        return prices
    try:
        from data.exchange_client import get_exchange

        ex = get_exchange()
        for sym in symbols:
            try:
                t = ex.fetch_ticker(sym)
                px = float(t.get("last") or t.get("close") or 0)
                if px > 0:
                    prices[sym] = px
            except Exception:
                continue
    except Exception:
        pass
    return prices


def _avg_entry_price(ex, sym: str, qty: float) -> float | None:
    """متوسط تكلفة تقريبي من آخر صفقات الشراء لتغطية الكمية الحالية."""
    if qty <= 0:
        return None
    try:
        trades = ex.fetch_my_trades(sym, limit=50) or []
    except Exception:
        return None
    need = float(qty)
    cost = 0.0
    got = 0.0
    for tr in reversed(trades):
        side = str(tr.get("side") or "").lower()
        if side != "buy":
            continue
        amt = float(tr.get("amount") or 0)
        px = float(tr.get("price") or 0)
        if amt <= 0 or px <= 0:
            continue
        take = min(amt, need - got)
        cost += take * px
        got += take
        if got >= need - 1e-12:
            break
    if got <= 0:
        return None
    return cost / got


def _entry_price_cached(ex, sym: str, qty: float, mark: float) -> float:
    """Avoid fetch_my_trades on every status poll — that was blowing past UI timeouts."""
    now = time.time()
    hit = _entry_cache.get(sym)
    if hit and (now - hit[0]) < _ENTRY_TTL_SEC and hit[1] > 0:
        return float(hit[1])
    entry = _avg_entry_price(ex, sym, qty) or mark
    if entry > 0:
        _entry_cache[sym] = (now, float(entry))
    return float(entry or mark or 0)


def _account_from_status(st: dict | None = None) -> dict:
    """Fallback account mirror when live Binance fetch is banned/unavailable."""
    st = st if isinstance(st, dict) else {}
    equity = st.get("balance")
    try:
        equity_f = float(equity) if equity is not None else None
    except Exception:
        equity_f = None
    return {
        "ok": equity_f is not None,
        "degraded": True,
        "equity": equity_f,
        "free_cash": st.get("free_cash"),
        "session_start_equity": st.get("session_start_balance"),
        "session_pnl": st.get("session_pnl"),
        "unrealized_pnl": st.get("unrealized_pnl"),
        "assets": st.get("assets") or [],
        "holdings": [],
        "open_positions": st.get("open_positions"),
        "demo": bool(st.get("demo")),
        "source": st.get("balance_source") or "status_fallback",
        "error": st.get("exchange_error"),
        "ts": _utc(),
    }


def _binance_snapshot(force: bool = False) -> dict:
    """مرآة حية لمحفظة Binance Spot (رصيد + أصول + PnL الجلسة).

    Critical: never stampede Binance on parallel /status+/positions polls —
    that caused client ``status:timeout`` / ``positions:Failed to fetch``.
    """
    now = time.time()
    cached = _snap_cache.get("data")
    cache_age = now - float(_snap_cache.get("ts") or 0)
    ban_until = float(_snap_cache.get("ban_until") or 0)
    # While Binance IP-banned, never hammer REST — serve cache / fail soft.
    if ban_until > now:
        if cached and cached.get("ok"):
            out = dict(cached)
            out["degraded"] = True
            out["ban_until"] = ban_until
            out["error"] = cached.get("error") or "binance temporarily banned — using cache"
            return out
        fail = {
            "ok": False,
            "degraded": True,
            "error": "binance temporarily banned — wait before retry",
            "ban_until": ban_until,
            "equity": None,
            "holdings": [],
            "assets": [],
            "source": "binance",
            "ts": _utc(),
        }
        return fail

    ttl = _SNAP_TTL_SEC
    if (
        not force
        and cached
        and cached.get("ok")
        and cache_age < ttl
    ):
        return cached

    # Soft-stale path: return last good snapshot NOW and refresh in background.
    # This is what stops ``status:timeout`` on the control panel.
    global _snap_refreshing
    if (
        not force
        and cached
        and cached.get("ok")
        and cache_age < _SNAP_STALE_SEC
    ):
        if not _snap_refreshing:
            _snap_refreshing = True

            def _bg_refresh() -> None:
                global _snap_refreshing
                try:
                    _binance_snapshot(force=True)
                except Exception:
                    pass
                finally:
                    _snap_refreshing = False

            threading.Thread(target=_bg_refresh, name="gs-snap-refresh", daemon=True).start()
        out = dict(cached)
        out["degraded"] = True
        out["stale"] = True
        return out

    # Another request is already refreshing — NEVER block clients past UI timeouts.
    acquired = _snap_lock.acquire(blocking=False)
    if not acquired:
        if cached and cached.get("ok"):
            out = dict(cached)
            out["degraded"] = True
            out["stale"] = True
            return out
        disk = _load_snap_disk()
        if disk:
            out = dict(disk)
            out["degraded"] = True
            out["stale"] = True
            out["error"] = "snapshot busy — disk cache"
            return out
        return {
            "ok": False,
            "degraded": True,
            "error": "snapshot busy",
            "equity": None,
            "holdings": [],
            "assets": [],
            "source": "binance",
            "ts": _utc(),
        }

    try:
        # Double-check after lock (winner may have just refreshed)
        now = time.time()
        cached = _snap_cache.get("data")
        cache_age = now - float(_snap_cache.get("ts") or 0)
        if (
            not force
            and cached
            and cached.get("ok")
            and cache_age < ttl
        ):
            return cached

        from data.exchange_client import get_exchange

        ex = get_exchange()
        # Warm markets once (cached by ccxt) — avoids per-ticker market loads
        try:
            ex.load_markets()
        except Exception:
            pass
        bal = ex.fetch_balance() or {}
        total = bal.get("total") or {}
        free = bal.get("free") or {}
        used = bal.get("used") or {}

        assets: list[dict] = []
        nonstable_syms: list[str] = []
        for asset, raw in total.items():
            try:
                amt = float(raw or 0)
            except Exception:
                continue
            if amt <= 0:
                continue
            a = str(asset).upper()
            assets.append(
                {
                    "asset": a,
                    "total": amt,
                    "free": float(free.get(asset) or free.get(a) or 0),
                    "used": float(used.get(asset) or used.get(a) or 0),
                }
            )
            if a not in _STABLE_ASSETS:
                nonstable_syms.append(f"{a}/USDT")

        # Batch tickers when possible (one REST round-trip instead of N)
        prices: dict[str, float] = {}
        if nonstable_syms:
            try:
                if hasattr(ex, "fetch_tickers"):
                    tickers = ex.fetch_tickers(nonstable_syms) or {}
                    for sym, t in tickers.items():
                        px = float((t or {}).get("last") or (t or {}).get("close") or 0)
                        if px > 0:
                            prices[sym] = px
            except Exception:
                prices = {}
            for sym in nonstable_syms:
                if sym in prices:
                    continue
                try:
                    t = ex.fetch_ticker(sym)
                    px = float(t.get("last") or t.get("close") or 0)
                    if px > 0:
                        prices[sym] = px
                except Exception:
                    continue

        equity = 0.0
        free_cash = 0.0
        holdings: list[dict] = []
        unrealized = 0.0

        for a in assets:
            asset = a["asset"]
            qty = float(a["total"])
            if asset in _STABLE_ASSETS:
                usdt_val = qty
                equity += usdt_val
                free_cash += float(a["free"])
                continue

            sym = f"{asset}/USDT"
            price = float(prices.get(sym) or 0)
            if price <= 0:
                continue
            usdt_val = qty * price
            free_qty = float(a["free"])
            # Fast path: sub-min-notional leftovers are dust — skip trade-history + precision REST
            if usdt_val < _FAST_DUST_USDT:
                entry = price
                sellable = 0.0
                is_dust = True
            else:
                entry = _entry_price_cached(ex, sym, qty, price)
                sellable = _sellable_amount(ex, sym, free_qty or qty, price, free=free_qty)
                is_dust = sellable <= 0
            pnl = (price - entry) * qty
            unrealized += pnl
            equity += usdt_val
            holdings.append(
                {
                    "sym": sym,
                    "asset": asset,
                    "side": "BUY",
                    "qty": qty,
                    "entry": entry,
                    "price": price,
                    "pnl": round(pnl, 6),
                    "usdt": round(usdt_val, 6),
                    "free": float(a["free"]),
                    "used": float(a["used"]),
                    "sellable": sellable,
                    "dust": is_dust,
                    "source": "binance",
                }
            )

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sess_path = RUNTIME / "binance_day_session.json"
        sess = _load_json(sess_path, {})
        if sess.get("day") != day or not sess.get("start_equity"):
            sess = {
                "day": day,
                "start_equity": round(equity, 8),
                "updated_at": _utc(),
            }
            _save_json(sess_path, sess)
        start_equity = float(sess.get("start_equity") or equity)
        session_pnl = equity - start_equity

        demo = str(os.getenv("BINANCE_DEMO_TRADING", "")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        payload = {
            "ok": True,
            "equity": round(equity, 8),
            "free_cash": round(free_cash, 8),
            "session_start_equity": round(start_equity, 8),
            "session_pnl": round(session_pnl, 8),
            "unrealized_pnl": round(unrealized, 8),
            "assets": assets,
            "holdings": holdings,
            # Count only market-tradeable positions (exclude Binance dust leftovers)
            "open_positions": len([h for h in holdings if not h.get("dust")]),
            "dust_positions": len([h for h in holdings if h.get("dust")]),
            "demo": demo,
            "source": "binance",
            "ts": _utc(),
        }
        _snap_cache["ts"] = time.time()
        _snap_cache["data"] = payload
        try:
            (RUNTIME / "binance_snapshot.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return payload
    except Exception as exc:
        msg = str(exc)
        # Parse Binance weight ban expiry if present ("IP banned until <ms>")
        ban_until = 0.0
        try:
            import re as _re

            m = _re.search(r"banned until\s+(\d+)", msg, _re.I)
            if m:
                raw = int(m.group(1))
                ban_until = (raw / 1000.0) if raw > 10_000_000_000 else float(raw)
        except Exception:
            ban_until = 0.0
        if ban_until <= 0 and ("-1003" in msg or "418" in msg or "teapot" in msg.lower()):
            ban_until = time.time() + _SNAP_BAN_TTL_SEC
        if ban_until > time.time():
            _snap_cache["ban_until"] = ban_until

        # Prefer last good snapshot over hard failure (keeps UI numbers alive)
        if cached and cached.get("ok"):
            out = dict(cached)
            out["degraded"] = True
            out["error"] = msg
            if ban_until:
                out["ban_until"] = ban_until
            return out

        fail = {
            "ok": False,
            "degraded": True,
            "error": msg,
            "equity": None,
            "holdings": [],
            "assets": [],
            "source": "binance",
            "ts": _utc(),
        }
        if ban_until:
            fail["ban_until"] = ban_until
        return fail
    finally:
        if acquired:
            try:
                _snap_lock.release()
            except Exception:
                pass


def _db_open_trades() -> list:
    """صفقات البوت المفتوحة من SQLite (للدمج مع مرآة المنصة)."""
    out = []
    try:
        conn = _db()
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
        live = _live_prices(syms)
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


def _positions() -> list:
    """مصدر الحقيقة: أرصدة Binance غير المستقرة + إثراء بيانات البوت إن وُجدت."""
    snap = _binance_snapshot()
    db_rows = [p for p in _db_open_trades() if p and "error" not in p]
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


def _history(limit: int = 100) -> list:
    """كل الصفقات المغلقة من 2026-10-04 فصاعداً (رابحة وخاسرة ومتعادلة)."""
    out = []
    keep_from = "2026-10-04"
    try:
        conn = _db()
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


import re

_SIGNAL_LINE_RE = re.compile(
    r"(?:✅|\*)\s*([A-Z0-9]+/[A-Z0-9]+)\s*\|\s*(?:price|السعر):\s*([0-9.]+)\s*\|\s*"
    r"(?:score|الدرجة):\s*(\d+(?:\.\d+)?)/10\s*\|\s*(?:الحالة:\s*)?([A-Z_ ]+|WAIT|REJECTED)",
    re.IGNORECASE,
)

_last_score_bucket: dict[str, int] = {}


def _score_bucket(score: int) -> int:
    """0 | 70 | 80 buckets for alert escalation."""
    if score >= 8:
        return 80
    if score >= 7:
        return 70
    return 0


def _parse_signal_line(ln: str) -> dict | None:
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


def _parse_signals_from_log() -> list:
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
        row = _parse_signal_line(ln)
        if row:
            found[row["sym"]] = row
    if not found:
        # fallback: scan last 200 lines of whole log
        for ln in text.splitlines()[-200:]:
            row = _parse_signal_line(ln)
            if row:
                found[row["sym"]] = row
    rows = sorted(found.values(), key=lambda r: (-int(r["score"]), r["sym"]))
    if rows:
        try:
            (RUNTIME / "last_cycle_signals.json").write_text(
                json.dumps({"signals": rows, "ts": _utc()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        _write_heartbeat({"signals": len(rows)})
    return rows


def _maybe_alert_signal(row: dict) -> None:
    sym = row["sym"]
    score = int(row["score"])
    bucket = _score_bucket(score)
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
        _push_alert(
            "auto_signal",
            title,
            f"{sym} · {pct}/100 · {status} · تلقائي من 80",
            level="trade" if status in {"BUY SIGNAL", "SELL SIGNAL"} else "signal",
            meta={"sym": sym, "score": score, "pct": pct},
        )
    else:
        _push_alert(
            "signal",
            "📡 إشارة قوية",
            f"{sym} · {pct}/100 · {status}",
            level="signal",
            meta={"sym": sym, "score": score, "pct": pct},
        )


def _signal_as_percent(row: dict) -> dict:
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


def _signals_live() -> list:
    """اقرأ آخر إشارات من ملف النبض أو من سجل البوت مباشرة."""
    rows = _parse_signals_from_log()
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
        return [_signal_as_percent(r) for r in rows if isinstance(r, dict)]
    try:
        from config.settings import get_settings

        pairs = list(getattr(get_settings(), "trading_pairs", []) or [])
    except Exception:
        pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
    return [
        _signal_as_percent({"sym": p, "score": 0, "signal": "WAIT", "price": 0, "liquidity": 50})
        for p in pairs[:20]
    ]


def _write_heartbeat(extra: dict | None = None) -> None:
    payload = {"ts": _utc(), "service": "mobile-api-pulse"}
    if extra:
        payload.update(extra)
    try:
        (RUNTIME / "heartbeat.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _mark_trade_closed(trade_id: str, exit_price: float, pnl: float) -> None:
    try:
        conn = _db()
        conn.execute(
            """
            UPDATE trades
            SET status='closed', exit_price=?, pnl=?, closed_at=?
            WHERE id=? AND (status='open' OR closed_at IS NULL)
            """,
            (exit_price, pnl, _utc(), trade_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _market_min_filters(ex, sym: str) -> tuple[float, float]:
    """Return (min_amount, min_notional/cost) for a market."""
    try:
        market = ex.market(sym) or {}
        limits = market.get("limits") or {}
        min_amt = float((limits.get("amount") or {}).get("min") or 0) or 0.0
        min_cost = float((limits.get("cost") or {}).get("min") or 0) or 0.0
        return min_amt, min_cost
    except Exception:
        return 0.0, 0.0


def _sellable_amount(
    ex, sym: str, qty: float, price: float, *, free: float | None = None, refresh_free: bool = False
) -> float:
    """Clamp to free balance + exchange precision. 0 = dust / untradeable.

    Pass ``free`` when already known (snapshot path) to avoid extra fetch_balance calls.
    Set ``refresh_free=True`` only on live close orders.
    """
    if qty <= 0 or not sym:
        return 0.0
    amount = float(qty)
    if free is not None and free >= 0:
        amount = min(amount, float(free))
    elif refresh_free:
        try:
            base = sym.split("/")[0]
            freex = float((ex.fetch_balance().get("free") or {}).get(base) or 0.0)
            if freex > 0:
                amount = min(amount, freex)
        except Exception:
            pass
    if amount <= 0:
        return 0.0
    try:
        amount = float(ex.amount_to_precision(sym, amount))
    except Exception:
        return 0.0
    if amount <= 0:
        return 0.0
    min_amt, min_cost = _market_min_filters(ex, sym)
    if min_amt and amount + 1e-18 < min_amt:
        return 0.0
    if min_cost and price > 0 and (amount * price) + 1e-12 < min_cost:
        return 0.0
    return amount


def _convert_dust_assets(ex, assets: list[str]) -> dict:
    """Convert tiny spot leftovers to BNB via Binance dust endpoint when available."""
    cleaned: list[str] = []
    for a in assets:
        asset = str(a or "").strip().upper()
        if not asset or asset in _STABLE_ASSETS or asset == "BNB":
            continue
        if asset not in cleaned:
            cleaned.append(asset)
    if not cleaned:
        return {"ok": True, "converted": [], "error": None}
    try:
        # Spot: POST /sapi/v1/asset/dust  (not available on some demo/testnet URLs)
        res = ex.sapiPostAssetDust({"asset": cleaned})
        return {"ok": True, "converted": cleaned, "raw": res, "error": None}
    except Exception as exc:
        return {"ok": False, "converted": [], "error": str(exc)}


def _close_positions(mode: str = "all", symbol: str | None = None) -> dict:
    """إغلاق مراكز عبر المنصة مباشرة (all|winners|losers|symbol).

    Handles Binance dust (below LOT_SIZE / min notional): attempts dust→BNB convert,
    otherwise reports skipped_dust instead of a fake success toast.
    """
    try:
        from data.exchange_client import get_exchange
    except Exception as exc:
        return {"ok": False, "error": f"exchange import: {exc}", "closed": [], "failed": []}

    positions = [p for p in _positions() if p and "error" not in p]
    if symbol:
        sym_u = symbol.strip().upper()
        positions = [p for p in positions if str(p.get("sym") or "").upper() == sym_u]
    if not positions:
        return {"ok": True, "closed": [], "failed": [], "skipped_dust": [], "message": "لا مراكز مفتوحة"}

    try:
        ex = get_exchange()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "closed": [], "failed": []}

    closed: list[str] = []
    failed: list[str] = []
    skipped_dust: list[str] = []
    dust_assets: list[str] = []
    selected = 0

    for p in positions:
        sym = p.get("sym") or ""
        entry = float(p.get("entry") or 0)
        qty = float(p.get("qty") or p.get("free") or 0)
        side = (p.get("side") or "BUY").upper()
        if qty <= 0 or not sym:
            continue
        try:
            ticker = ex.fetch_ticker(sym)
            price = float(ticker.get("last") or ticker.get("close") or entry or 0)
        except Exception:
            price = float(p.get("price") or entry or 0)
        pnl = float(p.get("pnl") or 0)
        if not pnl and entry and price:
            pnl = (price - entry) * qty if side == "BUY" else (entry - price) * qty
        if mode == "winners" and pnl <= 0:
            continue
        if mode == "losers" and pnl >= 0:
            continue
        selected += 1
        exit_side = "sell" if side == "BUY" else "buy"

        # Cancel protective orders first (best-effort)
        try:
            for o in ex.fetch_open_orders(sym) or []:
                try:
                    ex.cancel_order(o.get("id"), sym)
                except Exception:
                    pass
        except Exception:
            pass

        amount = qty
        if exit_side == "sell":
            amount = _sellable_amount(ex, sym, qty, price, free=float(p.get("free") or 0) or None, refresh_free=True)
            if amount <= 0:
                asset = (p.get("asset") or sym.split("/")[0] or "").upper()
                skipped_dust.append(sym)
                if asset:
                    dust_assets.append(asset)
                continue
        else:
            try:
                amount = float(ex.amount_to_precision(sym, qty))
            except Exception as exc:
                failed.append(f"{sym}:{exc}")
                continue
            if amount <= 0:
                skipped_dust.append(sym)
                continue

        try:
            ex.create_order(sym, "market", exit_side, amount)
            if p.get("id"):
                _mark_trade_closed(str(p["id"]), price, pnl)
            closed.append(sym)
        except Exception as exc:
            err = str(exc)
            low = err.lower()
            # Precision / min-notional → treat as dust leftover, not a dead button
            if any(
                k in low
                for k in (
                    "precision",
                    "lot_size",
                    "min notional",
                    "notional",
                    "filter failure",
                    "insufficient balance",
                )
            ):
                asset = (p.get("asset") or sym.split("/")[0] or "").upper()
                skipped_dust.append(sym)
                if asset:
                    dust_assets.append(asset)
            else:
                failed.append(f"{sym}:{exc}")

    dust_convert = None
    if dust_assets and not closed:
        # Only bother converting when market sells did not clear everything
        dust_convert = _convert_dust_assets(ex, dust_assets)
        if dust_convert.get("ok") and dust_convert.get("converted"):
            for asset in dust_convert["converted"]:
                sym = f"{asset}/USDT"
                if sym not in closed:
                    closed.append(f"{sym} (dust→BNB)")
            # Successfully converted — no longer "skipped"
            skipped_dust = [s for s in skipped_dust if s.split("/")[0].upper() not in set(dust_convert["converted"])]

    if selected == 0:
        if mode == "winners":
            msg = "لا صفقات رابحة للإغلاق"
        elif mode == "losers":
            msg = "لا صفقات خاسرة للإغلاق"
        else:
            msg = "لا مراكز مطابقة للإغلاق"
        return {
            "ok": True,
            "closed": [],
            "failed": [],
            "skipped_dust": [],
            "mode": mode,
            "message": msg,
            "trading_enabled": True,
        }

    parts = [f"أُغلق {len(closed)}"]
    if failed:
        parts.append(f"فشل {len(failed)}")
    if skipped_dust:
        parts.append(f"غبار {len(skipped_dust)}")
    msg = " · ".join(parts)
    if skipped_dust and not closed and not failed:
        msg = (
            f"بقايا غبار فقط ({len(skipped_dust)}) — أقل من حد بينانس الأدنى، "
            "لا تُغلق بأمر سوق"
        )
        if dust_convert and not dust_convert.get("ok"):
            msg += " · تحويل الغبار غير متاح على هذا الحساب"
    elif closed and skipped_dust:
        msg += " · بقايا غبار تُتجاهل"

    # Fake "تم" was the bug: all dust failures still returned ok=True with empty closed.
    # ok stays True when the only leftovers are dust (explained in message), False on real fails.
    ok = True
    if failed and not closed:
        ok = False
        msg = f"فشل الإغلاق: {failed[0][:120]}"
    elif failed and closed:
        ok = True  # partial success

    return {
        "ok": ok,
        "closed": closed,
        "failed": failed,
        "skipped_dust": skipped_dust,
        "dust_convert": {
            "ok": bool(dust_convert.get("ok")) if dust_convert else None,
            "converted": (dust_convert or {}).get("converted") or [],
            "error": (dust_convert or {}).get("error"),
        }
        if dust_convert
        else None,
        "mode": mode,
        "message": msg,
        "trading_enabled": True,
    }


def _status() -> dict:
    risk = _risk_state()
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

    snap = _binance_snapshot()
    positions = [p for p in _positions() if p and "error" not in p]
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
        "ts": _utc(),
        "pair_code_hint": PAIR_CODE[:3] + "***",
        "strategy_code": STRATEGY_CODE,
        "trading_enabled": True,
    }


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    token = handler.headers.get("X-GS-Token") or handler.headers.get("Authorization", "").replace(
        "Bearer ", ""
    )
    if not token:
        q = parse_qs(urlparse(handler.path).query)
        token = (q.get("token") or [""])[0]
    if token == MASTER_TOKEN:
        return True
    devices = _devices().get("devices", {})
    return token in devices


def _tunnel_url() -> str:
    p = RUNTIME / "mobile_tunnel_url.txt"
    try:
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        pass
    return ""


def _discord_cfg_public() -> dict:
    cfg_path = RUNTIME / "discord_bridge.json"
    disk = _load_json(cfg_path, {})
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


def _battalion_payload() -> dict:
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


def _stack_payload() -> dict:
    stack_disk = _load_json(RUNTIME / "gs_stack_status.json", {})
    tun = _tunnel_url()
    discord = _discord_cfg_public()
    payload = {
        "ts": _utc(),
        "os_version": os.getenv("GS_BOT_OS_VERSION", "2026.10_dual_battalion_v1"),
        "tunnel_url": tun,
        "app_download": (tun.rstrip("/") + "/download/apk?v=battalion1") if tun else "",
        "pair_code": PAIR_CODE,
        "strategy_code": STRATEGY_CODE,
        "battalion": _battalion_payload(),
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


def _save_discord_config(body: dict) -> dict:
    cfg_path = RUNTIME / "discord_bridge.json"
    cur = _load_json(cfg_path, {})
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
    _push_alert("discord", "تم ضبط Discord", "البث جاهز مثل تيليجرام السابق", level="ok")
    return {"ok": True, "discord": _discord_cfg_public()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-GS-Token, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")

    def _serve_panel_file(self, rel: str):
        """Serve GoldenShield control panel static assets from PANEL_ROOT."""
        rel = (rel or "index.html").replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            return self._json(400, {"ok": False, "error": "bad path"})
        target = (PANEL_ROOT / rel).resolve()
        try:
            target.relative_to(PANEL_ROOT.resolve())
        except Exception:
            return self._json(400, {"ok": False, "error": "bad path"})
        if target.is_dir():
            target = target / "index.html"
        if not target.exists() or not target.is_file():
            return self._json(404, {"ok": False, "error": f"not found: {rel}"})
        raw = target.read_bytes()
        suffix = target.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
            ".map": "application/json",
        }.get(suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)
        return True

    def _json(self, code: int, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/download/export", "/download/source.zip", "/GoldenShield-Source-Export.zip"):
                z = Path(r"C:\Users\Public\GoldenShield-Source-Export.zip")
                if not z.exists():
                    return self._json(404, {"ok": False, "error": "export zip not found"})
                raw = z.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header(
                    "Content-Disposition",
                    "attachment; filename=GoldenShield-Source-Export.zip",
                )
                self.send_header("Content-Length", str(len(raw)))
                self._cors()
                self.end_headers()
                self.wfile.write(raw)
                return
            if path in ("/download/apk", "/GoldenShield-Control.apk", "/app.apk"):
                apk = Path(r"C:\Users\Public\GoldenShield-Control.apk")
                if not apk.exists():
                    apk = ROOT / "downloads" / "GoldenShield-Control.apk"
                if not apk.exists():
                    return self._json(404, {"ok": False, "error": "apk not found"})
                raw = apk.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header(
                    "Content-Disposition",
                    "attachment; filename=GoldenShield-Control.apk",
                )
                self.send_header("Content-Length", str(len(raw)))
                self._cors()
                self.end_headers()
                self.wfile.write(raw)
                return
            if path in ("/download/live-base", "/LIVE_API_BASE.txt", "/api/live-base"):
                # Public pointer so clients rediscover the tunnel without Discord CDN
                tun = _tunnel_url().lstrip("\ufeff").strip().rstrip("/")
                if not tun.startswith("http"):
                    # Self-heal from request Host when tunnel file is stale
                    host = (self.headers.get("Host") or "").strip()
                    if host and "trycloudflare.com" in host:
                        tun = f"https://{host.split(':')[0]}"
                if not tun.startswith("http"):
                    return self._json(503, {"ok": False, "error": "tunnel url unavailable"})
                raw = (tun + "\n").encode("utf-8")
                try:
                    (RUNTIME / "mobile_tunnel_url.txt").write_text(tun + "\n", encoding="utf-8")
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self._cors()
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/health":
                return self._json(200, {"ok": True, "service": "goldenshield-mobile-api", "ts": _utc()})
            # Web dashboard (same tunnel) — root was JSON-only and confused phone browsers
            if path in ("/", "/panel", "/panel/", "/dashboard", "/dashboard/"):
                index = PANEL_ROOT / "index.html"
                if index.exists():
                    raw = index.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(raw)))
                    self._cors()
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                return self._json(
                    200,
                    {
                        "ok": True,
                        "service": "goldenshield-mobile-api",
                        "ts": _utc(),
                        "hint": "control panel not installed — open /api/health",
                        "pair_code_hint": PAIR_CODE[:3] + "***",
                    },
                )
            if path.startswith("/panel/") or path.startswith("/dashboard/"):
                rel = path.split("/", 2)[-1]  # after panel/ or dashboard/
                return self._serve_panel_file(rel)
            # Also allow direct asset paths used by index.html (./ui/ ./config/ ./boot.js ...)
            if path.startswith(("/ui/", "/config/", "/controllers/", "/services/", "/notifications/")) or path in (
                "/boot.js",
                "/index.html",
            ):
                return self._serve_panel_file(path.lstrip("/"))
            if path in ("/api/bootstrap", "/api/boot"):
                # Public — separates strategy identity from mobile pairing secret
                tun = _tunnel_url().lstrip("\ufeff").strip()
                return self._json(
                    200,
                    {
                        "ok": True,
                        "service": "goldenshield-mobile-api",
                        "ts": _utc(),
                        "strategy_code": STRATEGY_CODE,
                        "pair_code": PAIR_CODE,
                        "mobile_pair_code": PAIR_CODE,
                        "pair_code_hint": PAIR_CODE[:3] + "***",
                        "api_base_hint": tun.rstrip("/") if tun.startswith("https://") else "",
                        "rules": _rules_payload(),
                        "auth_model": {
                            "strategy_code": "macro/scalp identity only (e.g. GS-GOLD80)",
                            "mobile_pair_code": "device pairing secret",
                            "device_token": "session auth via X-GS-Token after /api/pair",
                        },
                    },
                )
            if path == "/api/rules":
                # القواعد عامة للقراءة بعد الربط
                if not _auth_ok(self):
                    return self._json(401, {"ok": False, "error": "unauthorized"})
                return self._json(200, {"ok": True, "rules": _rules_payload()})
            if not _auth_ok(self):
                return self._json(401, {"ok": False, "error": "unauthorized — pair first"})
            if path == "/api/status":
                return self._json(200, {"ok": True, "status": _status(), "rules": _rules_payload()})
            if path == "/api/account":
                # Cache-first (no force) — avoids Binance weight bans from phone polling.
                snap = _binance_snapshot(force=False)
                st = _status()
                if not snap.get("ok"):
                    # Soft-fail: synthesize from status so UI never freezes on 502
                    snap = _account_from_status(st)
                    if snap.get("error") is None and st.get("exchange_error"):
                        snap["error"] = st.get("exchange_error")
                return self._json(
                    200,
                    {
                        "ok": True,
                        "account": snap,
                        "status": st,
                        "degraded": bool(snap.get("degraded")),
                    },
                )
            if path == "/api/signals":
                return self._json(200, {"ok": True, "signals": _signals_live()})
            if path == "/api/positions":
                snap = _binance_snapshot()
                # Dashboard shows tradeable positions only (dust stays off the UI)
                positions = [r for r in _positions() if r and not r.get("dust")]
                return self._json(
                    200,
                    {
                        "ok": True,
                        "positions": positions,
                        "source": "binance" if snap.get("ok") else "bot_db",
                        "equity": snap.get("equity") if snap.get("ok") else None,
                    },
                )
            if path == "/api/history":
                return self._json(200, {"ok": True, "history": _history()})
            if path == "/api/alerts":
                q = parse_qs(urlparse(self.path).query)
                since = (q.get("since") or [""])[0]
                items = _alerts()
                if since:
                    items = [a for a in items if str(a.get("ts", "")) > since]
                return self._json(200, {"ok": True, "alerts": items[-50:]})
            if path == "/api/stack":
                return self._json(200, {"ok": True, "stack": _stack_payload(), "status": _status()})
            if path == "/api/battalion":
                return self._json(200, {"ok": True, "battalion": _battalion_payload(), "stack": _stack_payload()})
            if path == "/api/discord":
                return self._json(200, {"ok": True, "discord": _discord_cfg_public(), "stack": _stack_payload()})
            return self._json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-500:]})

    def do_PUT(self):
        path = urlparse(self.path).path
        try:
            if path in ("/upload/apk", "/api/upload/apk"):
                if not _auth_ok(self):
                    return self._json(401, {"ok": False, "error": "unauthorized"})
                n = int(self.headers.get("Content-Length") or 0)
                if n < 100_000 or n > 80_000_000:
                    return self._json(400, {"ok": False, "error": f"bad size {n}"})
                raw = self.rfile.read(n)
                if raw[:2] != b"PK":
                    return self._json(400, {"ok": False, "error": "not an apk/zip"})
                targets = [
                    Path(r"C:\Users\Public\GoldenShield-Control.apk"),
                    ROOT / "downloads" / "GoldenShield-Control.apk",
                    ROOT / "storage" / "mobile" / "GoldenShield-Control.apk",
                ]
                for t in targets:
                    try:
                        t.parent.mkdir(parents=True, exist_ok=True)
                        t.write_bytes(raw)
                    except Exception:
                        pass
                _push_alert("apk", "تم تحديث APK", f"{n} بايت", level="ok")
                return self._json(200, {"ok": True, "bytes": n})
            return self._json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/pair":
                code = str(body.get("pair_code") or body.get("code") or "").strip().upper()
                resume_token = str(
                    body.get("device_token") or body.get("session_token") or body.get("token") or ""
                ).strip()
                name = str(body.get("device_name") or body.get("name") or "Android").strip()[:64]

                def _tunnel_hint() -> str:
                    try:
                        tun = (
                            (RUNTIME / "mobile_tunnel_url.txt")
                            .read_text(encoding="utf-8", errors="replace")
                            .strip()
                            .lstrip("\ufeff")
                        )
                        return tun.rstrip("/") if tun.startswith("https://") else ""
                    except Exception:
                        return ""

                # Resume existing session token (never treat strategy code as auth)
                if resume_token:
                    data = _devices()
                    devices = data.setdefault("devices", {})
                    if resume_token in devices:
                        devices[resume_token]["name"] = name or devices[resume_token].get("name") or "Android"
                        devices[resume_token]["last_seen"] = _utc()
                        _save_devices(data)
                        return self._json(
                            200,
                            {
                                "ok": True,
                                "resumed": True,
                                "device_token": resume_token,
                                "api_base_hint": _tunnel_hint(),
                                "rules": _rules_payload(),
                                "strategy_code": STRATEGY_CODE,
                                "notify_channel": "discord+mobile",
                            },
                        )
                    return self._json(
                        401,
                        {"ok": False, "error": "جلسة غير صالحة — أعد الربط برمز التطبيق"},
                    )

                if code == STRATEGY_CODE or code in {"GS-GOLD80", "GOLD80"}:
                    return self._json(
                        403,
                        {
                            "ok": False,
                            "error": "GS-GOLD80 رمز الاستراتيجية وليس رمز ربط التطبيق",
                            "strategy_code": STRATEGY_CODE,
                            "hint": "استخدم رمز الربط المحقون في التطبيق",
                        },
                    )
                if code != PAIR_CODE.upper():
                    _push_alert("security", "محاولة ربط فاشلة", f"جهاز: {name}", level="warn")
                    return self._json(403, {"ok": False, "error": "رمز الربط غير صحيح"})
                token = secrets.token_urlsafe(24)
                data = _devices()
                data.setdefault("devices", {})[token] = {
                    "name": name,
                    "paired_at": _utc(),
                    "last_seen": _utc(),
                }
                data = _prune_devices(data, max_devices=8)
                _save_devices(data)
                _push_alert("pair", "تم ربط جهاز", f"{name} مربوط بالتطبيق", level="ok")
                return self._json(
                    200,
                    {
                        "ok": True,
                        "device_token": token,
                        "api_base_hint": _tunnel_hint(),
                        "rules": _rules_payload(),
                        "strategy_code": STRATEGY_CODE,
                        "notify_channel": "discord+mobile",
                    },
                )

            if not _auth_ok(self):
                return self._json(401, {"ok": False, "error": "unauthorized"})

            if path in ("/api/discord/config", "/api/discord"):
                result = _save_discord_config(body)
                return self._json(200 if result.get("ok") else 400, result)

            if path == "/api/heartbeat":
                token = self.headers.get("X-GS-Token") or ""
                data = _devices()
                if token in data.get("devices", {}):
                    data["devices"][token]["last_seen"] = _utc()
                    _save_devices(data)
                since = str(body.get("since") or "")
                items = _alerts()
                if since:
                    items = [a for a in items if str(a.get("ts", "")) > since]
                return self._json(
                    200,
                    {
                        "ok": True,
                        "status": _status(),
                        "alerts": items[-30:],
                        "rules": _rules_payload(),
                        "discord": _discord_cfg_public(),
                        "strategy_code": STRATEGY_CODE,
                    },
                )

            if path == "/api/act":
                act = str(body.get("act") or "")
                if act == "pause":
                    (RUNTIME / "user_stopped.flag").write_text("mobile-pause", encoding="utf-8")
                    _push_alert("control", "إيقاف من التطبيق", "تم طلب إيقاف الدخول", level="warn")
                    return self._json(200, {"ok": True, "paused": True})
                if act == "resume":
                    flag = RUNTIME / "user_stopped.flag"
                    if flag.exists():
                        flag.unlink()
                    _push_alert("control", "تشغيل من التطبيق", "تم استئناف الدخول", level="ok")
                    return self._json(200, {"ok": True, "paused": False})
                if act == "refresh":
                    _parse_signals_from_log()
                    _write_heartbeat({"reason": "refresh"})
                    return self._json(200, {"ok": True, "status": _status()})
                if act in {"close_all", "close_winners", "close_losers", "close_symbol"}:
                    mode = {
                        "close_all": "all",
                        "close_winners": "winners",
                        "close_losers": "losers",
                        "close_symbol": "symbol",
                    }[act]
                    symbol = str(body.get("symbol") or body.get("sym") or "").strip() or None
                    if act == "close_symbol" and not symbol:
                        return self._json(400, {"ok": False, "error": "symbol required", "closed": []})
                    result = _close_positions(mode, symbol=symbol if act == "close_symbol" else None)
                    _push_alert(
                        "control",
                        "إغلاق من التطبيق",
                        result.get("message") or act,
                        level="trade" if result.get("closed") else "info",
                    )
                    return self._json(200 if result.get("ok") else 500, result)
                if act == "panic":
                    confirm = str(body.get("confirm") or body.get("touch_lock_token") or "")
                    expected = (os.getenv("MOBILE_PANIC_CONFIRM") or "CONFIRM-PANIC").strip()
                    if confirm != expected:
                        return self._json(
                            403,
                            {
                                "ok": False,
                                "error": "touch_lock_required",
                                "hint": "أرسل confirm=MOBILE_PANIC_CONFIRM من .env",
                            },
                        )
                    result = _close_positions("all")
                    (RUNTIME / "user_stopped.flag").write_text("mobile-panic", encoding="utf-8")
                    (RUNTIME / "panic_touch_lock.flag").write_text("latched", encoding="utf-8")
                    _push_alert(
                        "control",
                        "طوارئ من التطبيق",
                        result.get("message") or "panic",
                        level="emergency",
                    )
                    result["paused"] = True
                    result["panic"] = True
                    return self._json(200 if result.get("ok") else 500, result)
                return self._json(400, {"ok": False, "error": f"unknown act {act}"})

            return self._json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc)})


def _watch_bot_log_for_alerts():
    """مراقبة ذيل السجل: صيغة البوت score N/10 + دخول تلقائي/أهداف."""
    log = ROOT / "storage" / "logs" / "bot_stdout.log"
    last_size = log.stat().st_size if log.exists() else 0
    # بذر الحالة الحالية حتى لا تُرسل تنبيهات قديمة عند الإقلاع
    try:
        for row in _parse_signals_from_log():
            _last_score_bucket[row["sym"]] = _score_bucket(int(row["score"]))
    except Exception:
        pass
    while True:
        try:
            time.sleep(3)
            if not log.exists():
                continue
            size = log.stat().st_size
            if size < last_size:
                last_size = 0
            if size == last_size:
                # حدّث النبض دورياً حتى لو لم يتغير الحجم قليلاً
                _parse_signals_from_log()
                continue
            with log.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(last_size)
                chunk = f.read()
                last_size = f.tell()
            for ln in chunk.splitlines():
                low = ln.lower()
                row = _parse_signal_line(ln)
                if row:
                    _maybe_alert_signal(row)
                    continue
                if "دخول تلقائي" in ln or ("auto" in low and "entry" in low):
                    _push_alert("auto_entry", "⚡ دخول تلقائي", ln[:180], level="trade")
                elif "هدف" in ln and ("1/3" in ln or "2/3" in ln or "3/3" in ln):
                    _push_alert("target", "🎯 هدف متدرج", ln[:180], level="trade")
                elif "kill switch" in low:
                    _push_alert("kill", "🚨 Kill Switch", ln[:180], level="emergency")
            # أعد بناء ملف النبض من آخر بلوك
            _parse_signals_from_log()
        except Exception:
            time.sleep(5)


def main():
    # تنبيه إقلاع
    try:
        _push_alert("boot", "Mobile API جاهز", f"المنفذ {PORT} · اربط الجهاز برمز {PAIR_CODE}", level="ok")
    except Exception as exc:
        print(f"BOOT_ALERT_FAIL:{exc}")
    # PID file لـ P0 watchdog
    try:
        import os as _os

        (RUNTIME / "mobile_api.pid").write_text(str(_os.getpid()), encoding="ascii")
    except Exception as exc:
        print(f"PID_WRITE_FAIL:{exc}")
    # تنظيف أجهزة قديمة عند الإقلاع
    try:
        data = _prune_devices(_devices(), max_devices=8)
        _save_devices(data)
    except Exception as exc:
        print(f"DEVICE_PRUNE_FAIL:{exc}")
    t = threading.Thread(target=_watch_bot_log_for_alerts, daemon=True)
    t.start()
    ThreadingHTTPServer.allow_reuse_address = True
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError as exc:
        # المنفذ مشغول — لا نخرج بصمت (كان يسبب exited 0 متكرر مع watchdog)
        print(f"MOBILE_API_BIND_FAIL:{PORT}:{exc}")
        raise SystemExit(75)
    print(f"MOBILE_API_LISTENING:{PORT}", flush=True)
    print(f"MOBILE_PAIR_CODE:{PAIR_CODE}", flush=True)
    print(f"MOBILE_API_TOKEN:{MASTER_TOKEN}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("MOBILE_API_STOP", flush=True)
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
