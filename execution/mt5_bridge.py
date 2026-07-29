"""جسر MetaTrader 5 (XM) — يعمل فقط على Windows مع طرفية MT5 مفتوحة."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.exceptions import ExecutionError

logger = logging.getLogger(__name__)

# رموز المشروع (Binance) → رموز شائعة على XM MT5
DEFAULT_SYMBOL_MAP: dict[str, str] = {
    "BTC/USDT": "BTCUSD",
    "ETH/USDT": "ETHUSD",
    "BNB/USDT": "BNBUSD",
    "SOL/USDT": "SOLUSD",
    "XRP/USDT": "XRPUSD",
    "ADA/USDT": "ADAUSD",
    "LINK/USDT": "LINKUSD",
    "AVAX/USDT": "AVAXUSD",
}


@dataclass(frozen=True)
class MT5OrderResult:
    ticket: int
    symbol: str
    volume: float
    price: float
    retcode: int


def is_windows() -> bool:
    return sys.platform.startswith("win")


def map_symbol(binance_symbol: str) -> str:
    try:
        from operations.symbol_registry import get_symbol_registry

        return get_symbol_registry().mt5_symbol_for(binance_symbol)
    except Exception:
        return DEFAULT_SYMBOL_MAP.get(binance_symbol, binance_symbol.replace("/", ""))


DEFAULT_MT5_PATHS = (
    Path(r"C:\Program Files\XM Global MT5\terminal64.exe"),
    Path(r"C:\Program Files\XM MT5\terminal64.exe"),
    Path(r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"),
    Path(r"C:\Program Files\MetaTrader 5\terminal64.exe"),
    Path(r"C:\Program Files (x86)\XM Global MT5\terminal64.exe"),
    Path(r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"),
)


def _mt5_process_running() -> bool:
    """هل طرفية MT5 شغّالة الآن؟"""
    try:
        import subprocess

        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            text=True,
            errors="replace",
            timeout=10,
        )
        return "terminal64.exe" in out.lower()
    except Exception:
        return False


def _candidate_terminal_paths() -> list[str]:
    custom = os.getenv("MT5_TERMINAL_PATH", "").strip()
    paths: list[str] = []
    if custom:
        paths.append(custom)
    for candidate in DEFAULT_MT5_PATHS:
        if candidate.exists():
            paths.append(str(candidate))
    # بدون تكرار مع الحفاظ على الترتيب
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


class MT5Bridge:
    """واجهة رفيعة حول حزمة MetaTrader5."""

    def __init__(self) -> None:
        self._mt5: Any | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _import_mt5(self) -> Any:
        if not is_windows():
            raise ExecutionError(
                "MetaTrader5 يتطلب Windows + طرفية MT5. Contabo الحالي Linux — اشترِ Windows VPS."
            )
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as exc:
            raise ExecutionError(
                "حزمة MetaTrader5 غير مثبتة. على Windows: pip install MetaTrader5"
            ) from exc
        return mt5

    def _initialize_terminal(self, mt5: Any) -> None:
        """يربط MT5 — يجرب path+login أولاً (الحل الأقوى لـ Authorization -6)."""
        import time

        settings = get_settings()
        last_error: Any = None
        terminal_paths = _candidate_terminal_paths()
        login = int(settings.mt5_login) if settings.mt5_login else 0
        password = settings.mt5_password or ""
        servers = []
        for server in (
            settings.mt5_server,
            "XMGlobal-MT5 11",
            "XMGlobal-MT5 10",
            "XM.COM-MT5",
            "XMGlobal-MT5",
        ):
            if server and server not in servers:
                servers.append(server)

        # 1) الأقوى: initialize مع مسار + بيانات الدخول
        for path in terminal_paths:
            for server in servers:
                try:
                    if mt5.initialize(
                        path=path,
                        login=login,
                        password=password,
                        server=server,
                    ):
                        info = mt5.account_info()
                        if info is not None:
                            logger.info(
                                "MT5 init path+login server=%s login=%s path=%s",
                                server,
                                info.login,
                                path,
                            )
                            return
                    last_error = mt5.last_error()
                    logger.warning("MT5 init failed path=%s server=%s err=%s", path, server, last_error)
                    try:
                        mt5.shutdown()
                    except Exception:
                        pass
                except Exception as exc:
                    last_error = exc
                    logger.warning("MT5 init exception path=%s server=%s: %s", path, server, exc)

        # 2) مسار فقط (يلتصق بالطرفية المفتوحة)
        for path in terminal_paths:
            if mt5.initialize(path=path):
                info = mt5.account_info()
                if info is not None:
                    logger.info("MT5 attached via path=%s login=%s", path, info.login)
                    return
            last_error = mt5.last_error()
            try:
                mt5.shutdown()
            except Exception:
                pass

        # 3) attach بدون مسار
        for attempt in range(1, 6):
            if mt5.initialize():
                info = mt5.account_info()
                if info is not None:
                    logger.info("MT5 attached default attempt=%s login=%s", attempt, info.login)
                    return
            last_error = mt5.last_error()
            time.sleep(2)

        raise ExecutionError(
            f"فشل ربط MT5: {last_error}\n"
            "تحقق: كلمة مرور التداول (Master) في .env + MT5 مفتوح + Disable Python API بدون علامة"
        )

    def connect(self) -> None:
        settings = get_settings()
        if not settings.mt5_enabled:
            raise ExecutionError("MT5_ENABLED=false — لم يُفعَّل الربط بعد")
        if not settings.mt5_login or not settings.mt5_password or not settings.mt5_server:
            raise ExecutionError("أكمل MT5_LOGIN و MT5_PASSWORD و MT5_SERVER في .env")

        mt5 = self._import_mt5()
        self._initialize_terminal(mt5)

        info = mt5.account_info()
        if info is not None and str(info.login) == str(settings.mt5_login):
            self._mt5 = mt5
            self._connected = True
            logger.info(
                "MT5 using open terminal | login=%s server=%s balance=%s",
                info.login,
                getattr(info, "server", settings.mt5_server),
                getattr(info, "balance", "?"),
            )
            return

        # مبتدئ: إذا الطرفية مفتوحة على XM بأي حساب — نستخدمها ولا نكسر الدخول اليدوي
        if info is not None:
            server = str(getattr(info, "server", "") or "")
            if "XM" in server.upper() or "XM" in str(settings.mt5_server or "").upper():
                self._mt5 = mt5
                self._connected = True
                logger.warning(
                    "MT5 attached to open XM session login=%s server=%s "
                    "(تحقق أن الحساب هو المطلوب في .env: %s)",
                    info.login,
                    server,
                    settings.mt5_login,
                )
                return

        servers_to_try: list[str] = []
        for server in (
            "XM.COM-MT5",
            settings.mt5_server,
            "XMGlobal-MT5 10",
            "XMGlobal-MT5 11",
            "XMGlobal-MT5",
        ):
            if server and server not in servers_to_try:
                servers_to_try.append(server)

        authorized = False
        for server in servers_to_try:
            if mt5.login(
                int(settings.mt5_login),
                password=settings.mt5_password,
                server=server,
            ):
                authorized = True
                logger.info("MT5 logged in via server=%s", server)
                break

        if not authorized:
            info = mt5.account_info()
            if info is not None and (
                str(info.login) == str(settings.mt5_login)
                or "XM" in str(getattr(info, "server", "") or "").upper()
            ):
                authorized = True
            else:
                err = mt5.last_error()
                raise ExecutionError(
                    f"فشل تسجيل دخول XM/MT5: {err}\n"
                    "ماذا تفعل أنت:\n"
                    "1) افتح برنامج XM MetaTrader 5\n"
                    "2) سجّل دخول حسابك يدوياً (مثل 345814054)\n"
                    "3) السيرفر: XM.COM-MT5\n"
                    "4) من Tools → Options → Expert Advisors فعّل Allow Algorithmic Trading\n"
                    "5) اترك MT5 مفتوحاً ثم 00_STOP و 00_START"
                )

        self._mt5 = mt5
        self._connected = True
        info = mt5.account_info()
        logger.info(
            "MT5 connected | login=%s server=%s balance=%s",
            settings.mt5_login,
            getattr(info, "server", settings.mt5_server) if info else settings.mt5_server,
            getattr(info, "balance", "?") if info else "?",
        )

    def ensure_connected(self) -> Any:
        if self._connected and self._mt5 is not None:
            try:
                info = self._mt5.account_info()
                if info is not None:
                    return self._mt5
            except Exception as exc:
                logger.warning("MT5 session stale — reconnect: %s", exc)
            self._connected = False
            self._mt5 = None
        self.connect()
        assert self._mt5 is not None
        return self._mt5

    def shutdown(self) -> None:
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            except Exception:
                logger.exception("MT5 shutdown error")
        self._mt5 = None
        self._connected = False

    def account_balance(self) -> float:
        mt5 = self.ensure_connected()
        info = mt5.account_info()
        if info is None:
            raise ExecutionError(f"تعذر قراءة رصيد MT5: {mt5.last_error()}")
        return float(info.balance)

    def resolve_symbol(self, binance_symbol: str) -> str:
        mt5 = self.ensure_connected()
        candidates: list[str] = []
        primary = map_symbol(binance_symbol)
        candidates.append(primary)
        if primary.startswith("#"):
            candidates.append(primary.lstrip("#"))
        if binance_symbol.startswith("STOCK/"):
            ticker = binance_symbol.split("/", 1)[1]
            candidates.extend([f"#{ticker}", ticker, f"{ticker}.US", f"{ticker}m"])
        if binance_symbol.startswith("FOREX/"):
            pair = binance_symbol.split("/", 1)[1]
            candidates.append(pair)
            for suffix in ("#", "m", ".i", ".pro", ".a"):
                candidates.append(f"{pair}{suffix}")
            # بحث في قائمة الرموز إن لم يُعثر بالأسماء المباشرة
            try:
                for item in mt5.symbols_get() or []:
                    name = str(item.name)
                    if pair in name.replace(".", "").replace("#", "").upper() or name.upper() == pair:
                        candidates.append(name)
            except Exception:
                pass

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            info = mt5.symbol_info(candidate)
            if info is None:
                if mt5.symbol_select(candidate, True):
                    info = mt5.symbol_info(candidate)
            if info is None:
                continue
            if not info.visible:
                mt5.symbol_select(candidate, True)
            return candidate
        raise ExecutionError(f"رمز MT5 غير موجود لـ {binance_symbol} — جرّب /add أو /sync_mt5")

    def volume_from_amount(
        self,
        mt5_symbol: str,
        amount: float,
        *,
        entry_price: float | None = None,
        stop_loss: float | None = None,
    ) -> float:
        """يحوّل الكمية إلى لوت MT5 — فوركس/أسهم تُحسب من المخاطر لا من وحدات كريبتو."""
        mt5 = self.ensure_connected()
        info = mt5.symbol_info(mt5_symbol)
        if info is None:
            raise ExecutionError(f"لا معلومات حجم لـ {mt5_symbol}")
        step = float(info.volume_step or 0.01)
        vmin = float(info.volume_min or step)
        vmax = float(info.volume_max or 100.0)

        volume: float
        looks_like_lots = 0 < amount <= max(1.0, vmin * 50)
        if looks_like_lots and amount <= vmax:
            volume = amount
        elif entry_price and stop_loss and abs(entry_price - stop_loss) > 0:
            volume = self._lots_from_risk(mt5_symbol, entry_price, stop_loss, info)
        else:
            # حماية: لا نرسل مئات اللوتات من حاسبة العملات على أزواج فوركس
            volume = vmin

        volume = round(volume / step) * step if step > 0 else volume
        if volume < vmin:
            volume = vmin
        volume = min(max(volume, vmin), vmax)
        decimals = max(0, str(step)[::-1].find("."))
        return round(volume, decimals if decimals > 0 else 2)

    def _lots_from_risk(
        self,
        mt5_symbol: str,
        entry_price: float,
        stop_loss: float,
        info: Any,
    ) -> float:
        """لوت تقريبي بحيث خسارة SL ≈ مخاطرة الحساب الافتراضية."""
        from risk.compound_growth import risk_amount

        mt5 = self.ensure_connected()
        account = mt5.account_info()
        balance = float(account.balance) if account is not None else 1000.0
        risk_money = max(risk_amount(balance), 0.01)

        tick_size = float(getattr(info, "trade_tick_size", 0) or 0) or float(
            getattr(info, "point", 0) or 0
        )
        tick_value = float(getattr(info, "trade_tick_value", 0) or 0)
        sl_dist = abs(entry_price - stop_loss)
        if tick_size <= 0 or tick_value <= 0 or sl_dist <= 0:
            return float(info.volume_min or 0.01)

        ticks = sl_dist / tick_size
        loss_per_lot = ticks * tick_value
        if loss_per_lot <= 0:
            return float(info.volume_min or 0.01)
        return risk_money / loss_per_lot

    def _filling_modes(self, mt5: Any, info: Any) -> list[int]:
        mode = int(getattr(info, "filling_mode", 0) or 0)
        ordered: list[int] = []
        # FLAGS: FOK=1 IOC=2 RETURN=4
        mapping = (
            (1, mt5.ORDER_FILLING_FOK),
            (2, mt5.ORDER_FILLING_IOC),
            (4, mt5.ORDER_FILLING_RETURN),
        )
        for flag, filling in mapping:
            if mode & flag:
                ordered.append(filling)
        for filling in (
            mt5.ORDER_FILLING_IOC,
            mt5.ORDER_FILLING_FOK,
            mt5.ORDER_FILLING_RETURN,
        ):
            if filling not in ordered:
                ordered.append(filling)
        return ordered

    def _normalize_stops(
        self,
        info: Any,
        price: float,
        *,
        stop_loss: float | None,
        take_profit: float | None,
        is_buy: bool,
    ) -> tuple[float | None, float | None]:
        point = float(getattr(info, "point", 0) or 0) or 0.00001
        stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
        min_dist = max(stops_level * point, point * 10)
        sl = float(stop_loss) if stop_loss and stop_loss > 0 else None
        tp = float(take_profit) if take_profit and take_profit > 0 else None
        if sl is not None:
            if is_buy and price - sl < min_dist:
                sl = price - min_dist
            elif (not is_buy) and sl - price < min_dist:
                sl = price + min_dist
        if tp is not None:
            if is_buy and tp - price < min_dist:
                tp = price + min_dist
            elif (not is_buy) and price - tp < min_dist:
                tp = price - min_dist
        return sl, tp

    def place_market(
        self,
        binance_symbol: str,
        *,
        side: str,
        amount: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> MT5OrderResult:
        mt5 = self.ensure_connected()
        symbol = self.resolve_symbol(binance_symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            raise ExecutionError(f"لا معلومات رمز لـ {symbol}")
        if not info.visible:
            mt5.symbol_select(symbol, True)

        trade_mode = int(getattr(info, "trade_mode", 4) or 4)
        # 0 disabled, 1 longonly, 2 shortonly, 3 closeonly, 4 full
        if trade_mode == 0:
            raise ExecutionError(f"التداول معطّل على الرمز {symbol} في المنصة")

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise ExecutionError(f"لا سعر حي لـ {symbol}")

        is_buy = side.lower() in {"buy", "long"}
        if trade_mode == 1 and not is_buy:
            raise ExecutionError(f"{symbol} يسمح بالشراء فقط")
        if trade_mode == 2 and is_buy:
            raise ExecutionError(f"{symbol} يسمح بالبيع فقط")
        if trade_mode == 3:
            raise ExecutionError(f"{symbol} للإغلاق فقط حالياً")

        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = float(tick.ask if is_buy else tick.bid)
        volume = self.volume_from_amount(
            symbol,
            amount,
            entry_price=price,
            stop_loss=stop_loss,
        )
        sl, tp = self._normalize_stops(
            info, price, stop_loss=stop_loss, take_profit=take_profit, is_buy=is_buy
        )

        # بروتوكول صارم: إن وُجد SL/TP مطلوبان — لا فتح عاري أبداً
        require_stops = sl is not None and tp is not None
        if (stop_loss is not None and float(stop_loss) > 0) or (
            take_profit is not None and float(take_profit) > 0
        ):
            if sl is None or tp is None:
                raise ExecutionError(
                    "Zero-SL/TP Denial: لا يُفتح مركز MT5 بلا Stop Loss و Take Profit معاً"
                )
            require_stops = True

        fillings = self._filling_modes(mt5, info)
        last_error = "فشل order_send"
        for filling in fillings:
            request: dict[str, Any] = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 80,
                "magic": 20260714,
                "comment": "GoldenShield",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            if require_stops:
                request["sl"] = sl
                request["tp"] = tp

            result = mt5.order_send(request)
            if result is None:
                last_error = f"order_send فشل: {mt5.last_error()}"
                continue
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                fill = float(result.price or price)
                ticket = int(result.order or result.deal or 0)
                return MT5OrderResult(
                    ticket=ticket,
                    symbol=symbol,
                    volume=volume,
                    price=fill,
                    retcode=int(result.retcode),
                )
            last_error = (
                f"رفض MT5 retcode={result.retcode} "
                f"comment={getattr(result, 'comment', '')} filling={filling}"
            )
            # invalid filling → جرّب التالي
            if int(result.retcode) in {10030, 10004, 10006, 10013, 10014, 10015, 10016}:
                continue

        raise ExecutionError(last_error)

    def modify_position_sl_tp(
        self,
        binance_symbol: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        """تعديل SL/TP على مركز MT5 المفتوح (يظهر في تطبيق الهاتف)."""
        if stop_loss is None and take_profit is None:
            return False

        mt5 = self.ensure_connected()
        symbol = self.resolve_symbol(binance_symbol)
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            raise ExecutionError(f"لا مركز مفتوح على MT5 لـ {symbol}")

        position = None
        for item in positions:
            if int(getattr(item, "magic", 0)) == 20260714:
                position = item
                break
        if position is None:
            position = positions[-1]

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(position.ticket),
            "symbol": symbol,
            "sl": float(stop_loss) if stop_loss is not None and stop_loss > 0 else float(position.sl),
            "tp": float(take_profit) if take_profit is not None and take_profit > 0 else float(position.tp),
        }
        result = mt5.order_send(request)
        if result is None:
            raise ExecutionError(f"تعديل SL/TP فشل: {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise ExecutionError(
                f"رفض MT5 تعديل SL/TP retcode={result.retcode} "
                f"comment={getattr(result, 'comment', '')}"
            )
        logger.info(
            "MT5 SL/TP updated %s ticket=%s sl=%s tp=%s",
            symbol,
            position.ticket,
            request["sl"],
            request["tp"],
        )
        return True

    def _get_managed_position(self, binance_symbol: str) -> Any | None:
        mt5 = self.ensure_connected()
        symbol = self.resolve_symbol(binance_symbol)
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return None
        for item in positions:
            if int(getattr(item, "magic", 0)) == 20260714:
                return item
        return positions[-1]

    def get_position_sl(self, binance_symbol: str) -> float | None:
        """قراءة SL الحالي للمركز — None إن لم يوجد مركز أو SL=0."""
        try:
            position = self._get_managed_position(binance_symbol)
            if position is None:
                return None
            sl = float(getattr(position, "sl", 0) or 0)
            return sl if sl > 0 else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_position_sl(%s) فشل: %s", binance_symbol, exc)
            return None

    def get_position_tp(self, binance_symbol: str) -> float | None:
        """قراءة TP الحالي للمركز — None إن لم يوجد مركز أو TP=0."""
        try:
            position = self._get_managed_position(binance_symbol)
            if position is None:
                return None
            tp = float(getattr(position, "tp", 0) or 0)
            return tp if tp > 0 else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_position_tp(%s) فشل: %s", binance_symbol, exc)
            return None

    def discover_tradeable_symbols(self) -> list[dict[str, str]]:
        """يكتشف عملات وفوركس متاحة على MT5 — للمزامنة التلقائية."""
        mt5 = self.ensure_connected()
        crypto_bases = {
            "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "LINK", "AVAX",
            "DOGE", "DOT", "MATIC", "LTC", "TRX", "ATOM", "BCH", "ETC",
        }
        forex_pairs = {
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
            "EURGBP", "EURJPY", "GBPJPY",
        }
        # معادن وطاقة على XM: GOLD/SILVER/USOIL أو XAUUSD...
        commodity_aliases = {
            "GOLD": "XAUUSD",
            "XAUUSD": "XAUUSD",
            "SILVER": "XAGUSD",
            "XAGUSD": "XAGUSD",
            "USOIL": "USOIL",
            "UKOIL": "UKOIL",
            "XTIUSD": "USOIL",
            "WTI": "USOIL",
        }

        def _match_forex(name: str) -> str | None:
            n = name.upper().replace("#", "").replace(".", "")
            if n in forex_pairs:
                return n
            for suf in ("PRO", "MICRO", "M", "I", "A"):
                if n.endswith(suf):
                    cand = n[: -len(suf)]
                    if cand in forex_pairs:
                        return cand
            for pair in forex_pairs:
                if n.startswith(pair):
                    return pair
            return None

        def _match_commodity(name: str) -> str | None:
            n = name.upper().replace("#", "").replace(".", "")
            if n in commodity_aliases:
                return commodity_aliases[n]
            for alias, canonical in commodity_aliases.items():
                if n.startswith(alias):
                    return canonical
            return None

        found: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for item in mt5.symbols_get() or []:
            name = str(item.name)
            commodity = _match_commodity(name)
            if commodity:
                symbol_id = f"FOREX/{commodity}"
                if symbol_id not in seen_ids:
                    seen_ids.add(symbol_id)
                    found.append({"kind": "forex", "id": symbol_id, "mt5": name})
                continue
            fx = _match_forex(name)
            if fx:
                symbol_id = f"FOREX/{fx}"
                if symbol_id not in seen_ids:
                    seen_ids.add(symbol_id)
                    found.append({"kind": "forex", "id": symbol_id, "mt5": name})
                continue
            if name.endswith("USD") and len(name) > 3:
                base = name[:-3]
                if base in crypto_bases:
                    symbol_id = f"{base}/USDT"
                    if symbol_id not in seen_ids:
                        seen_ids.add(symbol_id)
                        found.append({"kind": "crypto", "id": symbol_id, "mt5": name})
        return found


_bridge: MT5Bridge | None = None


def get_mt5_bridge() -> MT5Bridge:
    global _bridge
    if _bridge is None:
        _bridge = MT5Bridge()
    return _bridge
