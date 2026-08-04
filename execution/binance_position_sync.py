"""مزامنة أرصدة Binance Spot → مراكز البوت (طبقة مضافة).

عندما يُفتح شراء على المنصة لكن قاعدة البيانات فارغة (مثلاً فشل تأكيد SL
ثم بقي الرصيد)، تظهر المراكز في الداشبورد وتُدار.

مصدر الحقيقة الوحيد للوحة: get_live_open_positions_ssot()
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from config.settings import get_settings
from execution.models.order import OrderSide
from execution.models.trade import Position
from execution.sl_tp_calculator import calculate_sl_tp

logger = logging.getLogger(__name__)

_STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "EUR", "USD"}
_DUST = {
    "BTC": 1e-6,
    "ETH": 1e-5,
    "BNB": 1e-4,
    "SOL": 1e-3,
    "ADA": 1.0,
    "XRP": 1.0,
    "LTC": 1e-3,
    "DEFAULT": 0.01,
}
_ALLOWED_EXTRA = {
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "ADA/USDT",
    "XRP/USDT",
    "LTC/USDT",
    "DOT/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "ATOM/USDT",
    "DOGE/USDT",
    "TRX/USDT",
    "POL/USDT",
}


def _dust(asset: str) -> float:
    return float(_DUST.get(asset.upper(), _DUST["DEFAULT"]))


def _min_exchange_notional() -> float:
    try:
        min_notional = float(os.getenv("PROJECT_MIN_EXCHANGE_NOTIONAL", "5") or 5)
    except (TypeError, ValueError):
        min_notional = 5.0
    return max(min_notional, 5.0)


def _binance_live_enabled(settings) -> bool:
    if str(getattr(settings, "execution_backend", "binance")).lower() != "binance":
        return False
    if bool(getattr(settings, "binance_demo_trading", False)):
        return True
    if settings.execution_mode == "live":
        return True
    return False


def _symbol_allowed(symbol: str, pairs: set[str]) -> bool:
    if symbol in pairs or symbol in _ALLOWED_EXTRA:
        return True
    asset_u = symbol.split("/", 1)[0].upper()
    return any(str(p).upper().startswith(f"{asset_u}/") for p in pairs)


def discover_live_spot_holdings(exchange=None) -> dict[str, dict[str, float]]:
    """استعلام فوري من Binance — أرصدة تُعدّ صفقات مفتوحة حقيقية فقط.

    يستبعد المستقرات والغبار الكمّي والغبار بالقيمة (< حد المنصة ~5$).
    يُرجع: {symbol: {"qty": ..., "price": ..., "notional": ...}}
    """
    settings = get_settings()
    if not _binance_live_enabled(settings):
        return {}

    from data.exchange_client import get_exchange

    exchange = exchange or get_exchange()
    bal = exchange.fetch_balance() or {}
    total = bal.get("total") or {}
    pairs = set(getattr(settings, "trading_pairs", ()) or ())
    min_notional = _min_exchange_notional()
    out: dict[str, dict[str, float]] = {}

    for asset, qty_raw in total.items():
        asset_u = str(asset).upper()
        if asset_u in _STABLES:
            continue
        try:
            qty = float(qty_raw or 0.0)
        except (TypeError, ValueError):
            continue
        if qty <= _dust(asset_u):
            continue
        symbol = f"{asset_u}/USDT"
        if not _symbol_allowed(symbol, pairs):
            continue
        try:
            t = exchange.fetch_ticker(symbol)
            px = float(t.get("last") or t.get("close") or 0.0)
        except Exception:
            px = 0.0
        if px <= 0:
            continue
        notional = qty * px
        if notional + 1e-9 < min_notional:
            continue
        out[symbol] = {"qty": qty, "price": px, "notional": notional}
    return out


def _reconcile_manager_to_holdings(executor, holdings: dict[str, dict[str, float]]) -> list[str]:
    """يوفّق الذاكرة المحلية لتطابق حيازات المنصة الحقيقية فقط."""
    changed: list[str] = []
    settings = get_settings()
    from data.exchange_client import get_exchange

    exchange = get_exchange()
    bal = exchange.fetch_balance() or {}
    free = bal.get("free") or {}
    live_symbols = set(holdings.keys())

    for symbol, meta in holdings.items():
        qty = float(meta.get("qty") or 0.0)
        if qty <= 0:
            continue
        if executor.position_manager.has(symbol):
            pos = executor.position_manager.get(symbol)
            if pos is not None and abs(float(pos.amount) - qty) / max(qty, 1e-12) > 0.05:
                pos.amount = qty
                try:
                    executor._persist_open_trade(pos)  # noqa: SLF001
                except Exception:
                    pass
                changed.append(f"{symbol}:qty")
            continue

        asset_u = symbol.split("/", 1)[0].upper()
        entry = _estimate_entry(exchange, symbol, qty, free.get(asset_u))
        if entry <= 0:
            entry = float(meta.get("price") or 0.0)
        if entry <= 0:
            continue
        sl, tp = calculate_sl_tp(entry, side="buy")
        score = _lookup_signal_score(executor, symbol)
        position = Position(
            symbol=symbol,
            side=OrderSide.BUY,
            entry_price=entry,
            amount=qty,
            stop_loss=sl,
            take_profit=tp,
            opened_at=datetime.now(timezone.utc),
            is_paper=bool(getattr(settings, "binance_demo_trading", False)),
            signal_score=int(score or 0),
            entry_filters="synced_from_binance_balance",
        )
        executor.position_manager.add(position)
        try:
            executor._persist_open_trade(position)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            logger.debug("persist synced position: %s", exc)
        changed.append(symbol)
        logger.info(
            "مزامنة مركز من Binance: %s amount=%.8f entry≈%.6f",
            symbol,
            qty,
            entry,
        )

    # أي مركز محلي ليس ضمن الحيازات الحقيقية (بما فيها الغبار) → إغلاق شبحي
    for pos in list(executor.position_manager.all()):
        if pos.symbol in live_symbols:
            continue
        exit_px, pnl = _reconcile_ghost_close(exchange, pos)
        try:
            executor.position_manager.remove(pos.symbol)
            if hasattr(executor, "risk") and executor.risk is not None:
                try:
                    executor.risk.record_closed_trade(pnl)
                except Exception:
                    pass
            executor._persist_close_trade(pos.id, exit_px, pnl)  # noqa: SLF001
            changed.append(f"{pos.symbol}:closed_ghost")
            logger.warning(
                "إغلاق شبحي/غبار بالمزامنة: %s exit≈%.6f pnl=%.4f",
                pos.symbol,
                exit_px,
                pnl,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ghost close %s: %s", pos.symbol, exc)
            try:
                executor.position_manager.remove(pos.symbol)
            except Exception:
                pass

    return changed


def get_live_open_positions_ssot(executor) -> tuple[list, int]:
    """مصدر الحقيقة الوحيد (Single Source of Truth) للمراكز المفتوحة.

    - استعلام فوري من Binance Spot
    - نفس الفلتر للعدد وللقائمة
    - توفيق الذاكرة المحلية لتطابق المنصة
    يُرجع (قائمة المراكز للعرض, العدد) — متطابقان دائماً مع المنصة.
    """
    try:
        settings = get_settings()
        if not _binance_live_enabled(settings):
            positions = list(executor.position_manager.all())
            return positions, len(positions)

        holdings = discover_live_spot_holdings()
        _reconcile_manager_to_holdings(executor, holdings)

        positions: list = []
        for symbol in sorted(holdings.keys()):
            pos = executor.position_manager.get(symbol)
            if pos is not None:
                try:
                    pos.amount = float(holdings[symbol]["qty"])
                except Exception:
                    pass
                positions.append(pos)

        count = len(holdings)
        if len(positions) != count:
            logger.debug(
                "ssot list/count soft mismatch list=%s count=%s",
                len(positions),
                count,
            )
        return positions, count
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_live_open_positions_ssot: %s", exc)
        return [], 0


def live_mirror_sync_from_binance(executor) -> list[str]:
    """مرآة حية — توفّق الذاكرة عبر مصدر الحقيقة الوحيد."""
    try:
        holdings = discover_live_spot_holdings()
        return _reconcile_manager_to_holdings(executor, holdings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("live_mirror_sync_from_binance: %s", exc)
        return []


def count_live_spot_positions_from_binance(
    executor: object | None = None,
    *,
    exchange_only: bool = False,
) -> int:
    """عدد المراكز المفتوحة حسب Binance — عبر SSoT عند توفر executor."""
    if executor is not None:
        try:
            _, count = get_live_open_positions_ssot(executor)
            return int(count)
        except Exception as exc:  # noqa: BLE001
            logger.debug("count via ssot: %s", exc)
            if exchange_only:
                return 0
    try:
        return len(discover_live_spot_holdings())
    except Exception as exc:  # noqa: BLE001
        logger.debug("count_live_spot_positions_from_binance: %s", exc)
        if exchange_only:
            return 0
        if executor is not None:
            try:
                return int(executor.position_manager.count())
            except Exception:
                return 0
        return 0


def sync_binance_spot_positions(executor) -> list[str]:
    """يعيد قائمة الرموز التي أُضيفت/حُدّثت/أُغلقت بالمزامنة."""
    try:
        settings = get_settings()
        if not _binance_live_enabled(settings):
            return []
        holdings = discover_live_spot_holdings()
        return _reconcile_manager_to_holdings(executor, holdings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_binance_spot_positions: %s", exc)
        return []


def _reconcile_ghost_close(exchange, pos) -> tuple[float, float]:
    """يستنتج سعر الخروج وPnL من آخر بيع على المنصة."""
    exit_px = float(pos.entry_price or 0.0)
    try:
        trades = exchange.fetch_my_trades(pos.symbol, limit=30) or []
        sells = [t for t in trades if str(t.get("side", "")).lower() == "sell"]
        if sells:
            last = sells[-1]
            exit_px = float(last.get("price") or exit_px)
    except Exception:
        try:
            t = exchange.fetch_ticker(pos.symbol)
            exit_px = float(t.get("last") or t.get("close") or exit_px)
        except Exception:
            pass
    amount = float(pos.amount or 0.0)
    entry = float(pos.entry_price or 0.0)
    side = getattr(pos.side, "value", str(pos.side)).lower()
    if side == "buy":
        pnl = (exit_px - entry) * amount
    else:
        pnl = (entry - exit_px) * amount
    return exit_px, float(pnl)


def _lookup_signal_score(executor, symbol: str) -> int:
    """حاول استرجاع قوة الدخول من آخر صفقة محفوظة لنفس الزوج."""
    try:
        repo = getattr(executor, "trade_repo", None)
        if repo is None:
            return 0
        with repo._db.connect() as conn:  # noqa: SLF001
            row = conn.execute(
                """
                SELECT signal_score FROM trades
                WHERE symbol = ? AND COALESCE(signal_score, 0) > 0
                ORDER BY opened_at DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["signal_score"] if hasattr(row, "keys") else row[0] or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("lookup signal_score %s: %s", symbol, exc)
        return 0


