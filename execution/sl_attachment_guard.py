"""حارس إرفاق SL/TP بعد التعبئة — طبقة مضافة v1.1.2+.

يفرض: لا تذكرة حية بلا وقف خسارة. عند الفشل يُغلق الحجم فوراً.
"""

from __future__ import annotations

import logging

from config.settings import get_settings
from execution.models.order import Order, OrderSide

logger = logging.getLogger(__name__)


def ensure_fill_has_sl_or_close(
    order_manager,
    *,
    order: Order,
    symbol: str,
    side: OrderSide,
    amount: float,
    stop_loss: float | None,
    take_profit: float | None,
    reference_price: float,
) -> bool:
    """يتأكد من وجود SL بعد الفتح؛ إن تعذّر ذلك يغلق الحجم فوراً.

    يعيد True إذا كانت الحماية مؤكدة، False إذا أُغلق الأمر العاري.
    """
    try:
        settings = get_settings()
        if not bool(getattr(settings, "close_naked_tickets", True)):
            return True

        sl = float(stop_loss or 0.0)
        tp = float(take_profit or 0.0)
        if sl <= 0 or tp <= 0:
            logger.error(
                "تذكرة بلا SL/TP — إغلاق وقائي %s amount=%s sl=%s tp=%s",
                symbol,
                amount,
                sl,
                tp,
            )
            _emergency_close_fill(
                order_manager,
                symbol=symbol,
                side=side,
                amount=amount,
                reference_price=reference_price,
            )
            return False

        # Paper: الحماية برمجية عبر PositionManager — يكفي وجود قيم SL/TP
        if getattr(order, "is_paper", True) or settings.execution_mode != "live":
            order.protective_sl = sl
            order.protective_tp = tp
            order.stops_confirmed = True
            return True

        from config.runtime_profile import resolve_runtime_profile

        if resolve_runtime_profile(settings).uses_mt5:
            confirmed = _confirm_mt5_sl_tp(symbol, sl, tp)
        else:
            confirmed = bool(getattr(order, "stops_confirmed", False))
            if not confirmed:
                # محاولة إرفاق أخيرة على Binance قبل الإغلاق الوقائي
                try:
                    exchange = getattr(order_manager, "_last_exchange", None)
                    if exchange is None:
                        from data.exchange_client import get_exchange

                        exchange = get_exchange()
                    confirmed = bool(
                        order_manager._attach_binance_protective_stops(  # noqa: SLF001
                            exchange,
                            order,
                            stop_loss=sl,
                            take_profit=tp if tp > 0 else None,
                        )
                    )
                    order.stops_confirmed = confirmed
                except Exception as retry_exc:  # noqa: BLE001
                    logger.warning("إعادة إرفاق SL فشلت: %s", retry_exc)
                    confirmed = _confirm_binance_stops_flag(order)

        if confirmed:
            order.protective_sl = sl
            order.protective_tp = tp
            order.stops_confirmed = True
            return True

        logger.error(
            "فشل تأكيد SL/TP على المنصة — إغلاق وقائي %s amount=%s",
            symbol,
            amount,
        )
        try:
            from audit.execution_events import log_execution_event

            log_execution_event(
                "naked_ticket_closed",
                symbol=symbol,
                reason="تعذّر تأكيد SL/TP بعد الفتح",
                details={"amount": amount, "sl": sl, "tp": tp},
            )
        except Exception:
            pass
        _emergency_close_fill(
            order_manager,
            symbol=symbol,
            side=side,
            amount=amount,
            reference_price=reference_price,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_fill_has_sl_or_close فشل: %s", exc)
        try:
            _emergency_close_fill(
                order_manager,
                symbol=symbol,
                side=side,
                amount=amount,
                reference_price=reference_price,
            )
        except Exception:
            logger.exception("فشل الإغلاق الوقائي بعد خطأ الحارس")
        return False


def _confirm_mt5_sl_tp(symbol: str, stop_loss: float, take_profit: float) -> bool:
    try:
        from execution.mt5_bridge import get_mt5_bridge

        bridge = get_mt5_bridge()
        current_sl = bridge.get_position_sl(symbol)
        current_tp = bridge.get_position_tp(symbol)
        if (
            current_sl is not None
            and current_sl > 0
            and current_tp is not None
            and current_tp > 0
        ):
            return True
        # محاولة أخيرة لتعديل SL/TP
        bridge.modify_position_sl_tp(
            symbol, stop_loss=stop_loss, take_profit=take_profit
        )
        current_sl = bridge.get_position_sl(symbol)
        current_tp = bridge.get_position_tp(symbol)
        return (
            current_sl is not None
            and current_sl > 0
            and current_tp is not None
            and current_tp > 0
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("تأكيد MT5 SL/TP فشل (%s): %s", symbol, exc)
        return False


def _confirm_binance_stops_flag(order: Order) -> bool:
    return bool(getattr(order, "stops_confirmed", False))


def _emergency_close_fill(
    order_manager,
    *,
    symbol: str,
    side: OrderSide,
    amount: float,
    reference_price: float,
) -> None:
    if amount <= 0:
        return
    close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
    order_manager.create_market_order(
        symbol,
        close_side,
        amount,
        reference_price=reference_price,
        stop_loss=None,
        take_profit=None,
        allow_without_stops=True,
    )
