"""إنشاء وإلغاء وتعديل الأوامر."""

from __future__ import annotations

import logging

from config.settings import get_settings
from core.exceptions import ExecutionError
from data.exchange_client import get_exchange
from execution.models.order import Order, OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    @property
    def orders(self) -> list[Order]:
        return list(self._orders.values())

    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        *,
        reference_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        allow_without_stops: bool = False,
    ) -> Order:
        if amount <= 0:
            raise ExecutionError(f"حجم الأمر غير صالح: {amount}")

        settings = get_settings()
        # طبقة صارمة: رفض إرسال أمر دخول حي بلا SL و TP إلا للإغلاق الوقائي
        require_sl = bool(getattr(settings, "require_sl_on_all_chunks", True))
        if (
            require_sl
            and not allow_without_stops
            and (
                stop_loss is None
                or float(stop_loss) <= 0
                or take_profit is None
                or float(take_profit) <= 0
            )
        ):
            raise ExecutionError(
                "Zero-SL/TP Denial: لا يُرسل أمر دخول بلا Stop Loss و Take Profit"
            )

        order = Order(
            symbol=symbol,
            side=side,
            amount=round(amount, 8),
            order_type=OrderType.MARKET,
            price=reference_price,
            is_paper=settings.execution_mode != "live",
            protective_sl=float(stop_loss) if stop_loss else None,
            protective_tp=float(take_profit) if take_profit else None,
        )
        self._orders[order.id] = order

        if settings.execution_mode == "live":
            self._submit_live_order(order, stop_loss=stop_loss, take_profit=take_profit)
        else:
            order.mark_filled(reference_price)
            if (
                stop_loss
                and float(stop_loss) > 0
                and take_profit
                and float(take_profit) > 0
            ):
                order.stops_confirmed = True

        return order

    def _submit_live_order(
        self,
        order: Order,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        settings = get_settings()
        from config.runtime_profile import resolve_runtime_profile

        if resolve_runtime_profile(settings).uses_mt5:
            self._submit_mt5_order(order, stop_loss=stop_loss, take_profit=take_profit)
            return

        if not settings.binance_api_key or not settings.binance_api_secret:
            order.mark_rejected()
            raise ExecutionError("مفاتيح Binance مطلوبة للتنفيذ الحي (أو فعّل MT5)")

        exchange = get_exchange()
        try:
            ccxt_side = order.side.value
            if order.order_type == OrderType.MARKET:
                result = exchange.create_order(
                    order.symbol,
                    "market",
                    ccxt_side,
                    order.amount,
                )
            else:
                result = exchange.create_order(
                    order.symbol,
                    "limit",
                    ccxt_side,
                    order.amount,
                    order.price,
                )
            order.id = str(result.get("id", order.id))
            fill_price = float(result.get("average") or result.get("price") or order.price or 0)
            order.mark_filled(fill_price)
            # طبقة مضافة: أوامر حماية بعد التعبئة (Binance لا يقبل SL مع market غالباً)
            if stop_loss is not None and float(stop_loss) > 0:
                attached = self._attach_binance_protective_stops(
                    exchange,
                    order,
                    stop_loss=float(stop_loss),
                    take_profit=float(take_profit) if take_profit else None,
                )
                order.stops_confirmed = attached
            else:
                order.stops_confirmed = False
        except ExecutionError:
            raise
        except Exception as exc:
            order.mark_rejected()
            logger.exception("فشل تنفيذ الأمر الحي")
            raise ExecutionError(f"فشل تنفيذ الأمر: {exc}") from exc

    def _attach_binance_protective_stops(
        self,
        exchange,
        order: Order,
        *,
        stop_loss: float,
        take_profit: float | None,
    ) -> bool:
        """يضع وقف خسارة (وهدف اختياري) بعد تعبئة أمر السوق على Binance."""
        try:
            close_side = "sell" if order.side == OrderSide.BUY else "buy"
            fill = float(order.fill_price or order.price or 0)
            if fill <= 0 or order.amount <= 0:
                return False

            # STOP_MARKET / STOP_LOSS — يختلف دعمها حسب السوق؛ فشل → False
            stop_ok = False
            tp_ok = False
            try:
                exchange.create_order(
                    order.symbol,
                    "STOP_MARKET",
                    close_side,
                    order.amount,
                    None,
                    {"stopPrice": stop_loss},
                )
                stop_ok = True
            except Exception:
                try:
                    # بديل شائع على Spot: STOP_LOSS_LIMIT قرب سعر الوقف
                    limit_price = stop_loss
                    exchange.create_order(
                        order.symbol,
                        "STOP_LOSS_LIMIT",
                        close_side,
                        order.amount,
                        limit_price,
                        {"stopPrice": stop_loss},
                    )
                    stop_ok = True
                except Exception as exc:
                    logger.warning(
                        "فشل أمر وقف Binance لـ %s: %s", order.symbol, exc
                    )
                    stop_ok = False

            if take_profit and take_profit > 0 and stop_ok:
                try:
                    exchange.create_order(
                        order.symbol,
                        "TAKE_PROFIT_MARKET",
                        close_side,
                        order.amount,
                        None,
                        {"stopPrice": take_profit},
                    )
                    tp_ok = True
                except Exception:
                    try:
                        exchange.create_order(
                            order.symbol,
                            "limit",
                            close_side,
                            order.amount,
                            take_profit,
                        )
                        tp_ok = True
                    except Exception as exc:
                        logger.warning(
                            "فشل أمر TP Binance لـ %s: %s", order.symbol, exc
                        )
                        tp_ok = False
            elif not take_profit or take_profit <= 0:
                tp_ok = False

            order.protective_sl = stop_loss
            order.protective_tp = take_profit
            # كلاهما إلزامي — فشل أي منهما = غير مؤكد
            return bool(stop_ok and tp_ok)
        except Exception as exc:  # noqa: BLE001
            logger.warning("_attach_binance_protective_stops: %s", exc)
            return False
    def _submit_mt5_order(
        self,
        order: Order,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        from execution.mt5_bridge import get_mt5_bridge

        bridge = get_mt5_bridge()
        # بروتوكول صارم: دائماً نمرّر SL/TP مع أمر الدخول — لا فتح عاري ثم تعديل
        sl = float(stop_loss) if stop_loss and float(stop_loss) > 0 else None
        tp = float(take_profit) if take_profit and float(take_profit) > 0 else None
        try:
            result = bridge.place_market(
                order.symbol,
                side=order.side.value,
                amount=order.amount,
                stop_loss=sl,
                take_profit=tp,
            )
        except Exception as exc:
            order.mark_rejected()
            logger.exception("فشل تنفيذ أمر MT5")
            raise ExecutionError(f"فشل أمر MT5: {exc}") from exc

        order.id = f"mt5-{result.ticket}"
        order.mark_filled(result.price)
        order.protective_sl = sl
        order.protective_tp = tp

        # تأكيد فعلي على المنصة — ليس نية فقط
        confirmed = True
        if sl is not None or tp is not None:
            live_sl = bridge.get_position_sl(order.symbol)
            live_tp = bridge.get_position_tp(order.symbol)
            if live_sl is None or live_sl <= 0 or live_tp is None or live_tp <= 0:
                try:
                    bridge.modify_position_sl_tp(
                        order.symbol, stop_loss=sl, take_profit=tp
                    )
                    live_sl = bridge.get_position_sl(order.symbol)
                    live_tp = bridge.get_position_tp(order.symbol)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("تعديل SL/TP بعد الفتح فشل: %s", exc)
            confirmed = (
                live_sl is not None
                and live_sl > 0
                and live_tp is not None
                and live_tp > 0
            )
            if not confirmed:
                # إغلاق فوري — ممنوع ترك تذكرة عارية
                try:
                    close_side = (
                        OrderSide.SELL
                        if order.side == OrderSide.BUY
                        else OrderSide.BUY
                    )
                    bridge.place_market(
                        order.symbol,
                        side=close_side.value,
                        amount=order.amount,
                    )
                except Exception:
                    logger.exception(
                        "فشل إغلاق تذكرة عارية بعد MT5 %s", order.symbol
                    )
                order.stops_confirmed = False
                order.mark_rejected()
                raise ExecutionError(
                    "Zero-SL/TP Denial: فُتح المركز بلا SL/TP مؤكدين — أُغلق فوراً"
                )

        order.stops_confirmed = confirmed
        logger.info(
            "MT5 filled %s %s vol=%s @ %s ticket=%s sl=%s tp=%s confirmed=%s",
            order.side.value,
            result.symbol,
            result.volume,
            result.price,
            result.ticket,
            sl,
            tp,
            confirmed,
        )

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False

        settings = get_settings()
        if settings.execution_mode == "live":
            exchange = get_exchange()
            try:
                exchange.cancel_order(order_id, order.symbol)
            except Exception as exc:
                raise ExecutionError(f"فشل إلغاء الأمر: {exc}") from exc

        order.mark_cancelled()
        return True

    def modify_order(
        self,
        order_id: str,
        *,
        amount: float | None = None,
        price: float | None = None,
    ) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise ExecutionError(f"الأمر غير موجود: {order_id}")
        if order.status == OrderStatus.FILLED:
            raise ExecutionError("لا يمكن تعديل أمر منفّذ")
        if order.status in {OrderStatus.CANCELLED, OrderStatus.REJECTED}:
            raise ExecutionError(f"لا يمكن تعديل أمر بحالة {order.status.value}")

        if amount is not None:
            if amount <= 0:
                raise ExecutionError(f"حجم الأمر غير صالح: {amount}")
            order.amount = round(amount, 8)

        if price is not None:
            if price <= 0:
                raise ExecutionError(f"سعر الأمر غير صالح: {price}")
            order.price = price
            order.order_type = OrderType.LIMIT

        settings = get_settings()
        if settings.execution_mode == "live" and order.is_active:
            exchange = get_exchange()
            try:
                params: dict = {}
                if amount is not None:
                    params["amount"] = order.amount
                if price is not None:
                    params["price"] = order.price
                exchange.edit_order(
                    order_id,
                    order.symbol,
                    order.order_type.value,
                    order.side.value,
                    order.amount,
                    order.price,
                    params,
                )
            except Exception as exc:
                raise ExecutionError(f"فشل تعديل الأمر: {exc}") from exc

        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def clear(self) -> None:
        self._orders.clear()
