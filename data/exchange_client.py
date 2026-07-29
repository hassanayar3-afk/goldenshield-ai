from __future__ import annotations

import ccxt

from config.settings import get_settings
from data.api_failover import (
    ApiCredential,
    failover_enabled,
    is_rate_limit_error,
    list_binance_credentials,
)

_exchange: ccxt.binance | None = None
_active_label: str = "primary"
_credential_index: int = 0


def _build_exchange(cred: ApiCredential | None) -> ccxt.binance:
    """يبني عميل Spot.

    - مفاتيح demo.binance.com تعمل فقط عبر enable_demo_trading(True).
    - المفاتيح الحية تُرفق في live؛ في paper العام تُجلب البيانات بلا مفاتيح إن لم يكن Demo.
    """
    settings = get_settings()
    demo = bool(getattr(settings, "binance_demo_trading", False))
    mode = str(getattr(settings, "execution_mode", "paper")).lower()

    config: dict = {
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
            "recvWindow": 60000,
        },
    }

    # Demo: دائماً نرفق المفاتيح ونوجّه لـ demo-api
    # Live: نرفق المفاتيح للمسارات الخاصة
    # Paper بدون Demo: عميل عام للأسعار فقط
    attach_keys = cred is not None and (demo or mode == "live")
    if attach_keys and cred is not None:
        config["apiKey"] = cred.api_key
        config["secret"] = cred.secret

    exchange = ccxt.binance(config)
    try:
        exchange.has["fetchCurrencies"] = False
    except Exception:
        pass

    if demo:
        try:
            exchange.enable_demo_trading(True)
        except Exception:
            # إصدارات أقدم: توجيه يدوي إن وُجدت الواجهة
            try:
                exchange.urls["api"] = dict(exchange.urls.get("api") or {})
                exchange.urls["api"]["public"] = "https://demo-api.binance.com/api/v3"
                exchange.urls["api"]["private"] = "https://demo-api.binance.com/api/v3"
                exchange.urls["api"]["v1"] = "https://demo-api.binance.com/api/v1"
            except Exception:
                pass
    return exchange


def get_exchange() -> ccxt.binance:
    """عميل Binance موحّد (Singleton) مع Rate Limiting + Failover."""
    global _exchange, _active_label, _credential_index

    if _exchange is not None:
        return _exchange

    creds = list_binance_credentials()
    if creds:
        _credential_index = 0
        _active_label = creds[0].label
        _exchange = _build_exchange(creds[0])
    else:
        _exchange = _build_exchange(None)
        _active_label = "anon"
    return _exchange


def active_credential_label() -> str:
    return _active_label


def rotate_exchange_on_rate_limit(exc: BaseException | None = None) -> bool:
    """تبديل للمفتاح الاحتياطي عند Rate Limit. يعيد True إن تم التبديل."""
    global _exchange, _active_label, _credential_index

    if not failover_enabled():
        return False
    if exc is not None and not is_rate_limit_error(exc):
        return False

    creds = list_binance_credentials()
    if len(creds) < 2:
        return False

    next_index = (_credential_index + 1) % len(creds)
    if next_index == _credential_index:
        return False

    _credential_index = next_index
    cred = creds[_credential_index]
    _active_label = cred.label
    _exchange = _build_exchange(cred)
    return True


def call_with_failover(fn, *args, **kwargs):
    """تنفيذ استدعاء ccxt مع محاولة تبديل مفتاح عند 418/429."""
    exchange = get_exchange()
    try:
        return fn(exchange, *args, **kwargs)
    except Exception as exc:
        if rotate_exchange_on_rate_limit(exc):
            exchange = get_exchange()
            return fn(exchange, *args, **kwargs)
        raise


def reset_exchange() -> None:
    """إعادة ضبط العميل — للاختبارات."""
    global _exchange, _active_label, _credential_index
    _exchange = None
    _active_label = "primary"
    _credential_index = 0
