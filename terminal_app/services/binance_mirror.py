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

_STABLE_ASSETS = frozenset({"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI"})
_SNAP_TTL_SEC = 20.0
_SNAP_STALE_SEC = 120.0
_SNAP_BAN_TTL_SEC = 90.0
_snap_cache: dict = {"ts": 0.0, "data": None, "ban_until": 0.0}
_snap_lock = threading.Lock()
_snap_refreshing = False
_entry_cache: dict[str, tuple[float, float]] = {}
_ENTRY_TTL_SEC = 300.0
_FAST_DUST_USDT = 5.0


def load_snap_disk() -> dict | None:
    try:
        path = RUNTIME / "binance_snapshot.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("ok"):
            return data
    except Exception:
        return None
    return None


try:
    _disk_seed = load_snap_disk()
    if _disk_seed:
        _snap_cache["data"] = _disk_seed
        _snap_cache["ts"] = time.time() - (_SNAP_TTL_SEC + 1.0)
except Exception:
    pass


def account_from_status(st: dict | None = None) -> dict:
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
        "ts": aq.utc(),
    }
def sellable_amount(
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
def market_min_filters(ex, sym: str) -> tuple[float, float]:
    """Return (min_amount, min_notional/cost) for a market."""
    try:
        market = ex.market(sym) or {}
        limits = market.get("limits") or {}
        min_amt = float((limits.get("amount") or {}).get("min") or 0) or 0.0
        min_cost = float((limits.get("cost") or {}).get("min") or 0) or 0.0
        return min_amt, min_cost
    except Exception:
        return 0.0, 0.0


def entry_price_cached(ex, sym: str, qty: float, mark: float) -> float:
    """Avoid fetch_my_trades on every status poll — that was blowing past UI timeouts."""
    now = time.time()
    hit = _entry_cache.get(sym)
    if hit and (now - hit[0]) < _ENTRY_TTL_SEC and hit[1] > 0:
        return float(hit[1])
    entry = _avg_entry_price(ex, sym, qty) or mark
    if entry > 0:
        _entry_cache[sym] = (now, float(entry))
    return float(entry or mark or 0)
def live_prices(symbols: list[str]) -> dict[str, float]:
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
def binance_snapshot(force: bool = False) -> dict:
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
            "ts": aq.utc(),
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
            "ts": aq.utc(),
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
        sess = aq.load_json(sess_path, {})
        if sess.get("day") != day or not sess.get("start_equity"):
            sess = {
                "day": day,
                "start_equity": round(equity, 8),
                "updated_at": aq.utc(),
            }
            aq.save_json(sess_path, sess)
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
            "ts": aq.utc(),
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
            "ts": aq.utc(),
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
def convert_dust_assets(ex, assets: list[str]) -> dict:
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
def avg_entry_price(ex, sym: str, qty: float) -> float | None:
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
def close_positions(mode: str = "all", symbol: str | None = None) -> dict:
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
