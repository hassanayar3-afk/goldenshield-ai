"""صندوق أسود — لقطة خسارة + تقرير تيليجرام + تعديل وزن مؤقت."""

from __future__ import annotations

import logging
from typing import Any

from intelligence.adaptive_weights import soften_component_after_loss
from intelligence.shadow_store import ShadowStore

logger = logging.getLogger(__name__)


def record_losing_trade_blackbox(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    reason: str,
    indicators: dict[str, Any] | None = None,
    orderbook: dict[str, Any] | None = None,
    alerts=None,
) -> int | None:
    if pnl >= 0:
        return None
    try:
        weights = soften_component_after_loss(reason=reason)
        db = ShadowStore()
        snap_id = db.insert_blackbox(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            reason=reason,
            indicators=indicators or {},
            orderbook=orderbook or {},
            weight_adjust=weights,
        )
        detail = (
            f"تمت خسارة الصفقة بسبب: {reason}\n"
            f"الدخول: {entry_price:.6f} → الخروج: {exit_price:.6f}\n"
            f"PnL: {pnl:.4f}\n"
            f"تم تعديل الوزن الفني مؤقتاً: {weights or '—'}\n"
            f"BlackBox#{snap_id}"
        )
        if alerts is not None:
            try:
                from operations.alert_dispatcher import AlertLevel

                alerts.dispatch(AlertLevel.WARNING, f"صندوق أسود — {symbol}", detail)
            except Exception as exc:  # noqa: BLE001
                logger.debug("blackbox telegram: %s", exc)
        logger.info("blackbox #%s %s pnl=%.4f", snap_id, symbol, pnl)
        return snap_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_losing_trade_blackbox: %s", exc)
        return None