def _estimate_entry(exchange, symbol: str, qty: float, free_qty) -> float:
    """متوسط تكلفة تقريبي من آخر صفقات الشراء."""
    try:
        trades = exchange.fetch_my_trades(symbol, limit=30) or []
        buys = [t for t in trades if str(t.get("side", "")).lower() == "buy"]
        if not buys:
            return 0.0
        remain = float(qty)
        cost = 0.0
        filled = 0.0
        for t in reversed(buys):
            amt = float(t.get("amount") or 0)
            px = float(t.get("price") or 0)
            if amt <= 0 or px <= 0:
                continue
            take = min(remain, amt)
            cost += take * px
            filled += take
            remain -= take
            if remain <= 1e-12:
                break
        if filled > 0:
            return cost / filled
    except Exception as exc:  # noqa: BLE001
        logger.debug("estimate entry %s: %s", symbol, exc)
    return 0.0


def format_holdings_report(executor) -> str:
    """نص عربي سريع لمراكز الذاكرة + ملاحظة المزامنة."""
    lines = ["📂 <b>المراكز الحالية</b>", ""]
    try:
        positions, count = get_live_open_positions_ssot(executor)
    except Exception:
        positions = list(executor.position_manager.all())
        count = len(positions)
    if not positions:
        lines.append("لا توجد مراكز مفتوحة على المنصة حالياً.")
        return "\n".join(lines)
    for p in positions:
        lines.append(
            f"• <b>{p.symbol}</b> {p.side.value.upper()} "
            f"كمية {p.amount:.6g} @ {p.entry_price:.6g} "
            f"| SL {p.stop_loss:.6g} | TP {p.take_profit:.6g}"
        )
    lines.append("")
    lines.append(f"المجموع: {count} مركز")
    return "\n".join(lines)
